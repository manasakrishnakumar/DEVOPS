$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube;C:\Users\manas\AppData\Local\Microsoft\WinGet\Packages\Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe\windows-amd64"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase78.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase78_done.flag; exit 1 }
Set-Content results\phase78_done.flag ""
Log "== phase 7/8 start"
docker build -q -t climate-inference:5 inference-api | Out-Null
docker image inspect climate-inference:5 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "inference:5 build" }
docker build -q -t climate-operator:2 operator | Out-Null
docker image inspect climate-operator:2 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "operator:2 build" }
minikube image load climate-inference:5
minikube image load climate-operator:2
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:5' -or $have -notmatch 'climate-operator:2') { Fail "images not in minikube" }
Log "images built and loaded"
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
kubectl -n climate create configmap forecast-policy --from-file=policy.json=analysis\policy.json --dry-run=client -o yaml | kubectl apply -f - | Out-Null
(Get-Content operator\deploy.yaml) -replace 'climate-operator:1','climate-operator:2' | Set-Content operator\deploy.yaml
kubectl apply -f operator\deploy.yaml | Out-Null
kubectl -n climate rollout status deploy/forecast-operator --timeout=180s | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "operator did not start" }
Log "operator deployed"
helm upgrade prom prometheus-community/prometheus -n monitoring --reuse-values -f monitoring\slo-values.yaml 2>&1 | Add-Content results\phase78.log
kubectl -n monitoring rollout status deploy/prom-prometheus-server --timeout=240s | Out-Null
Log "SLO rules applied"
$env:INFER_TAG = "5"
Log "slo replay"
python analysis\slo_replay.py --configs C4 E4 --trials 2 *> results\slo_replay.log
Log "slo replay done"
Log "operator experiments"
python chaos\run_operator.py --trials 5 *> results\operator_run.log
Log "operator experiments done"
python analysis\twin_bandit.py *> results\twin_bandit_phase8.log
Log "== phase 7/8 complete"
"done" | Set-Content results\phase78_done.flag
