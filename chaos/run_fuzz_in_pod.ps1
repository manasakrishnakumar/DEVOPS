# Runs analysis/bitflip_fuzz.py INSIDE a pod of the production inference image (same Python, TensorFlow and model files as the service)
# and copies the result back to results/bitflip_fuzz_in_pod.json.   .\chaos\run_fuzz_in_pod.ps1 [-Trials 100] [-Image climate-inference:14]
param([int]$Trials = 100, [string]$Image = 'climate-inference:14')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
kubectl -n climate delete pod fuzz-in-pod --ignore-not-found --wait=true | Out-Null
kubectl -n climate create configmap fuzz-script --from-file="$root\analysis\bitflip_fuzz.py" --dry-run=client -o yaml | kubectl apply -f - | Out-Null
$spec = @"
apiVersion: v1
kind: Pod
metadata: {name: fuzz-in-pod, namespace: climate}
spec:
  restartPolicy: Never
  containers:
  - name: fuzz
    image: $Image
    imagePullPolicy: Never
    workingDir: /app
    env: [{name: FUZZ_API_DIR, value: /app}]
    command: ["sh", "-c", "mkdir -p /out && python /fuzz/bitflip_fuzz.py --trials $Trials --out /out && touch /out/DONE; sleep 900"]
    volumeMounts: [{name: fuzz, mountPath: /fuzz}]
  volumes: [{name: fuzz, configMap: {name: fuzz-script}}]
"@
$spec | kubectl apply -f - | Out-Null
$ErrorActionPreference = 'Continue'            # kubectl exec writes to stderr while the file does not exist yet
for ($i = 0; $i -lt 360; $i++) {               # up to 60 min
  Start-Sleep 10
  kubectl -n climate exec fuzz-in-pod -- test -f /out/DONE 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { break }
}
if ($LASTEXITCODE) { throw 'fuzz in pod did not finish' }
Push-Location "$root\results"                  # kubectl cp mis-reads "C:\..." as pod:path, so copy to a relative name
kubectl -n climate cp fuzz-in-pod:/out/bitflip_fuzz.json bitflip_fuzz_in_pod.json 2>&1 | Out-Null
Pop-Location
kubectl -n climate delete pod fuzz-in-pod --wait=false | Out-Null
"copied results\bitflip_fuzz_in_pod.json"
