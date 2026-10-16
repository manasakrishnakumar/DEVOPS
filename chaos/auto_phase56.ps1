$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\phase56_auto.log }
function Fail($m) { Log "FAILED: $m"; "failed: $m" | Set-Content results\phase56_done.flag; exit 1 }
Set-Content results\phase56_done.flag ""
Log "== pipeline start: build :4 with checks"

docker build -q -t climate-inference:4 inference-api | Out-Null
docker image inspect climate-inference:4 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "inference:4 build" }
minikube image load climate-inference:4
$have = (minikube image ls) -join "`n"
if ($have -notmatch 'climate-inference:4') { Fail "inference:4 not in minikube" }
kubectl -n climate create configmap probe-script --from-file=probe.py=chaos\probe.py --dry-run=client -o yaml | kubectl apply -f - | Out-Null
Log "image :4 built and loaded; probe-script updated"

# keep pilot rows separate from the real run
if (Test-Path results\silentbench.jsonl) { Move-Item results\silentbench.jsonl ("results\silentbench_pilot_" + (Get-Date -Format yyyyMMddHHmm) + ".jsonl") -Force }

Log "pass 1: 5 trials x 8 faults x C4,D4,E4"
python chaos\run.py --silent --configs C4 D4 E4 --trials 5 *> results\silent_pass1.log
Log "pass 1 done (rows: $(@(Get-Content results\silentbench.jsonl -ErrorAction SilentlyContinue).Count))"

Log "healthy soak 10 min per config"
python chaos\run.py --silent --configs C4 D4 E4 --faults none --trials 1 --fault-window 600 --heal-window 10 *> results\silent_soak.log
Log "soak done"

Log "DoE (hang fault, CCD) on C4"
python chaos\doe.py --config C4 --repeats 2 *> results\doe_run.log
Log "DoE done (rows: $(@(Get-Content results\doe.jsonl -ErrorAction SilentlyContinue).Count))"
python analysis\bo_probe.py *> results\bo_probe.log

Log "pass 2: trials 6-10"
python chaos\run.py --silent --configs C4 D4 E4 --trials 5 --trial-offset 5 *> results\silent_pass2.log
Log "pass 2 done"

python analysis\silentbench_summary.py *> results\silentbench_summary.md
python analysis\build_handoff_pdf.py *> results\handoff_pdf.log
Log "pipeline complete"
"done" | Set-Content results\phase56_done.flag
