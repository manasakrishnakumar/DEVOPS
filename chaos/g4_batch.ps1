Set-Location $PSScriptRoot\..
$env:INFER_TAG='10'; $env:PYTHONUTF8='1'
python chaos/run.py --silent --configs G4 --faults bitflip bitflip_severe --trials 10 *> results\g4_pass1.log
python chaos/run.py --silent --configs G4 --faults none corrupt scaler flatline unitchange stale --trials 5 *> results\g4_pass2.log
'done' | Out-File results\g4_done.flag
