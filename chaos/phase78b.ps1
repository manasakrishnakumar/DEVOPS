$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube;C:\Users\manas\AppData\Local\Microsoft\WinGet\Packages\Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe\windows-amd64"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase78.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase78_done.flag; exit 1 }
Set-Content results\phase78_done.flag ""
Log "== phase 7/8 restart (image :6 threaded worker; direct burn queries; eval interval 5s)"
docker build -q -t climate-inference:6 inference-api | Out-Null
docker image inspect climate-inference:6 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "inference:6 build" }
minikube image load climate-inference:6
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:6') { Fail "inference:6 not in minikube" }
Log "image :6 built and loaded"
helm upgrade prom prometheus-community/prometheus -n monitoring --reuse-values --set server.global.evaluation_interval=5s -f monitoring\slo-values.yaml 2>&1 | Out-Null
kubectl -n monitoring rollout status deploy/prom-prometheus-server --timeout=240s | Out-Null
Log "prometheus evaluation interval 5s"
$env:INFER_TAG = "6"
if (Test-Path results\slo_replay.jsonl) { Move-Item results\slo_replay.jsonl ("results\slo_replay_invalid_" + (Get-Date -Format yyyyMMddHHmm) + ".jsonl") -Force }
if (Test-Path results\operator_trials.jsonl) { Move-Item results\operator_trials.jsonl ("results\operator_trials_invalid_" + (Get-Date -Format yyyyMMddHHmm) + ".jsonl") -Force }
Log "slo replay"
python analysis\slo_replay.py --configs C4 E4 --trials 3 *> results\slo_replay.log
Log "slo replay done"
Log "operator experiments"
python chaos\run_operator.py --trials 5 *> results\operator_run.log
Log "operator experiments done"
python analysis\twin_bandit.py *> results\twin_bandit_phase8.log
Log "== phase 7/8 complete"
"done" | Set-Content results\phase78_done.flag
