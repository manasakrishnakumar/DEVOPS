$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase4_auto.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase4_done.flag; exit 1 }
Set-Content results\phase4_done.flag ""
Log "== restart: building images with checks"

docker build -q -t climate-inference:3 inference-api | Out-Null
docker image inspect climate-inference:3 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "inference:3 build" }
docker build -q -t climate-operator:1 operator | Out-Null
docker image inspect climate-operator:1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "operator build" }

minikube image load climate-inference:3
minikube image load climate-operator:1
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:3') { Fail "inference:3 not in minikube" }
Log "images built and loaded"

kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null

# set up config D and VERIFY the pod really runs the :3 image with the guard on before measuring anything
kubectl -n climate set image deploy/inference-api inference-api=climate-inference:3 | Out-Null
kubectl -n climate set env deploy/inference-api SEMANTIC_GUARD=1 | Out-Null
kubectl -n climate rollout restart deploy/inference-api | Out-Null   # same tag, rebuilt image
$ok = $false
for ($i = 0; $i -lt 6 -and -not $ok; $i++) {
  Start-Sleep 10
  kubectl -n climate rollout status deploy/inference-api --timeout=120s | Out-Null
  if ($LASTEXITCODE -eq 0) { $ok = $true }
}
if (-not $ok) { Fail "D rollout did not complete" }
Start-Sleep 20
$img = kubectl -n climate get pods -l app=inference-api -o jsonpath='{.items[*].spec.containers[0].image}'
Log "inference pod image(s): $img"
if ($img -notmatch 'climate-inference:3') { Fail "pod not on :3" }

# discard the invalid D rows from the earlier broken attempt (kept in a backup file)
$all = Get-Content results\fault_trials.jsonl
$bad = $all | Where-Object { $_ -match '"config": ?"D"' }
$good = $all | Where-Object { $_ -notmatch '"config": ?"D"' }
if ($bad) { $bad | Set-Content ("results\fault_trials_D_invalid_" + (Get-Date -Format yyyyMMddHHmm) + ".jsonl"); $good | Set-Content results\fault_trials.jsonl }
Log "removed $(@($bad).Count) invalid D rows"

Log "running config D"
python chaos\run.py --configs D --trials 5 *> results\batch_D.log
Log "config D done; twin + bandit"
python analysis\twin_bandit.py *> results\twin_bandit.log
Log "phase 4 complete"
"done" | Set-Content results\phase4_done.flag
