$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DcHome = Resolve-Path (Join-Path $ScriptDir "..\..")
$RepoRoot = Resolve-Path (Join-Path $DcHome "..")
if (-not $env:DIAGNOSTIC_CLANK_HOME) { $env:DIAGNOSTIC_CLANK_HOME = "$DcHome" }
$env:PYTHONPATH = "$RepoRoot\clank-runtime\src;$RepoRoot\clank-desktop\src;$env:PYTHONPATH"
$Py = if ($env:DIAGNOSTIC_PYTHON) { $env:DIAGNOSTIC_PYTHON } else { "python" }
$Mode = if ($args.Count -gt 0) { $args[0] } elseif ($env:DIAGNOSTIC_MODE) { $env:DIAGNOSTIC_MODE } else { "inbox" }
$env:DIAGNOSTIC_MODE = $Mode
$LogDir = Join-Path $env:DIAGNOSTIC_CLANK_HOME "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Write-Host "[launch.ps1] home=$($env:DIAGNOSTIC_CLANK_HOME) mode=$Mode python=$Py"
& $Py (Join-Path $DcHome "launcher\common\preflight.py") $Mode
exit $LASTEXITCODE
