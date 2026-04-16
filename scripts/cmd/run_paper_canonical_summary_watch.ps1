param(
    [string]$CanonicalReportDir = "report/formal_paper_canonical_s42_current",
    [int]$PollSeconds = 120,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$reportPath = Join-Path $repoRoot $CanonicalReportDir
$metricsCsv = Join-Path $reportPath "metrics_table.csv"
$taskCsv = Join-Path $reportPath "task_metrics.csv"

function Wait-ForFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    while (-not (Test-Path -LiteralPath $PathValue)) {
        Write-Host ("[{0}] waiting for {1}" -f (Get-Date -Format s), $PathValue)
        Start-Sleep -Seconds $PollSeconds
    }
}

Wait-ForFile -PathValue $metricsCsv
Wait-ForFile -PathValue $taskCsv

$metricsRows = Import-Csv -LiteralPath $metricsCsv
$taskRows = Import-Csv -LiteralPath $taskCsv
$baselineRow = $metricsRows | Where-Object { $_.method -like "baseline*" } | Select-Object -First 1
$agentRow = $metricsRows | Where-Object { $_.method -like "edge_agent*" } | Select-Object -First 1

if (-not $baselineRow -or -not $agentRow) {
    throw "Could not find baseline/agent rows in paper canonical metrics CSV"
}

$baselineF1 = [double]$baselineRow.f1
$agentF1 = [double]$agentRow.f1
$baselineP95 = [double]$baselineRow.p95_latency_ms
$agentP95 = [double]$agentRow.p95_latency_ms
$deltaF1 = $agentF1 - $baselineF1
$p95Ratio = if ($baselineP95 -gt 0) { $agentP95 / $baselineP95 } else { 0.0 }

Write-Host ("[{0}] paper canonical seed={1} overall baseline={2:N4} agent={3:N4} delta={4:N4} p95_ratio={5:N3}" -f (Get-Date -Format s), $Seed, $baselineF1, $agentF1, $deltaF1, $p95Ratio)

foreach ($task in @("single_doc_qa", "multi_doc_qa", "code_qa")) {
    $row = $taskRows | Where-Object { $_.method -like "edge_agent*" -and $_.task -eq $task } | Select-Object -First 1
    if ($row) {
        Write-Host ("[{0}] paper canonical task={1} f1={2} p95={3}" -f (Get-Date -Format s), $task, $row.f1, $row.p95_latency_ms)
    }
}

Write-Host ("[{0}] paper canonical summary watcher complete report={1}" -f (Get-Date -Format s), $reportPath)
