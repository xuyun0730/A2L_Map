$ErrorActionPreference = "Stop"

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\3983\AppData\Local\Programs\Python\Python311\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Set-Location -LiteralPath $toolDir
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "MapA2LMatcher" `
    --distpath (Join-Path $toolDir "release") `
    --workpath (Join-Path $toolDir "build") `
    --specpath (Join-Path $toolDir "build") `
    "app.py"

$exe = Join-Path $toolDir "release\MapA2LMatcher.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "打包失败，未生成 $exe"
}

Write-Output "打包完成：$exe"
