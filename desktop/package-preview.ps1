$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$artifactRoot = Join-Path $projectRoot "desktop-artifacts"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundleName = "Short-Drama-OS-Preview-$stamp"
$bundleRoot = Join-Path $artifactRoot $bundleName
$zipPath = Join-Path $artifactRoot "$bundleName.zip"

Set-Location $projectRoot
New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null

& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed; preview package was not created." }

foreach ($directory in @("backend", "desktop", "dist", "public")) {
  Copy-Item -Recurse -Force (Join-Path $projectRoot $directory) (Join-Path $bundleRoot $directory)
}
foreach ($file in @("requirements.txt", ".env.example", "package.json", "package-lock.json")) {
  Copy-Item -Force (Join-Path $projectRoot $file) (Join-Path $bundleRoot $file)
}

Get-ChildItem -LiteralPath (Join-Path $bundleRoot "backend") -Directory -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $bundleRoot -File -Filter "*.pyc" -Recurse | Remove-Item -Force

if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
Write-Output "Preview package created: $zipPath"
