$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\extras_batch.log }
Set-Content results\extras_batch_done.flag ""
Log "== extras cluster batch start"
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
$env:INFER_TAG = "9"
Log "START e1-e8"
python -X utf8 analysis\extras_cluster.py *> results\extras_cluster.log
Log "END e1-e8 (exit $LASTEXITCODE)"
"done" | Set-Content results\extras_batch_done.flag
