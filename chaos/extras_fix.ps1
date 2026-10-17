$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\extras_batch.log }
Set-Content results\extras_fix_done.flag ""
$env:INFER_TAG = "9"
Log "== fix run start (e8 with guard on, heavier scaling burst)"
python -X utf8 analysis\extras_cluster.py --only e8 *> results\extras_fix_e8.log
Log "END e8 rerun (exit $LASTEXITCODE)"
python -X utf8 analysis\extras_scaling.py --trials 3 *> results\extras_scaling.log
Log "END scaling rerun (exit $LASTEXITCODE)"
python -X utf8 analysis\summarize_extras_cluster.py *> results\summarize_extras_cluster.log
python -X utf8 analysis\build_handoff_pdf.py *> results\handoff_pdf.log
python -X utf8 analysis\build_handoff_pdf.py EXTRAS_AND_FUTURE_WORK.pdf EXTRAS_AND_FUTURE_WORK.md *> results\extras_pdf.log
Log "== fix run complete"
"done" | Set-Content results\extras_fix_done.flag
