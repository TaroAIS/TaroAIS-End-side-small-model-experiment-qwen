param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("baseline", "agent")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$Config,

    [Parameter(Mandatory = $true)]
    [string]$Dataset,

    [Parameter(Mandatory = $true)]
    [string]$Out,

    [int]$ShardSize = 170,
    [int]$Concurrency = 2,
    [int]$Seed = 42,
    [string]$RunMode = "formal",
    [string]$RetrievalScope = "sample",
    [int]$StartIdx = 0,
    [int]$EndIdx = -1,
    [bool]$Resume = $true,
    [int]$PollSeconds = 15,
    [int]$StallSeconds = 1800,
    [int]$MaxRetriesPerShard = 2
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$concatScript = Join-Path $repoRoot "scripts\\concat_jsonl.py"

function Resolve-RepoPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return (Resolve-Path -LiteralPath $PathValue).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $repoRoot $PathValue)).Path
}

function Get-LineCount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return 0
    }
    return (Get-Content -LiteralPath $PathValue | Measure-Object -Line).Lines
}

function Get-FileLength {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return 0
    }
    return (Get-Item -LiteralPath $PathValue).Length
}

function Backup-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,

        [Parameter(Mandatory = $true)]
        [string]$Suffix
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }
    $backup = "{0}.{1}.bak" -f $PathValue, $Suffix
    Move-Item -LiteralPath $PathValue -Destination $backup -Force
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python executable not found: $python"
}

$configPath = Resolve-RepoPath -PathValue $Config
$datasetPath = Resolve-RepoPath -PathValue $Dataset
$outPath = if ([System.IO.Path]::IsPathRooted($Out)) {
    $Out
} else {
    Join-Path $repoRoot $Out
}
$scriptPath = if ($Mode -eq "baseline") {
    Join-Path $repoRoot "run_baseline_rag.py"
} else {
    Join-Path $repoRoot "run_agent.py"
}

$totalRows = (Get-Content -LiteralPath $datasetPath | Measure-Object -Line).Lines
if ($EndIdx -lt 0 -or $EndIdx -gt $totalRows) {
    $EndIdx = $totalRows
}
if ($StartIdx -lt 0 -or $StartIdx -ge $EndIdx) {
    throw "Invalid slice range [${StartIdx}:${EndIdx}) for total rows $totalRows"
}

