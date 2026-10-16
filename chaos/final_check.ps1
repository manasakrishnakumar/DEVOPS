$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content results\final_check.log }
Set-Content results\final_check_done.flag ""
$env:INFER_TAG = "9"
$n0 = @(Get-Content results\operator_trials.jsonl).Count
Log "operator live check start (rows before: $n0)"
python -X utf8 chaos\run_operator.py --policies rules --faults corrupt --trials 1 *> results\final_check_operator.log
$all = Get-Content results\operator_trials.jsonl
$all | Select-Object -First $n0 | Set-Content results\operator_trials.jsonl
$all | Select-Object -Skip $n0 | Set-Content results\operator_final_check.jsonl
Log "operator live check done"
$s0 = @(Get-Content results\shadow_gate_cluster.jsonl).Count
python -X utf8 analysis\shadow_gate_cluster.py --trials 1 *> results\final_check_shadow.log
$all = Get-Content results\shadow_gate_cluster.jsonl
$all | Select-Object -First $s0 | Set-Content results\shadow_gate_cluster.jsonl
$all | Select-Object -Skip $s0 | Set-Content results\shadow_gate_final_check.jsonl
Log "shadow gate live check done"
"done" | Set-Content results\final_check_done.flag
