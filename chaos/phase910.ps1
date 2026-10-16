$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase910.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase910_done.flag; exit 1 }
Set-Content results\phase910_done.flag ""
Log "== waiting for phase 8"
while (-not ((Get-Content results\phase8_done.flag -ErrorAction SilentlyContinue) -match 'done')) { Start-Sleep 60 }
Log "phase 8 finished -> starting phase 9/10"

docker build -q -t climate-inference:7 inference-api | Out-Null
docker image inspect climate-inference:7 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "inference:7 build" }
minikube image load climate-inference:7
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:7') { Fail "inference:7 not in minikube" }
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
Log "image :7 built and loaded"

Log "phase 9: validating tuned probe settings (image :4, config C4)"
$env:INFER_TAG = "4"
python chaos\validate_probe.py --trials 5 *> results\probe_validation.log
Log "phase 9 validation done"

Log "phase 10: telemetry smoke test (image :7, config E4)"
$env:INFER_TAG = "7"
python analysis\collect_telemetry.py --smoke *> results\telemetry_smoke.log
if ($LASTEXITCODE -ne 0) { Fail "telemetry smoke test failed (see results\telemetry_smoke.log)" }
Log "smoke ok -> collecting telemetry"
python analysis\collect_telemetry.py --plan healthy:2:480 leak:6:200 drift:6:170 *> results\telemetry_collect.log
Log "telemetry collected"
python analysis\failure_predictor.py *> results\predictor.log
python analysis\summarize_phase9_10.py *> results\summarize_phase9_10.log
python analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "== phase 9/10 complete (documents and PDF updated)"
"done" | Set-Content results\phase910_done.flag
