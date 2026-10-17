# Security review (2026-10-17) — lab prototype, not production-ready

Method: manual review of manifests, Dockerfiles and app code (grep for secrets, endpoints, privileges). No penetration test, no image scan.

| # | Finding | Severity | Where | Status / recommendation |
|---|---|---|---|---|
| S1 | Placeholder secrets committed (`SECRET_KEY`, `POSTGRES_PASSWORD=climate_pw`) | High if reused | `k8s/00-base.yaml`, `docker-compose.yml` | Lab values only. Before any real use: create the Secret out-of-band (sealed-secrets/External Secrets), rotate, never commit |
| S2 | `/fault/*` endpoints (crash, corrupt, bitflip...) are unauthenticated and enabled (`FAULT_INJECTION=1`) | High in production | `inference-api/app.py`, ConfigMap | Needed for experiments. Must be `FAULT_INJECTION=0` in any real deployment; endpoints are cluster-internal (ClusterIP, no Ingress) |
| S3 | `/shadow/load`, `/golden/refresh` change served models/reference outputs without auth | Medium | `inference-api/app.py` | Add auth token or NetworkPolicy; golden refresh should only follow a passed shadow gate |
| S4 | No NetworkPolicy; any pod can call inference, Postgres | Medium | `k8s/` | Add default-deny + allow frontend→inference, operator→inference, Prometheus→metrics |
| S5 | Containers run as root, no `securityContext` / read-only root FS | Medium | Dockerfiles, `k8s/` | Add `runAsNonRoot`, drop capabilities, read-only FS where possible |
| S6 | Operator has patch rights on Deployments; RBAC scope not audited | Medium | `operator/deploy.yaml` | Restrict to the one Deployment (`resourceNames`) |
| S7 | Model files (`*.pkl`) are unpickled at start-up: loading an untrusted pickle executes code | High if models come from outside | `inference-api/backends.py` | Models are our own, LFS-tracked; the shadow gate loads candidates from a local dir. Keep model supply chain signed (cosign workflow exists, untested) |
| S8 | Test account password `Test@1234` in chaos scripts | Low | `chaos/probe.py` | Test-only account created by the script on a local cluster |
| S9 | Images not scanned; base image tags not pinned by digest | Medium | Dockerfiles | Run Trivy in CI (not yet run) |
| S10 | App login: Werkzeug password hashing, min length 6, no rate limit/CSRF token | Medium | `frontend/app.py` | Out of scope for the DevOps study; note as limitation |

Not verified here: the GitHub Actions workflow (`.github/workflows/ci.yml`, build + cosign) and the Kyverno image-verify policy (`k8s/policy/kyverno-verify.yaml`) were written but cannot run on this laptop without GitHub/registry; treat them as untested.
