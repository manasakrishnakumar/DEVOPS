# Restore on a new machine (updated 2026-10-17)

1. Install: Python 3.10, Docker Desktop (WSL2), kubectl, minikube, helm, git, git-lfs.
2. Clone: `git clone https://github.com/manasakrishnakumar/DEVOPS.git` then `cd DEVOPS` and `git lfs pull` (models are `*.pkl` / `*.h5`).
3. Python packages: `pip install tensorflow-cpu==2.15.1 pandas scikit-learn statsmodels joblib scipy matplotlib seaborn requests psycopg2-binary prometheus-client kopf kubernetes imbalanced-learn pyDOE2 reportlab pypdf pytest Flask==2.3.3 Werkzeug==2.3.7`.
4. Start the cluster: `minikube start --driver=docker --cpus=4 --memory=5500`.
5. Build and load images (tags matter; see PROJECT_HANDOFF 8.3):
   `docker build -t climate-inference:9 inference-api` ; `docker build -t climate-frontend:3 frontend` ; `docker build -t climate-operator:2 operator` ; `docker build -t climate-monolith:1 monolith`
   `minikube image load climate-inference:9 climate-frontend:3 climate-operator:2`
6. Deploy: `kubectl apply -f k8s/` ; set the final image/env: `kubectl -n climate set image deploy/inference-api inference-api=climate-inference:9` and `kubectl -n climate set env deploy/inference-api SEMANTIC_GUARD=1 GUARD_MODE=envelope+inv FAULT_INJECTION=1` ; `kubectl -n climate set image deploy/frontend frontend=climate-frontend:3`.
7. Monitoring: see `k8s/README.md` (Prometheus + Grafana via helm; dashboard `monitoring/dashboard.json`; rules `monitoring/slo-values.yaml`; set Prometheus `server.global.evaluation_interval=5s`).
8. Operator: `kubectl apply -f operator/deploy.yaml` and `kubectl -n climate create configmap forecast-policy --from-file=policy.json=analysis/policy.json`.
9. Check: `python validation/validate_all.py` (expects the cluster up and results present).
10. Experiments: `chaos/run.py` (faults/load), `chaos/run_operator.py`, `chaos/validate_probe.py`, `analysis/collect_telemetry.py`, `analysis/shadow_gate_cluster.py`, `analysis/phase12_cluster.py`, `chaos/run_family.py`, `analysis/extras_cluster.py` (set `INFER_TAG`).
Windows notes: use `python -X utf8` (training code prints an emoji); `kubectl cp` needs a relative source path; keep the laptop awake and plugged in (Docker stops on sleep); detached PowerShell scripts are used for long runs; avoid killing processes with patterns that match your own command line.
