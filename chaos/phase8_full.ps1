$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase8.log }
Set-Content results\phase8_done.flag ""
Log "== phase 8 full run start"
if (Test-Path results\operator_trials.jsonl) { Move-Item results\operator_trials.jsonl results\operator_sanity_trial.jsonl -Force }
$env:INFER_TAG = "6"
python chaos\run_operator.py --trials 5 *> results\operator_run.log
Log "operator experiments done"
python analysis\twin_bandit.py *> results\twin_bandit_phase8.log
Log "twin re-run done"
python analysis\summarize_phase8.py *> results\summarize_phase8.log
python analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "== phase 8 complete (documents and PDF updated)"
"done" | Set-Content results\phase8_done.flag
