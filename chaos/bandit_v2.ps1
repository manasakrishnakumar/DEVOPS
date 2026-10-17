Set-Location $PSScriptRoot\..
$env:INFER_TAG='5'; $env:PYTHONUTF8='1'
Start-Sleep 90
python chaos/run_operator.py --policies bandit --trials 5 *> results\bandit_v2.log
'done' | Out-File results\bandit_v2_done.flag
