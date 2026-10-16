$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase56_auto.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase56_done.flag; exit 1 }
Set-Content results\phase56_done.flag ""
Log "== part B start (after pass 1 + validation)"
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:4') { Fail "inference:4 missing in minikube" }

Log "phase 7/8 (SLO + operator) first"
powershell -NoProfile -ExecutionPolicy Bypass -File chaos\phase78.ps1
Log "phase 7/8 finished (see results\phase78.log)"

Log "healthy soak 10 min per config"
python chaos\run.py --silent --configs C4 D4 E4 --faults none --trials 1 --fault-window 600 --heal-window 10 *> results\silent_soak.log
Log "soak done"

Log "DoE (hang fault, CCD) on C4"
python chaos\doe.py --config C4 --repeats 2 *> results\doe_run.log
Log "DoE done (rows: $(@(Get-Content results\doe.jsonl -ErrorAction SilentlyContinue).Count))"
python analysis\bo_probe.py *> results\bo_probe.log

Log "pass 2: trials 6-10"
python chaos\run.py --silent --configs C4 D4 E4 --trials 5 --trial-offset 5 *> results\silent_pass2.log
Log "pass 2 done"

python analysis\silentbench_summary.py *> results\silentbench_summary.md
python analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "pipeline complete"
"done" | Set-Content results\phase56_done.flag
