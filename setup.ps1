param(
    [string]$Python,
    [string]$CreoRoot,
    [string]$VcVars64,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Windows x64 is required.'
}

$settingsPath = Join-Path $PSScriptRoot 'config.json'
$settingsSource = if (Test-Path -LiteralPath $settingsPath) { $settingsPath } else { Join-Path $PSScriptRoot 'config.example.json' }
$settings = Get-Content -LiteralPath $settingsSource -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $CreoRoot) { $CreoRoot = $settings.creo_root }
if (-not $VcVars64 -and (Test-Path -LiteralPath $settings.vcvars64 -PathType Leaf)) { $VcVars64 = $settings.vcvars64 }
if (-not $VcVars64) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $vsInstallation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0 -and $vsInstallation) {
            $VcVars64 = Join-Path ($vsInstallation | Select-Object -First 1) 'VC\Auxiliary\Build\vcvars64.bat'
        }
    }
}
if (-not $VcVars64) { throw 'MSVC x64 tools not found. Install Visual Studio C++ Build Tools, or pass -VcVars64.' }
foreach ($localPath in @($CreoRoot, $VcVars64, $PSScriptRoot)) {
    if ($localPath -match '[\r\n"%]') { throw 'Installation paths cannot contain quotes, percent signs or newlines.' }
}
if (-not (Test-Path -LiteralPath $CreoRoot -PathType Container)) { throw 'Creo installation not found. Pass -CreoRoot with your Creo 10 installation directory.' }
$CreoRoot = (Resolve-Path -LiteralPath $CreoRoot).ProviderPath
if (-not (Test-Path -LiteralPath $VcVars64 -PathType Leaf)) { throw 'vcvars64.bat not found. Pass -VcVars64 with the installed compiler setup file.' }
$VcVars64 = (Resolve-Path -LiteralPath $VcVars64).ProviderPath
$required = @(
    'Parametric\bin\parametric.exe',
    'Common Files\protoolkit\includes\ProToolkit.h',
    'Common Files\protoolkit\x86e_win64\obj\ptasyncmd.lib',
    'Common Files\protoolkit\x86e_win64\obj\protkmd_NU.lib',
    'Common Files\protoolkit\x86e_win64\obj\ucore.lib',
    'Common Files\protoolkit\x86e_win64\obj\udata.lib',
    'Common Files\x86e_win64\obj\pro_comm_msg.exe',
    'Common Files\templates\mmns_part_solid_abs.prt',
    'Common Files\templates\mmns_asm_design_abs.asm'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $CreoRoot $relative) -PathType Leaf)) {
        throw "Missing Creo prerequisite: $relative. Install the matching Creo Toolkit SDK and metric templates."
    }
}

$pythonPrefix = @()
if (-not $Python) {
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) { $Python = $launcher.Source; $pythonPrefix = @('-3') }
    else {
        $pythonCommand = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pythonCommand) { $Python = $pythonCommand.Source }
    }
}
if (-not $Python) { throw 'Python not found. Install Python 3.12+ x64, or pass -Python with python.exe.' }
$pythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pythonCommand) { throw 'Python executable not found. Pass -Python with its full path.' }
$Python = $pythonCommand.Source
$pythonInfoText = & $Python @pythonPrefix -c 'import json,struct,sys; print(json.dumps(dict(version=list(sys.version_info[:3]),bits=struct.calcsize(chr(80))*8)))'
if ($LASTEXITCODE -ne 0) { throw 'Cannot run Python. Pass -Python with a working Python 3.12+ x64 executable.' }
$pythonInfo = $pythonInfoText | ConvertFrom-Json
if ($pythonInfo.bits -ne 64 -or $pythonInfo.version[0] -ne 3 -or $pythonInfo.version[1] -lt 12) {
    throw 'Python 3.12+ x64 is required. Pass -Python with a compatible executable.'
}
Write-Output ("Prerequisites found: Python {0}, Creo SDK and MSVC x64." -f ($pythonInfo.version -join '.'))
if ($CheckOnly) { Write-Output 'File checks passed. Toolkit license and the live Creo connection still require runtime verification.'; return }

$localSettings = [ordered]@{}
# Preserve session selection and future local options when reinstalling/upgrading.
foreach ($property in $settings.PSObject.Properties) { $localSettings[$property.Name] = $property.Value }
$localSettings['creo_root'] = $CreoRoot
$localSettings['vcvars64'] = $VcVars64
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$stage = 'local configuration'
$completed = @()
try {
    $localSettings | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
    $completed += $stage
    $stage = 'Python virtual environment'
    & $Python @pythonPrefix -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed.' }
    $completed += $stage
    $stage = 'client configuration'
    $connection = @{ mcpServers = @{ 'MCP_CREO_MechDog' = @{ command = $projectPython; args = @((Join-Path $PSScriptRoot 'server.py')) } } }
    $connection | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'client-config.json') -Encoding UTF8
    $completed += $stage
    $stage = 'Python dependencies'
    & $projectPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet/PyPI access and requirements.lock.txt.' }
    $completed += $stage
    $stage = 'native Blend seed library'
    & $projectPython (Join-Path $PSScriptRoot 'seeds.py') --install
    if ($LASTEXITCODE -ne 0) { throw 'Seed library verification failed. Restore the packaged seed_library, or register the original published library.' }
    $completed += $stage
    $stage = 'SDK constants and native worker'
    & $projectPython (Join-Path $PSScriptRoot 'bridge.py') build
    if ($LASTEXITCODE -ne 0) { throw 'Toolkit worker build failed; inspect build\generate_constants.log and build\build.log.' }
    $completed += $stage
} catch {
    Write-Output ("INSTALL_INCOMPLETE: failed at {0}. Completed: {1}." -f $stage, ($completed -join ', '))
    Write-Output 'Existing models/jobs and local settings are retained. client-config.json, if generated, does not mean the native worker is ready.'
    Write-Output 'Fix the reported prerequisite/network/compiler error and rerun the same setup.ps1 command. No cleanup is required; existing .venv and unchanged native builds are reused.'
    throw
}
Write-Output 'Ready. Open one Creo 10 session and import client-config.json into your local MCP client.'
Write-Output 'Check creo_session_status before modeling; installation alone does not prove Toolkit license availability.'
