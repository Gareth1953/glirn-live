Set-Location $PSScriptRoot

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
py -m pytest
