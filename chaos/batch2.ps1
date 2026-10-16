$env:Path += ";C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube"
Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
python chaos\run.py --configs C --faults corrupt --trials 5 *> results\batch_faults2.log
python chaos\run.py --configs B A --trials 5 *> results\batch_faults3.log
python chaos\run.py --load --configs A B C *> results\batch_load.log
