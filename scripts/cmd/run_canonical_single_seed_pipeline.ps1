param(
    [string]$Dataset = "data/main_eval/longbench_3tasks_test.jsonl",
    [string]$BaselineOut = "results/baseline_rag_formal_anchor_4b_canonical.jsonl",
    [string]$AgentConfig = "configs/agent_qwen3_4b_fast.yaml",
    [string]$AgentOut = "results/edge_agent_formal_fast_canonical_s42.jsonl",
    [string]$ReportDir = "report/formal_fast_canonical_s42_current",
    [string]$RunTag = "formal_fast_canonical_s42_current",
    [int]$ShardSize = 170,
    [int]$Concurrency = 2,
    [int]$Seed = 42,
    [int]$PollSeconds = 60,
    [int]$StallSeconds = 1800,
    [int]$MaxRetriesPerShard = 2
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$datasetPath = (Resolve-Path (Join-Path $repoRoot $Dataset)).Path
$baselinePath = Join-Path $repoRoot $BaselineOut
$agentConfigPath = Join-Path $repoRoot $AgentConfig
$agentPath = Join-Path $repoRoot $AgentOut
$reportPath = Join-Path $repoRoot $ReportDir
$runner = Join-Path $PSScriptRoot "run_sharded_canonical.ps1"

function Get-LineCount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    return (Get-Content -LiteralPath $Path | Measure-Object -Line).Lines
}

$expectedRows = Get-LineCount -Path $datasetPath
Write-Host ("[{0}] canonical single-seed pipeline start rows={1}" -f (Get-Date -Format s), $expectedRows)

while ((Get-LineCount -Path $baselinePath) -ne $expectedRows) {
    $baselineLines = Get-LineCount -Path $baselinePath
    Write-Host ("[{0}] waiting for baseline anchor: {1}/{2} lines" -f (Get-Date -Format s), $baselineLines, $expectedRows)
    Start-Sleep -Seconds $PollSeconds
}

Write-Host ("[{0}] baseline anchor ready: {1}" -f (Get-Date -Format s), $baselinePath)

if ((Get-LineCount -Path $agentPath) -ne $expectedRows) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runner `
        -Mode agent `
        -Config $AgentConfigPath `
        -Dataset $datasetPath `
        -Out $AgentOut `
        -ShardSize $ShardSize `
        -Concurrency $Concurrency `
        -Seed $Seed `
        -StallSeconds $StallSeconds `
        -MaxRetriesPerShard $MaxRetriesPerShard

    if ($LASTEXITCODE -ne 0) {
        throw "Agent sharded run failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host ("[{0}] agent output already complete: {1}" -f (Get-Date -Format s), $agentPath)
}

$agentLines = Get-LineCount -Path $agentPath
if ($agentLines -ne $expectedRows) {
    throw "Agent output incomplete: $agentLines / $expectedRows"
}

New-Item -ItemType Directory -Force -Path $reportPath | Out-Null

& $python (Join-Path $repoRoot "evaluate.py") `
    --gold $datasetPath `
    --pred $baselinePath $agentPath `
    --out_dir $reportPath `
    --run_mode formal `
    --task_breakdown `
    --run_tag $RunTag

if ($LASTEXITCODE -ne 0) {
    throw "evaluate.py failed with exit code $LASTEXITCODE"
}

$metricsCsv = Join-Path $reportPath "metrics_table.csv"
$taskCsv = Join-Path $reportPath "task_metrics.csv"
if (Test-Path -LiteralPath $metricsCsv) {
    $metricsRows = Import-Csv -LiteralPath $metricsCsv
    $baselineRow = $metricsRows | Where-Object { $_.method -like "baseline*" } | Select-Object -First 1
    $agentRow = $metricsRows | Where-Object { $_.method -like "edge_agent*" } | Select-Object -First 1
    if ($baselineRow -and $agentRow) {
        $baselineF1 = [double]$baselineRow.f1
        $agentF1 = [double]$agentRow.f1
        $baselineP95 = [double]$baselineRow.p95_latency_ms
        $agentP95 = [double]$agentRow.p95_latency_ms
        $deltaF1 = $agentF1 - $baselineF1
        $p95Ratio = if ($baselineP95 -gt 0) { $agentP95 / $baselineP95 } else { 0.0 }
        Write-Host ("[{0}] summary overall_f1 baseline={1:N4} agent={2:N4} delta={3:N4} p95_ratio={4:N3}" -f (Get-Date -Format s), $baselineF1, $agentF1, $deltaF1, $p95Ratio)
    }
}

if (Test-Path -LiteralPath $taskCsv) {
    $taskRows = Import-Csv -LiteralPath $taskCsv | Where-Object { $_.method -like "edge_agent*" }
    foreach ($row in $taskRows) {
        Write-Host ("[{0}] summary task={1} f1={2} p95={3}" -f (Get-Date -Format s), $row.task, $row.f1, $row.p95_latency_ms)
    }
}

Write-Host ("[{0}] canonical single-seed pipeline complete report={1}" -f (Get-Date -Format s), $reportPath)
