param(
    [int]$StallSeconds = 1800,
    [int]$PollSeconds = 120,
    [int]$LivePollSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$guardian = Join-Path $PSScriptRoot "run_canonical_guardian.ps1"
$logDir = Join-Path $repoRoot "logs\\canonical_guardian"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stdout = Join-Path $logDir "stdout.log"
$stderr = Join-Path $logDir "stderr.log"
$pidFile = Join-Path $logDir "pid.txt"

$command = "& '$guardian' -StallSeconds $StallSeconds -PollSeconds $PollSeconds -LivePollSeconds $LivePollSeconds"
$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $proc.Id
Write-Host ("launched canonical guardian pid={0}" -f $proc.Id)
