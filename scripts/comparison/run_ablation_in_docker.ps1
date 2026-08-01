#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Run ablation_runner.py inside Docker container. Copies scripts + fixtures,
  runs the benchmark, fetches report, cleans up temp files.

.PARAMETER Dataset
  Dataset name: golden_qa | expense_qa | enterprise_qa | advanced_qa | all
  Default: golden_qa.

.PARAMETER Output
  Optional host path for Markdown report (e.g. scripts/comparison/report.md).

.PARAMETER Verbose
  Show subprocess commands and full output.

.PARAMETER NoClean
  Keep temp files in container for debugging.

.PARAMETER Service
  Docker Compose service name (default: api).
#>

param(
    [ValidateSet("golden_qa", "expense_qa", "enterprise_qa", "advanced_qa", "all")]
    [string]$Dataset = "golden_qa",

    [string]$Output = "",

    [switch]$Verbose,

    [switch]$NoClean,

    [string]$Service = "api"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ScriptsHost = Join-Path $ProjectRoot "scripts"
$FixturesHost = Join-Path (Join-Path $ProjectRoot "backend") "tests/fixtures"

$CScripts = "/app/scripts"
$CFixtures = "/app/tests/fixtures"

# --- helpers ---
function Info  { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Ok    { Write-Host "[OK]   $args" -ForegroundColor DarkGreen }
function Warn  { Write-Host "[WARN] $args" -ForegroundColor DarkYellow }

function Cleanup {
    if ($NoClean) { return }
    Warn "Cleaning up container temp files..."
    docker compose exec $Service rm -rf $CScripts $CFixtures 2>$null
    Ok "Cleaned"
}

function CpFile {
    param([string]$Local, [string]$Remote)
    $remoteDir = Split-Path $Remote -Parent
    docker compose exec $Service mkdir -p $remoteDir 2>$null | Out-Null
    docker compose cp $Local "${Service}:${Remote}" 2>$null | Out-Null
}

# --- 1. check service ---
Info "Checking service: $Service ..."
$running = docker compose ps --filter "status=running" --services 2>$null
if ($running -notcontains $Service) {
    Write-Error "Service '$Service' not running. Run 'docker compose up -d' first."
    exit 1
}
Ok "Service '$Service' is running"

# --- 2. copy scripts ---
Info "Copying scripts..."
CpFile (Join-Path $ScriptsHost "run_benchmark.py") "${CScripts}/run_benchmark.py"
CpFile (Join-Path (Join-Path $ScriptsHost "comparison") "ablation_runner.py") "${CScripts}/comparison/ablation_runner.py"
Ok "run_benchmark.py + ablation_runner.py"

# --- 3. determine fixtures ---
$qaFiles = @()
$docFiles = @()
switch ($Dataset) {
    "golden_qa" {
        $qaFiles = @("golden_qa.json")
        $docFiles = @("golden_handbook.md")
    }
    "expense_qa" {
        $qaFiles = @("expense_qa.json")
        $docFiles = @("expense_policy.md")
    }
    "enterprise_qa" {
        $qaFiles = @("enterprise_qa.json")
        $docFiles = @("acme_FAQ合集.md", "acme_产品规格书.md", "acme_员工手册_英文.md",
                      "acme_季度报告.md", "acme_操作手册.md", "acme_框架合同.md")
    }
    "advanced_qa" {
        $qaFiles = @("advanced_qa.json")
        $docFiles = @("golden_handbook.md")
    }
    "all" {
        $qaFiles = @("golden_qa.json", "expense_qa.json", "enterprise_qa.json", "advanced_qa.json")
        $docFiles = @("golden_handbook.md", "expense_policy.md",
                      "acme_FAQ合集.md", "acme_产品规格书.md", "acme_员工手册_英文.md",
                      "acme_季度报告.md", "acme_操作手册.md", "acme_框架合同.md")
    }
}

# --- 4. copy fixtures ---
Info "Copying fixture data..."
foreach ($f in $qaFiles) {
    $src = Join-Path $FixturesHost $f
    if (Test-Path $src) { CpFile $src "${CFixtures}/$f"; Ok $f }
    else { Warn "Not found: $src" }
}
foreach ($f in $docFiles) {
    $src = Join-Path $FixturesHost $f
    if (Test-Path $src) { CpFile $src "${CFixtures}/$f"; Ok $f }
    else { Warn "Not found: $src" }
}

# --- 5. run ablation ---
$execArgs = @("exec", "-e", "PYTHONPATH=/app")
if ($Verbose) { $execArgs += "-e", "PYTHONIOENCODING=utf-8" }

$runnerArgs = @("python", "${CScripts}/comparison/ablation_runner.py", "--dataset", $Dataset)
if ($Output) { $runnerArgs += "--output", "${CScripts}/comparison/report.md" }
if ($Verbose) { $runnerArgs += "--verbose" }

$timeoutSec = if ($Dataset -eq "all") { 3600 } else { 900 }

Info "Running ablation experiment (dataset=$Dataset, timeout=${timeoutSec}s)..."

$timer = [System.Diagnostics.Stopwatch]::StartNew()
$allArgs = $execArgs + $Service + $runnerArgs

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "docker"
$psi.Arguments = "compose " + ($allArgs -join " ")
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

$proc = [System.Diagnostics.Process]::Start($psi)
$buf = New-Object System.Text.StringBuilder
while (-not $proc.StandardOutput.EndOfStream) {
    $line = $proc.StandardOutput.ReadLine()
    $null = $buf.AppendLine($line)
    if ($Verbose) { Write-Host $line }
}
$err = $proc.StandardError.ReadToEnd()
$proc.WaitForExit($timeoutSec * 1000) | Out-Null
$timer.Stop()
$output = $buf.ToString()

if (-not $proc.HasExited) { Warn "Timed out ${timeoutSec}s"; $proc.Kill() }
elseif ($proc.ExitCode -ne 0) { Warn "Exit code $($proc.ExitCode)" }

# print summary (matrix only) if not verbose
if ($output -and (-not $Verbose)) {
    $lines = $output -split "`n"
    $show = $false
    foreach ($line in $lines) {
        if ($line -match "检索质量消融矩阵|配置\s+Hat@3|Hit@3|边际提升|数据集:|═|─") { $show = $true }
        if ($show) { Write-Host $line }
    }
}
if ($err -and $Verbose) { Write-Host $err -ForegroundColor DarkRed }

$elapsed = $timer.Elapsed.TotalSeconds.ToString('0.0')
Info "Elapsed: ${elapsed}s"

# --- 6. fetch report ---
if ($Output) {
    $rPath = "${CScripts}/comparison/report.md"
    $outPath = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $ProjectRoot $Output }
    $outDir = Split-Path -Parent $outPath
    if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
    docker compose cp "${Service}:${rPath}" $outPath 2>$null | Out-Null
    if (Test-Path $outPath) { Ok "Report: $outPath" }
    else { Warn "Report not generated" }
}

# --- 7. clean ---
Cleanup
Ok "Done"
