# Phase 2: Kubernetes baseline (config C)
minikube start --driver=docker --cpus=4 --memory=5500
minikube image load climate-inference:1 ; minikube image load climate-frontend:2
kubectl apply -f k8s/
helm upgrade --install prom prometheus-community/prometheus -n monitoring --set alertmanager.enabled=false --set prometheus-pushgateway.enabled=false --set prometheus-node-exporter.enabled=false --set server.persistentVolume.enabled=false --set server.global.scrape_interval=5s --set server.global.scrape_timeout=4s
kubectl -n monitoring create configmap climate-dashboard --from-file=climate.json=monitoring/dashboard.json
helm upgrade --install grafana grafana/grafana -n monitoring -f monitoring/grafana-values.yaml
kubectl -n monitoring port-forward svc/grafana 3000:80   # admin/admin
kubectl -n climate port-forward svc/frontend 5000:5000

## Signed golden outputs and admission policy (2026-10-22)
```bash
# release machine (key outside the repo):  $env:COSIGN_PASSWORD='...'
./chaos/release_signed_golden.ps1 -Publish          # golden.json + cosign bundle + public key -> ConfigMap signed-golden
kubectl apply -f k8s/12-signed-golden-patch.yaml    # SIGNED_GOLDEN_DIR=/golden and the volume mount
kubectl apply -f k8s/policy/vap-require-signed-golden.yaml   # Kubernetes 1.30+: forbids removing the wiring
python chaos/test_admission_policy.py               # six server-side dry-run cases
```