$outDir = Split-Path -Parent $outPath
if ([string]::IsNullOrWhiteSpace($outDir)) {
    $outDir = $repoRoot
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$stem = [System.IO.Path]::GetFileNameWithoutExtension($outPath)
$ext = [System.IO.Path]::GetExtension($outPath)
$shardRoot = Join-Path $repoRoot "results\\_sharded\\$stem"
$logRoot = Join-Path $repoRoot "logs\\sharded\\$stem"
$statePath = Join-Path $shardRoot "_runner_state.json"
New-Item -ItemType Directory -Force -Path $shardRoot | Out-Null
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$jobs = @()
$shardIndex = 0
for ($s = $StartIdx; $s -lt $EndIdx; $s += $ShardSize) {
    $e = [Math]::Min($s + $ShardSize, $EndIdx)
    $jobs += [pscustomobject]@{
        Name = "{0}_{1:0000}_{2:0000}" -f $stem, $s, $e
        Start = $s
        End = $e
        ExpectedLines = ($e - $s)
        ShardIndex = $shardIndex
        Out = Join-Path $shardRoot ("{0}_{1:0000}_{2:0000}{3}" -f $stem, $s, $e, $ext)
        Stdout = Join-Path $logRoot ("{0}_{1:0000}_{2:0000}.out.log" -f $stem, $s, $e)
        Stderr = Join-Path $logRoot ("{0}_{1:0000}_{2:0000}.err.log" -f $stem, $s, $e)
    }
    $shardIndex += 1
}

$jobStatus = @{}
$jobAttempts = @{}
$jobNote = @{}
$jobPid = @{}
$jobLastActivity = @{}

function Write-RunnerState {
    $jobStates = @()
    foreach ($job in ($jobs | Sort-Object Start)) {
        $jobStates += [ordered]@{
            name = $job.Name
            start = $job.Start
            end = $job.End
            expected_lines = $job.ExpectedLines
            status = $jobStatus[$job.Name]
            attempts = [int]$jobAttempts[$job.Name]
            pid = [int]($jobPid[$job.Name] | ForEach-Object { if ($_ -eq $null) { 0 } else { $_ } })
            out = $job.Out
            out_lines = Get-LineCount -PathValue $job.Out
            stdout = $job.Stdout
            stdout_length = Get-FileLength -PathValue $job.Stdout
            stderr = $job.Stderr
            stderr_length = Get-FileLength -PathValue $job.Stderr
            last_activity = if ($jobLastActivity[$job.Name]) { ([datetime]$jobLastActivity[$job.Name]).ToString("s") } else { "" }
            note = $jobNote[$job.Name]
        }
    }

    $state = [ordered]@{
        updated_at = (Get-Date).ToString("s")
        stem = $stem
        mode = $Mode
        config = $configPath
        dataset = $datasetPath
        out = $outPath
        resume = $Resume
        run_mode = $RunMode
        total_rows = $totalRows
        start_idx = $StartIdx
        end_idx = $EndIdx
        shard_size = $ShardSize
        concurrency = $Concurrency
        stall_seconds = $StallSeconds
        max_retries_per_shard = $MaxRetriesPerShard
        completed_shards = @($jobs | Where-Object { $jobStatus[$_.Name] -eq "completed" }).Count
        running_shards = @($jobs | Where-Object { $jobStatus[$_.Name] -eq "running" }).Count
        pending_shards = @($jobs | Where-Object { $jobStatus[$_.Name] -in @("pending", "retry_pending") }).Count
        failed_shards = @($jobs | Where-Object { $jobStatus[$_.Name] -eq "failed" }).Count
        jobs = $jobStates
    }
    $json = $state | ConvertTo-Json -Depth 6
    Set-Content -LiteralPath $statePath -Value $json -Encoding UTF8
}

function Start-ShardProcess {
    param(
        [Parameter(Mandatory = $true)]
        $Job
    )

    $jobAttempts[$Job.Name] = [int]$jobAttempts[$Job.Name] + 1
    $attempt = [int]$jobAttempts[$Job.Name]

    if (-not $Resume -and (Test-Path -LiteralPath $Job.Out)) {
        Remove-Item -LiteralPath $Job.Out -Force
    }
    Backup-IfExists -PathValue $Job.Stdout -Suffix ("attempt{0}" -f $attempt)
    Backup-IfExists -PathValue $Job.Stderr -Suffix ("attempt{0}" -f $attempt)

    $args = @(
        $scriptPath,
        "--config", $configPath,
        "--dataset", $datasetPath,
        "--out", $Job.Out,
        "--run_mode", $RunMode,
        "--seed", "$Seed",
        "--start_idx", "$($Job.Start)",
        "--end_idx", "$($Job.End)",
        "--flush_every", "1",
        "--progress_interval", "5"
    )
    if ($Mode -eq "baseline") {
        $args += @("--retrieval_scope", $RetrievalScope)
    }
    if ($Resume) {
        $args += @("--resume")
    }

    $quotedArgs = $args | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }
    $argLine = $quotedArgs -join " "

    $proc = Start-Process -FilePath $python `
        -ArgumentList $argLine `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $Job.Stdout `
        -RedirectStandardError $Job.Stderr `
        -PassThru

    $now = Get-Date
    $jobStatus[$Job.Name] = "running"
    $jobNote[$Job.Name] = "launched attempt=$attempt"
    $jobPid[$Job.Name] = $proc.Id
    $jobLastActivity[$Job.Name] = $now

    return [pscustomobject]@{
        Job = $Job
        Proc = $proc
        Attempt = $attempt
        LastCpu = if ($proc.CPU -ne $null) { [double]$proc.CPU } else { 0.0 }
        LastActivity = $now
        LastStdoutLength = Get-FileLength -PathValue $Job.Stdout
        LastStderrLength = Get-FileLength -PathValue $Job.Stderr
        LastOutLines = Get-LineCount -PathValue $Job.Out
    }
}

$pending = @()
$running = @()
$completed = @()
$failed = @()
$launchTime = Get-Date

