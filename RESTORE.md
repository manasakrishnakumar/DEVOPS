# Restore on a new machine
1. Install: Python 3.10, Docker Desktop (WSL2), kubectl, minikube, helm, git + git-lfs.
2. git clone <repo> ; cd devops_project ; git lfs pull   (models are *.pkl / *.h5 via LFS)
3. pip install locust gunicorn psycopg2-binary prometheus-client kopf kubernetes imbalanced-learn pyDOE2 psutil pypdf reportlab tensorflow-cpu==2.15.1
4. Config B:  docker compose up -d --build
5. Config C:  minikube start --driver=docker --cpus=4 --memory=5500
              docker build -t climate-inference:2 inference-api ; docker build -t climate-frontend:2 frontend
              minikube image load climate-inference:2 ; minikube image load climate-frontend:2
              kubectl apply -f k8s/   (see k8s/README.md for Prometheus + Grafana)
6. Experiments: python chaos/run.py --configs C B A --trials 5 ; python chaos/run.py --load --configs A B C
7. Config D:  docker build -t climate-inference:3 inference-api ; minikube image load climate-inference:3 ; python chaos/run.py --configs D --trials 5
8. Analysis:  python analysis/twin_bandit.py ; python chaos/doe.py --config C ; python analysis/bo_probe.py
