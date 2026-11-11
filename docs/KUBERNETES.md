# Kubernetes Deployment & Operations Runbook

Production deployment instructions, Helm commands, and operational runbooks for FandomWatch.

---

## 1. Quick Deployment via Helm

### Prerequisites
- Kubernetes cluster v1.26+
- Helm v3.12+
- Ingress-NGINX and Cert-Manager installed

### Step-by-Step Installation
```bash
# 1. Add your registry credentials (if using private image)
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=SriRamKunamsetty \
  --docker-password=<GH_PAT> \
  -n fandomwatch

# 2. Lint the Helm chart
helm lint deploy/helm/fandomwatch

# 3. Deploy the application with custom values
helm upgrade --install fandomwatch deploy/helm/fandomwatch \
  --namespace fandomwatch \
  --create-namespace \
  --set ingress.hosts[0].host=fandom.yourdomain.com \
  --set secrets.DATABASE_URL="postgresql://user:pass@postgres-host:5432/fandom_db" \
  --set secrets.ANTHROPIC_API_KEY="your-api-key"
```

---

## 2. Raw Manifest Deployment (Alternative)

```bash
# 1. Create Namespace & Core Resources
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml
kubectl apply -f deploy/k8s/networkpolicy.yaml

# 2. Deploy Workloads
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/api-service.yaml
kubectl apply -f deploy/k8s/ingress.yaml
kubectl apply -f deploy/k8s/hpa.yaml
kubectl apply -f deploy/k8s/pdb.yaml

# 3. Verify Rollout
kubectl rollout status deployment/fandomwatch-api -n fandomwatch
kubectl get pods -n fandomwatch -o wide
```

---

## 3. Observability & Scaling Runbook

### Horizontal Pod Autoscaling (HPA)
The API pods scale automatically between 2 and 10 replicas based on real-time metrics:
```bash
kubectl get hpa -n fandomwatch
```
- Targets: $70\%$ CPU utilization, $80\%$ Memory utilization.

### Checking Metrics & Probes
```bash
# Forward port for local inspection
kubectl port-forward svc/fandomwatch-api 8000:80 -n fandomwatch

# Inspect health and prometheus metrics
curl http://localhost:8000/healthz
curl http://localhost:8000/metrics | grep fandom_
```

### Incident Triage (Backlash Crisis)
When a `BacklashCriticalIncidentDetected` alert fires in Alertmanager:
1. Identify the affected title in the Prometheus alert label `title`.
2. Generate an instant PR Crisis Briefing via CLI or API:
   ```bash
   kubectl exec -it deploy/fandomwatch-api -n fandomwatch -- fandomwatch crisis-brief --title "<Title Name>"
   ```
3. Check 7-day predictive trajectory:
   ```bash
   kubectl exec -it deploy/fandomwatch-api -n fandomwatch -- fandomwatch forecast --title "<Title Name>"
   ```
4. Query top negative narrative clusters:
   ```bash
   kubectl exec -it deploy/fandomwatch-api -n fandomwatch -- fandomwatch search --title "<Title Name>" "problematic aspect"
   ```
