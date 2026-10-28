$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') {
    throw 'Build this package on Windows x64 with Python 3.12 (3.10+ required).'
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Venv = Join-Path $Root '.venv-windows-build'
$Python = Join-Path $Venv 'Scripts/python.exe'
if (-not (Test-Path $Python)) {
    & python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated build environment.' }
}
& $Python -c "import sys; assert sys.version_info >= (3,10); assert sys.maxsize > 2**32, 'Use x64 Python'"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ x64 is required.' }
& $Python -m pip install --disable-pip-version-check -r requirements-build-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

$RunId = [Guid]::NewGuid().ToString('N')
$Output = Join-Path $Root "dist/windows-$RunId"
$Work = Join-Path $Root "build/windows-$RunId"
# Build tools on PATH can contain unrelated ICU/API-set DLLs with the same names
# as Windows system libraries. Do not let PyInstaller bundle those by accident.
$TaskOriginalPath = $env:PATH
$TaskOriginalConsole = $env:FUCKZHS_BUILD_CONSOLE
try {
    $BasePython = & $Python -c "import sys; print(sys.base_prefix)"
    $env:PATH = @((Split-Path $Python), $BasePython, (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
    $env:FUCKZHS_BUILD_CONSOLE = '0'
    & $Python -m PyInstaller --noconfirm --clean --distpath $Output --workpath $Work fuckZHS.spec
    $TaskBuildExit = $LASTEXITCODE
} finally {
    $env:PATH = $TaskOriginalPath
    $env:FUCKZHS_BUILD_CONSOLE = $TaskOriginalConsole
}
if ($TaskBuildExit -ne 0) { throw 'PyInstaller build failed.' }
$App = Join-Path $Output 'fuckZHS'
Copy-Item (Join-Path $Root 'packaging/windows/README.txt') $App
Copy-Item (Join-Path $Root 'LICENSE') $App

# Audit the finished application, never copy the repository or a local profile.
$ForbiddenNames = @('key','config.json','cookies.json','execution.json','daily_limit.json','qr.temp.jpg','.env','run.lock')
$ForbiddenDirectories = @('profiles','logs','images','.venv','.venv-windows-build','aiexamAnswer','AiDownloadCache')
$Leaks = Get-ChildItem $App -Recurse -Force | Where-Object {
    if ($_.PSIsContainer) { $ForbiddenDirectories -contains $_.Name }
    else { $ForbiddenNames -contains $_.Name -or $_.Extension -eq '.log' }
}
if ($Leaks) { throw 'Privacy audit failed: a forbidden private file or directory was included.' }
# Wait explicitly: windowed executables do not reliably set LASTEXITCODE in PowerShell.
$Smoke = Start-Process -FilePath (Join-Path $App 'fuckZHS.exe') -ArgumentList '--gui-smoke-test' -WindowStyle Hidden -PassThru
if (-not $Smoke.WaitForExit(30000)) {
    Stop-Process -Id $Smoke.Id -ErrorAction SilentlyContinue
    throw 'Packaged executable smoke test did not finish within 30 seconds.'
}
$LASTEXITCODE = $Smoke.ExitCode
if ($LASTEXITCODE -ne 0) { throw 'Packaged executable smoke test failed.' }
$Archive = Join-Path $Root 'dist/fuckZHS-Windows-x64.zip'
Compress-Archive -Path $App -DestinationPath $Archive -Force
Get-FileHash $Archive -Algorithm SHA256
Write-Output "Windows package: $Archive"
