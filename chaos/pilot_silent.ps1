$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
python chaos\run.py --silent --configs C4 E4 --faults corrupt unitchange bitflip --trials 1 *> results\pilot_silent.log
"done" | Set-Content results\pilot_silent.flag
