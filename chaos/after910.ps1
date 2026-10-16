$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase910.log }
while (-not ((Get-Content results\phase910_done.flag -ErrorAction SilentlyContinue) -match 'done|failed')) { Start-Sleep 60 }
Log "[after910] phase 9/10 finished -> running probe-validation controls"
$env:INFER_TAG = "4"
python chaos\validate_probe_control.py *> results\probe_validation_control.log
Log "[after910] controls done"
python analysis\summarize_phase9_10.py *> results\summarize_phase9_10.log
python analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "[after910] documents and PDF updated"
