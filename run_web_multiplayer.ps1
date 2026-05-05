param(
    [int]$Port = 8000,
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$verifyScript = Join-Path $repoRoot "verify_web_multiplayer_setup.ps1"
$venvPython = Join-Path $repoRoot ".venv-web\Scripts\python.exe"

if (-not $SkipSetup) {
    powershell -ExecutionPolicy Bypass -File $verifyScript
}

if (-not (Test-Path $venvPython)) {
    throw ".venv-web\\Scripts\\python.exe was not found. Run verify_web_multiplayer_setup.ps1 first."
}

$existingJob = Get-Job -Name "pans_trial_room_server" -ErrorAction SilentlyContinue
if ($existingJob) {
    Remove-Job -Job $existingJob -Force
}

$roomServerJob = Start-Job -Name "pans_trial_room_server" -ScriptBlock {
    param($workingDir, $pythonPath)
    Set-Location $workingDir
    & $pythonPath ".\room_server.py"
} -ArgumentList $repoRoot, $venvPython

Write-Host ""
Write-Host "Pan's Trial room server job started: $($roomServerJob.Id)"
Write-Host "Game URL: http://localhost:$Port"
Write-Host "Two Player server URL: http://127.0.0.1:8765"
Write-Host "Room server logs: Receive-Job -Name pans_trial_room_server -Keep"
Write-Host ""

Set-Location $repoRoot
& $venvPython ".\build_web.py" --port $Port
