Set-Location $PSScriptRoot\..
$env:INFER_TAG='12'; $env:PYTHONUTF8='1'
python chaos/run.py --silent --configs H4 --faults none corrupt bitflip flatline --trials 5 *> results\deadline_regress.log
'done' | Out-File results\deadline_done.flag
