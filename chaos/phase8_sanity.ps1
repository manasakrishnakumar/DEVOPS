$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase8.log }
Log "== phase 8 sanity start"
for ($i = 0; $i -lt 40; $i++) {
  $p = kubectl -n climate get pods --no-headers 2>$null
  if ((@($p | Where-Object { $_ -match '^(frontend|postgres)\S*\s+1/1\s+Running' })).Count -ge 2) { break }
  Start-Sleep 10
}
kubectl apply -f operator\deploy.yaml | Out-Null
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
kubectl -n climate create configmap forecast-policy --from-file=policy.json=analysis\policy.json --dry-run=client -o yaml | kubectl apply -f - | Out-Null
$env:INFER_TAG = "6"
python chaos\run_operator.py --policies rules --faults corrupt --trials 1 --window 150 *> results\operator_sanity.log
Log "sanity done"
"done" | Set-Content results\phase8_sanity.flag