function Pop-NextPendingJob {
    if ($pending.Count -le 0) {
        return $null
    }

    $ordered = $pending | Sort-Object `
        @{ Expression = { if ($jobStatus[$_.Name] -eq "retry_pending") { 0 } else { 1 } } }, `
        @{ Expression = { $_.Start } }
    $selected = $ordered | Select-Object -First 1
    if ($null -eq $selected) {
        return $null
    }

    $script:pending = @($pending | Where-Object { $_.Name -ne $selected.Name })
    return $selected
}

foreach ($job in $jobs) {
    $jobAttempts[$job.Name] = 0
    $existingLines = Get-LineCount -PathValue $job.Out
    if ($Resume -and $existingLines -eq $job.ExpectedLines) {
        $jobStatus[$job.Name] = "completed"
        $jobNote[$job.Name] = "resume_skip lines=$existingLines"
        $jobPid[$job.Name] = 0
        $jobLastActivity[$job.Name] = Get-Date
        $completed += $job
        Write-Host ("[{0}] resume skip shard [{1}:{2}) lines={3}" -f (Get-Date -Format s), $job.Start, $job.End, $existingLines)
    } else {
        $jobStatus[$job.Name] = if ($existingLines -gt 0) { "retry_pending" } else { "pending" }
        $jobNote[$job.Name] = if ($existingLines -gt 0) { "resume_partial lines=$existingLines" } else { "queued" }
        $jobPid[$job.Name] = 0
        $jobLastActivity[$job.Name] = $null
        $pending += ,$job
    }
}

Write-Host ("[{0}] start {1} sharded run: mode={2} shards={3} concurrency={4} range=[{5}:{6}) resume={7}" -f (Get-Date -Format s), $stem, $Mode, $jobs.Count, $Concurrency, $StartIdx, $EndIdx, $Resume)
Write-RunnerState

