$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\extras_batch.log }
Set-Content results\extras_batch2_done.flag ""
while (-not ((Get-Content results\extras_batch_done.flag -ErrorAction SilentlyContinue) -match 'done')) { Start-Sleep 60 }
Log "== batch 2 start (scaling, chronos)"
$env:INFER_TAG = "9"
Log "START scaling"
python -X utf8 analysis\extras_scaling.py --trials 3 *> results\extras_scaling.log
Log "END scaling (exit $LASTEXITCODE)"
Log "START chronos"
python -X utf8 analysis\extras_chronos.py *> results\extras_chronos.log
Log "END chronos (exit $LASTEXITCODE)"
python -X utf8 analysis\incident_summary.py *> results\incident_summary.log
python -X utf8 analysis\summarize_extras_cluster.py *> results\summarize_extras_cluster.log
python -X utf8 analysis\build_handoff_pdf.py *> results\handoff_pdf.log
python -X utf8 analysis\build_handoff_pdf.py EXTRAS_AND_FUTURE_WORK.pdf EXTRAS_AND_FUTURE_WORK.md *> results\extras_pdf.log
Log "== batch 2 complete (documents and PDFs updated)"
"done" | Set-Content results\extras_batch2_done.flag
