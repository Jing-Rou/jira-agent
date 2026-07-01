# Docker and Kubernetes Guide for Jira Agent

This project has two apps:

- `backend`: Django REST API on port `8000`
- `frontend`: React app served by Nginx on port `80` inside the container

## Beginner Concepts

### Docker
Docker packages your app plus its runtime into an image.

- `Dockerfile`: recipe for building an image
- `image`: packaged app template
- `container`: running copy of an image
- `docker compose`: runs multiple containers together, such as frontend + backend

In this project:

- `docker/backend.Dockerfile` builds the Django API image
- `docker/frontend.Dockerfile` builds the React app and serves it with Nginx
- `docker-compose.yml` runs both containers locally

### Kubernetes
Kubernetes runs containers in a cluster.

- `Pod`: smallest running unit, usually one app container
- `Deployment`: keeps Pods running and restarts them if they crash
- `Service`: stable network name for Pods
- `ConfigMap`: non-secret configuration
- `Secret`: sensitive values such as Jira API token
- `Probe`: health check Kubernetes uses to know if a Pod is ready/alive

In this project:

- `k8s/backend-deployment.yaml` runs Django
- `k8s/frontend-deployment.yaml` runs Nginx + React
- `k8s/backend-service.yaml` lets frontend reach backend as `http://backend:8000`
- `k8s/frontend-service.yaml` exposes the frontend on NodePort `30080`

## Run Locally with Docker Compose

From the project root:

```powershell
cd C:\Users\User\Documents\JR\LLM\Jira-Agent
docker compose up --build
```

Open:

```text
http://127.0.0.1:5173
```

The frontend container proxies `/triage/` requests to the backend container.

If Ollama runs on your Windows host, Docker containers should use:

```text
LLM_BASE_URL=http://host.docker.internal:11434
```

That is already set in `docker-compose.yml`.

## Build Images Manually

```powershell
docker build -t jira-agent-backend:local -f docker/backend.Dockerfile .
docker build -t jira-agent-frontend:local -f docker/frontend.Dockerfile .
```

## Run in Kubernetes

First build images:

```powershell
docker build -t jira-agent-backend:local -f docker/backend.Dockerfile .
docker build -t jira-agent-frontend:local -f docker/frontend.Dockerfile .
```

If you use Docker Desktop Kubernetes, local images may be available directly. If you use Minikube, build inside Minikube instead:

```powershell
minikube image build -t jira-agent-backend:local -f docker/backend.Dockerfile .
minikube image build -t jira-agent-frontend:local -f docker/frontend.Dockerfile .
```

Create a real secret file from the example:

```powershell
Copy-Item k8s\secret.example.yaml k8s\secret.yaml
```

Edit `k8s/secret.yaml` and put your real values. Do not commit it.

Then update `k8s/kustomization.yaml` to use:

```yaml
- secret.yaml
```

instead of:

```yaml
- secret.example.yaml
```

Apply manifests:

```powershell
kubectl apply -k k8s
```

Check status:

```powershell
kubectl get pods
kubectl get services
```

Open frontend:

```text
http://localhost:30080
```

## Important Notes

This setup uses SQLite for learning. In real production, use PostgreSQL and a PersistentVolume.

Never put real Jira API tokens in Git. Use Kubernetes Secrets or a secret manager.

For Kubernetes, Ollama must be reachable from inside the cluster. You can deploy Ollama in the cluster or point `LLM_BASE_URL` to a reachable model gateway.