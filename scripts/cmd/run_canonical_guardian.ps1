param(
    [int]$StallSeconds = 1800,
    [int]$PollSeconds = 120,
    [int]$LivePollSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$supervisor = Join-Path $PSScriptRoot "supervise_canonical.ps1"

& powershell -NoProfile -ExecutionPolicy Bypass -File $supervisor `
    -StallSeconds $StallSeconds `
    -PollSeconds $PollSeconds `
    -LivePollSeconds $LivePollSeconds `
    -Apply `
    -Loop `
    -StopWhenDone `
    -RefreshLiveOnce

if ($LASTEXITCODE -ne 0) {
    throw "run_canonical_guardian.ps1 failed with exit code $LASTEXITCODE"
}
