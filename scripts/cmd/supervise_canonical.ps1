param(
    [int]$StallSeconds = 1800,
    [int]$PollSeconds = 120,
    [int]$LivePollSeconds = 120,
    [switch]$Apply,
    [switch]$Loop,
    [switch]$StopWhenDone,
    [switch]$RefreshLiveOnce
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$script = Join-Path $repoRoot "scripts\\supervise_canonical.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python executable not found: $python"
}

$args = @(
    $script,
    "--stall_seconds", "$StallSeconds",
    "--poll_seconds", "$PollSeconds",
    "--live_poll_seconds", "$LivePollSeconds"
)
if ($Apply) {
    $args += "--apply"
}
if ($Loop) {
    $args += "--loop"
}
if ($StopWhenDone) {
    $args += "--stop_when_done"
}
if ($RefreshLiveOnce) {
    $args += "--refresh_live_once"
}

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "supervise_canonical.py failed with exit code $LASTEXITCODE"
}
