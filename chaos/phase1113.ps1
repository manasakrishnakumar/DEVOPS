$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase1113.log }
function Step($name, $cmd) { Log "START $name"; Invoke-Expression $cmd; Log "END $name (exit $LASTEXITCODE)" }
Set-Content results\phase1113_done.flag ""
Log "== phase 11-13 start"
Step "adaptive conformal (offline)" 'python -X utf8 analysis\adaptive_conformal.py *> results\adaptive_conformal.log'
Step "make candidates (host, TF)" 'python -X utf8 analysis\make_candidates.py *> results\make_candidates.log'

docker build -q -t climate-inference:8 inference-api | Out-Null
docker image inspect climate-inference:8 | Out-Null
if ($LASTEXITCODE -ne 0) { Log "FAILED: inference:8 build"; "failed: build" | Set-Content results\phase1113_done.flag; exit 1 }
minikube image load climate-inference:8
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:8') { Log "FAILED: image :8 not in minikube"; "failed: image" | Set-Content results\phase1113_done.flag; exit 1 }
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
Log "image :8 built and loaded"
$env:INFER_TAG = "8"

Step "phase 11 shadow gate in cluster" 'python -X utf8 analysis\shadow_gate_cluster.py --trials 3 *> results\shadow_gate_cluster.log'
Step "phase 12 cluster" 'python -X utf8 analysis\phase12_cluster.py *> results\phase12.log'
Step "phase 13b model family" 'python -X utf8 chaos\run_family.py --trials 5 *> results\model_family.log'
Step "summarize" 'python -X utf8 analysis\summarize_phase11_13.py *> results\summarize_phase11_13.log'
python -X utf8 analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "== phase 11-13 complete (documents and PDF updated)"
"done" | Set-Content results\phase1113_done.flag

