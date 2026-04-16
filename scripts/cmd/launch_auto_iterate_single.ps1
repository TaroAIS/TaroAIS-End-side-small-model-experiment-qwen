param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$lockPath = Join-Path $repoRoot "results\\auto_iterate_launcher.lock"
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$scriptPath = Join-Path $repoRoot "scripts\\auto_iterate_formal.py"

$lockHandle = $null
try {
    $lockHandle = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
} catch [System.IO.IOException] {
    Write-Output "[skip] launcher lock exists: $lockPath"
    exit 0
}

try {
    $payload = @{
        pid = $PID
        created_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    } | ConvertTo-Json
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $lockHandle.Write($bytes, 0, $bytes.Length)
    $lockHandle.Flush()
    $lockHandle.Close()
    $lockHandle = $null

    & $python $scriptPath @ForwardArgs
    exit $LASTEXITCODE
} finally {
    if ($lockHandle) {
        $lockHandle.Dispose()
    }
    if (Test-Path $lockPath) {
        Remove-Item -LiteralPath $lockPath -Force
    }
}
