$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
$env:INFER_TAG = "6"
"$(Get-Date -Format s) [short] E4 replay (2 trials) start" | Add-Content results\phase78.log
python analysis\slo_replay.py --configs E4 --trials 2 *> results\slo_replay_e4.log
"$(Get-Date -Format s) [short] E4 replay done" | Add-Content results\phase78.log
"stopped-by-user-deadline" | Set-Content results\phase78_done.flag
