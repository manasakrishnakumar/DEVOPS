Set-Location $PSScriptRoot\..
$env:INFER_TAG='12'; $env:PYTHONUTF8='1'
python analysis/extras_deadline.py --trials 3 *> results\deadline_burst.log
python chaos/run.py --silent --configs G4 H4 --faults delay --trials 10 *> results\deadline_delay.log
python chaos/run.py --silent --configs H4 --faults none corrupt bitflip flatline --trials 5 *> results\deadline_regress.log
'done' | Out-File results\deadline_done.flag
