$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$port = 8000
$url = "http://127.0.0.1:$port/"

Set-Location $projectRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show("Python 3 was not found. Please install Python 3.9 or newer.", "Short Drama OS") | Out-Null
  exit 1
}

& $pythonCommand.Source -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
  & $pythonCommand.Source -m pip install -r (Join-Path $projectRoot "requirements.txt")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path (Join-Path $projectRoot "dist/client/index.html"))) {
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$health = $null
try { $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 1 } catch { }
if (-not $health) {
  Start-Process -FilePath $pythonCommand.Source `
    -ArgumentList "-m uvicorn backend.app:app --host 127.0.0.1 --port $port" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden | Out-Null
  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 1
      break
    } catch { }
  }
}

$browserCandidates = @(
  (Join-Path ${env:ProgramFiles} "Microsoft\Edge\Application\msedge.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
  (Join-Path ${env:LocalAppData} "Microsoft\Edge\Application\msedge.exe"),
  (Join-Path ${env:ProgramFiles} "Google\Chrome\Application\chrome.exe"),
  (Join-Path ${env:LocalAppData} "Google\Chrome\Application\chrome.exe")
)
$browser = $browserCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($browser) {
  Start-Process -FilePath $browser -ArgumentList "--app=$url", "--new-window" | Out-Null
} else {
  Start-Process $url | Out-Null
}
