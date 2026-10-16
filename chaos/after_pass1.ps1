$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase56_auto.log }
Log "[after_pass1] waiting for pass 1 to finish"
while (-not (Select-String -Path results\phase56_auto.log -Pattern 'pass 1 done' -Quiet)) { Start-Sleep 30 }
Log "[after_pass1] pass 1 done -> stopping pipeline for validation"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'auto_phase56\.ps1|chaos\\run\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 15
kubectl -n climate rollout status deploy/inference-api --timeout=300s | Out-Null
Start-Sleep 20
python analysis\silentbench_summary.py *> results\silentbench_summary_pass1.md
Log "[after_pass1] running validation suite"
python validation\validate_all.py *> results\validation_run.log
Log "[after_pass1] validation finished (see results\validation_report.md); resuming part B"
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project\chaos\auto_phase56b.ps1' -WindowStyle Hidden