while ($pending.Count -gt 0 -or $running.Count -gt 0) {
    while ($pending.Count -gt 0 -and $running.Count -lt $Concurrency) {
        $job = Pop-NextPendingJob
        if ($null -eq $job) {
            break
        }
        $entry = Start-ShardProcess -Job $job
        $running += $entry
        Write-Host ("[{0}] launched shard {1}/{2}: [{3}:{4}) pid={5} attempt={6}" -f (Get-Date -Format s), ($job.ShardIndex + 1), $jobs.Count, $job.Start, $job.End, $entry.Proc.Id, $entry.Attempt)
    }

    Write-RunnerState
    Start-Sleep -Seconds $PollSeconds

    $stillRunning = @()
    foreach ($entry in $running) {
        $entry.Proc.Refresh()
        if (-not $entry.Proc.HasExited) {
            $activityDetected = $false
            $currentCpu = if ($entry.Proc.CPU -ne $null) { [double]$entry.Proc.CPU } else { 0.0 }
            $stdoutLength = Get-FileLength -PathValue $entry.Job.Stdout
            $stderrLength = Get-FileLength -PathValue $entry.Job.Stderr
            $outLines = Get-LineCount -PathValue $entry.Job.Out

            if ($currentCpu -gt ($entry.LastCpu + 0.02)) {
                $entry.LastCpu = $currentCpu
                $activityDetected = $true
            }
            if ($stdoutLength -gt $entry.LastStdoutLength) {
                $entry.LastStdoutLength = $stdoutLength
                $activityDetected = $true
            }
            if ($stderrLength -gt $entry.LastStderrLength) {
                $entry.LastStderrLength = $stderrLength
                $activityDetected = $true
                $jobNote[$entry.Job.Name] = "stderr_growth bytes=$stderrLength"
            }
            if ($outLines -gt $entry.LastOutLines) {
                $entry.LastOutLines = $outLines
                $activityDetected = $true
            }
            if ($activityDetected) {
                $entry.LastActivity = Get-Date
                $jobLastActivity[$entry.Job.Name] = $entry.LastActivity
                $jobNote[$entry.Job.Name] = "running lines=$outLines stdout_bytes=$stdoutLength stderr_bytes=$stderrLength"
            }

            $idleSeconds = ((Get-Date) - $entry.LastActivity).TotalSeconds
            if ($idleSeconds -ge $StallSeconds) {
                Write-Host ("[{0}] stalled shard [{1}:{2}) idle_seconds={3:N0} attempt={4}" -f (Get-Date -Format s), $entry.Job.Start, $entry.Job.End, $idleSeconds, $entry.Attempt)
                try {
                    Stop-Process -Id $entry.Proc.Id -Force -ErrorAction SilentlyContinue
                } catch {
                }
                $jobPid[$entry.Job.Name] = 0
                if ([int]$jobAttempts[$entry.Job.Name] -le $MaxRetriesPerShard) {
                    $jobStatus[$entry.Job.Name] = "retry_pending"
                    $jobNote[$entry.Job.Name] = "stalled idle_seconds=$([int]$idleSeconds);retrying"
                    $pending += ,$entry.Job
                } else {
                    $jobStatus[$entry.Job.Name] = "failed"
                    $jobNote[$entry.Job.Name] = "stalled idle_seconds=$([int]$idleSeconds);max_retries_exceeded"
                    $failed += [pscustomobject]@{
                        Job = $entry.Job
                        ExitCode = -1
                    }
                }
                continue
            }

            $stillRunning += $entry
            continue
        }

        $exitCode = $entry.Proc.ExitCode
        $outLines = Get-LineCount -PathValue $entry.Job.Out

        if ($outLines -eq $entry.Job.ExpectedLines) {
            $completed += $entry.Job
            $jobStatus[$entry.Job.Name] = "completed"
            $jobNote[$entry.Job.Name] = "completed lines=$outLines exit=$exitCode"
            $jobPid[$entry.Job.Name] = 0
            $jobLastActivity[$entry.Job.Name] = Get-Date
            Write-Host ("[{0}] completed shard [{1}:{2}) lines={3}" -f (Get-Date -Format s), $entry.Job.Start, $entry.Job.End, $outLines)
        } else {
            $jobPid[$entry.Job.Name] = 0
            $jobLastActivity[$entry.Job.Name] = Get-Date
            if ([int]$jobAttempts[$entry.Job.Name] -le $MaxRetriesPerShard) {
                $jobStatus[$entry.Job.Name] = "retry_pending"
                $jobNote[$entry.Job.Name] = "exit=$exitCode partial_lines=$outLines expected=$($entry.Job.ExpectedLines);retrying"
                $pending += ,$entry.Job
                Write-Host ("[{0}] retry shard [{1}:{2}) exit={3} partial_lines={4}" -f (Get-Date -Format s), $entry.Job.Start, $entry.Job.End, $exitCode, $outLines)
            } else {
                $failed += [pscustomobject]@{
                    Job = $entry.Job
                    ExitCode = $exitCode
                }
                $jobStatus[$entry.Job.Name] = "failed"
                $jobNote[$entry.Job.Name] = "exit=$exitCode partial_lines=$outLines expected=$($entry.Job.ExpectedLines);max_retries_exceeded"
                Write-Host ("[{0}] failed shard [{1}:{2}) exit={3} partial_lines={4}" -f (Get-Date -Format s), $entry.Job.Start, $entry.Job.End, $exitCode, $outLines)
            }
        }
    }
    $running = $stillRunning
    Write-RunnerState
}

if ($failed.Count -gt 0) {
    $failedRanges = ($failed | ForEach-Object { "[{0}:{1})" -f $_.Job.Start, $_.Job.End }) -join ", "
    Write-RunnerState
    throw "One or more shards failed: $failedRanges"
}

$concatArgs = @($concatScript, "--out", $outPath)
foreach ($job in ($jobs | Sort-Object Start)) {
    $concatArgs += $job.Out
}

& $python @concatArgs
if ($LASTEXITCODE -ne 0) {
    throw "concat_jsonl failed with exit code $LASTEXITCODE"
}

$elapsed = ((Get-Date) - $launchTime).TotalSeconds
$finalLines = (Get-Content -LiteralPath $outPath | Measure-Object -Line).Lines
Write-RunnerState
Write-Host ("[{0}] merged output={1} lines={2} elapsed_seconds={3:N1}" -f (Get-Date -Format s), $outPath, $finalLines, $elapsed)
