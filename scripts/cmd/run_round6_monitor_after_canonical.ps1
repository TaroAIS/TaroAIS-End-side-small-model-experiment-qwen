param(
    [string]$CanonicalReportDir = "report/formal_fast_canonical_s42_current",
    [int]$PollSeconds = 120,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
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

function Run-MonitorEval {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Config,
        [Parameter(Mandatory = $true)]
        [string]$Dataset,
        [Parameter(Mandatory = $true)]
        [string]$Out,
        [Parameter(Mandatory = $true)]
        [string]$BaselinePred,
        [Parameter(Mandatory = $true)]
        [string]$ReportDir,
        [Parameter(Mandatory = $true)]
        [string]$RunTag
    )

    & $python (Join-Path $repoRoot "run_agent.py") `
        --config (Join-Path $repoRoot $Config) `
        --dataset (Join-Path $repoRoot $Dataset) `
        --out (Join-Path $repoRoot $Out) `
        --run_mode formal `
        --seed $Seed

    if ($LASTEXITCODE -ne 0) {
        throw "run_agent.py failed for $Config on $Dataset"
    }

    & $python (Join-Path $repoRoot "evaluate.py") `
        --gold (Join-Path $repoRoot $Dataset) `
        --pred (Join-Path $repoRoot $BaselinePred) (Join-Path $repoRoot $Out) `
        --out_dir (Join-Path $repoRoot $ReportDir) `
        --run_mode formal `
        --task_breakdown `
        --run_tag $RunTag

    if ($LASTEXITCODE -ne 0) {
        throw "evaluate.py failed for $Config on $Dataset"
    }
}

Wait-ForFile -PathValue $metricsCsv
Wait-ForFile -PathValue $taskCsv

$metricsRows = Import-Csv -LiteralPath $metricsCsv
$taskRows = Import-Csv -LiteralPath $taskCsv | Where-Object { $_.method -like "edge_agent*" }
$baselineRow = $metricsRows | Where-Object { $_.method -like "baseline*" } | Select-Object -First 1
$agentRow = $metricsRows | Where-Object { $_.method -like "edge_agent*" } | Select-Object -First 1

if (-not $baselineRow -or -not $agentRow) {
    throw "Could not find baseline/agent rows in canonical metrics CSV"
}

$overall = [double]$agentRow.f1
$singleDoc = [double](($taskRows | Where-Object { $_.task -eq "single_doc_qa" } | Select-Object -First 1).f1)
$multiDoc = [double](($taskRows | Where-Object { $_.task -eq "multi_doc_qa" } | Select-Object -First 1).f1)
$code = [double](($taskRows | Where-Object { $_.task -eq "code_qa" } | Select-Object -First 1).f1)
$baselineP95 = [double]$baselineRow.p95_latency_ms
$agentP95 = [double]$agentRow.p95_latency_ms
$p95Ratio = if ($baselineP95 -gt 0) { $agentP95 / $baselineP95 } else { 0.0 }

Write-Host ("[{0}] canonical summary overall={1:N4} single_doc={2:N4} multi_doc={3:N4} code={4:N4} p95_ratio={5:N3}" -f (Get-Date -Format s), $overall, $singleDoc, $multiDoc, $code, $p95Ratio)

if ($overall -ge 0.34 -and $singleDoc -ge 0.29 -and $p95Ratio -le 1.8) {
    Write-Host ("[{0}] canonical gate passed; freeze fast line and stop Round 6 automation" -f (Get-Date -Format s))
    exit 0
}

if ($p95Ratio -gt 1.8) {
    Write-Host ("[{0}] canonical gate failed on latency; do not launch heavier Round 6 candidates" -f (Get-Date -Format s))
    exit 0
}

$candidateConfig = ""
$candidateTag = ""
if ($multiDoc -le $code -and $multiDoc -le $singleDoc) {
    $candidateConfig = "configs/agent_round6_multi_doc_only_lift.yaml"
    $candidateTag = "round6_multi_doc_only_lift"
} elseif ($code -lt 0.43) {
    $candidateConfig = "configs/agent_round6_code_only_lift.yaml"
    $candidateTag = "round6_code_only_lift"
} else {
    Write-Host ("[{0}] canonical miss is not cleanly attributable; keep current fast line frozen for manual review" -f (Get-Date -Format s))
    exit 0
}

Write-Host ("[{0}] launching Round 6 monitor candidate {1}" -f (Get-Date -Format s), $candidateConfig)

Run-MonitorEval `
    -Config $candidateConfig `
    -Dataset "data/main_eval/longbench_3tasks_quickgate30.jsonl" `
    -Out ("results/edge_agent_{0}_quickgate30.jsonl" -f $candidateTag) `
    -BaselinePred "results/baseline_rag_formal_anchor_4b_quickgate30.jsonl" `
    -ReportDir ("report/{0}_quickgate30" -f $candidateTag) `
    -RunTag ("{0}_quickgate30" -f $candidateTag)

Run-MonitorEval `
    -Config $candidateConfig `
    -Dataset "data/main_eval/longbench_3tasks_holdout100.jsonl" `
    -Out ("results/edge_agent_{0}_holdout100.jsonl" -f $candidateTag) `
    -BaselinePred "results/baseline_rag_formal_anchor_4b_holdout100.jsonl" `
    -ReportDir ("report/{0}_holdout100" -f $candidateTag) `
    -RunTag ("{0}_holdout100" -f $candidateTag)

Write-Host ("[{0}] Round 6 monitor candidate finished: {1}" -f (Get-Date -Format s), $candidateConfig)
