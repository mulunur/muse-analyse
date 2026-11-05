# Muse Analyse Kubernetes manifests

Practical manifests for the project. **They have not been run in a real cluster.** All we have checked is that Kustomize builds them, that the result passes validation against the Kubernetes 1.31 schemas (`kubeconform`), and that the patches apply as intended. Everything else is reasoning from the code and from measurements, and is marked as such below.

## What is here

```
k8s/
  base/                  everything the app needs (without RAG)
    namespace.yaml         the muse-analyse Namespace
    configmap.yaml         ordinary settings (≈ environment: in compose)
    secret.example.yaml    a SAMPLE secret with keys; not part of the build
    pvc.yaml               volumes: uploads, growth-state, redis-data
    redis.yaml             Deployment + Service
    web.yaml               Deployment + Service (FastAPI/uvicorn)
    worker.yaml            Deployment (Celery)
  overlays/
    k3s/                   the base + an Ingress for Traefik
    local-rag/             the base + RAG, for kind/minikube
  components/rag/          the "RAG option": the :rag image, index volumes, an indexing Job
```

How it maps to `docker-compose.yml`:

| compose | Kubernetes |
|---|---|
| the `muse-analyse` service | `Deployment web` + `Service web` |
| the `worker` service | `Deployment worker` |
| the `redis` service | `Deployment redis` + `Service redis` |
| `.env`, `environment:` | `ConfigMap muse-config` + `Secret muse-secrets` |
| the `growth_state`, `redis_data` and `uploads` volumes | `PersistentVolumeClaim` |
| the `rag` profile | `components/rag` |
| `compose run … index_knowledge.py` | `Job index-knowledge` |

## Are the manifests the same for kind, minikube and k3s?

Yes. Deployment, Service, ConfigMap and PVC are the standard Kubernetes API, and it is the same everywhere. What differs is everything around the manifests:

| | kind | minikube | k3s |
|---|---|---|---|
| What it is | a cluster inside Docker containers, for development | a local cluster (VM/Docker); according to its docs, "for learning and development" | a lightweight cluster that is fine for production |
| Getting the image into the cluster | `kind load docker-image muse-analyse:local` | `minikube image load muse-analyse:local` | `docker save muse-analyse:local \| sudo k3s ctr images import -`, or a registry |
| Reaching the app | `kubectl port-forward` (there is no Ingress controller) | `port-forward`, `minikube service`, or the `ingress` addon | Traefik out of the box → `overlays/k3s` |
| Disk (StorageClass) | a "default" one exists | a "default" one exists | a "default" one exists (local-path) |
| Minimum, per its docs | your Docker's resources | 2 CPUs, 2 GB of free memory, 20 GB of disk | server: 2 cores, 2 GB RAM |

`storageClassName` is deliberately left out of `pvc.yaml`, so the default class is used (as far as I know all three have one; I have not checked). That is what keeps the manifests portable.

## Running it

The order is the same in every case: image → namespace → secret → apply.

### kind (or minikube) on your own computer

```bash
# 1. The image (the runtime target, as in docker-compose.yml)
docker build --target runtime -t muse-analyse:local .

# 2. The cluster, and loading the image into it
kind create cluster --name muse
kind load docker-image muse-analyse:local --name muse
#   minikube:  minikube start --cpus=2 --memory=4096 && minikube image load muse-analyse:local

# 3. The namespace, and a secret (keys are optional; without them you get the template review)
kubectl apply -f k8s/base/namespace.yaml
kubectl -n muse-analyse create secret generic muse-secrets \
  --from-literal=LLM_PROVIDER=claude \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-...

# 4. Apply it and wait
kubectl apply -k k8s/base
kubectl -n muse-analyse get pods -w

# 5. Open http://localhost:8000
kubectl -n muse-analyse port-forward svc/web 8000:8000
```

With RAG: build `docker build --target rag -t muse-analyse:rag .`, load **that** image into the cluster, and apply `kubectl apply -k k8s/overlays/local-rag`. To follow the indexing: `kubectl -n muse-analyse logs job/index-knowledge -f`.

### k3s on a server

```bash
curl -sfL https://get.k3s.io | sh -               # installs k3s (needs root)
docker save muse-analyse:local | sudo k3s ctr images import -   # an image built elsewhere
sudo k3s kubectl apply -f k8s/base/namespace.yaml
sudo k3s kubectl -n muse-analyse create secret generic muse-secrets --from-literal=...
sudo k3s kubectl apply -k k8s/overlays/k3s
```

You need port 80 open (Traefik) and, if you connect from another machine, port 6443 (the Kubernetes API). None of this has been tested.

## Secrets and LLM keys

Keys go through a `Secret` only (see `base/secret.example.yaml`). Do not put them in the ConfigMap, and do not commit a file with real values. After creating or changing the secret, the pods need a restart:

```bash
kubectl -n muse-analyse rollout restart deployment/web deployment/worker
```

## Resources: will it fit on a small server?

Memory requests (`requests`) in the base: web 256 MiB + worker 512 MiB + redis 32 MiB ≈ **0.8 GiB**, and about 2 GiB with RAG (measured on macOS: the worker after its first RAG request takes ~1.37 GB). Kubernetes itself comes on top of that:

- **k3s**: per its docs, the minimum for a server is 2 cores and 2 GB of RAM. In their test (which ran Prometheus and Grafana, so the figure is too high for us) the server used 1.4-1.6 GB.
- **minikube**: per its docs, the minimum is 2 CPUs and 2 GB of free memory *for the cluster itself*, and it is built for development, not for servers.

The conclusion (an estimate): without RAG you need a machine with 4 GB or more, and with RAG 6 GB or more. On a server with 1 vCPU and 1-2 GB, neither minikube nor k3s will fit this app next to its workload; `docker compose` is what stays there.

## Scaling workers by queue length (a sketch, not tested)

CPU is a poor metric for a worker; the load shows up as the length of the queue in Redis. For that you need [KEDA](https://keda.sh) (installed into the cluster separately):

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker
  namespace: muse-analyse
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 1
  maxReplicaCount: 3
  triggers:
    - type: redis
      metadata:
        address: redis.muse-analyse.svc.cluster.local:6379
        listName: celery        # Celery's default queue
        listLength: "2"
        databaseIndex: "0"
```

## What probes are

A probe is a periodic check that Kubernetes itself runs against a container (a "pulse"). There are three kinds:

| Probe | The question | If it fails |
|---|---|---|
| `startupProbe` | "Has it started yet?" (the other probes do not run until this one passes) | the container is restarted if it did not make it in the allotted time |
| `readinessProbe` | "Is it ready to take requests?" | the pod is removed from the `Service`, so no traffic reaches it, but it is **not restarted** |
| `livenessProbe` | "Is it alive, or hung?" | the container is **restarted** |

A check can be done in three ways: `httpGet` (a GET to a path; a 2xx/3xx answer is a success), `tcpSocket` (the port is open) and `exec` (a command inside the container; exit code 0 is a success). In our setup: `web` uses `httpGet /healthz`, `redis` uses `exec redis-cli ping`, and `worker` has no probes (the reason is in a comment in `worker.yaml`).

The compose equivalent is `HEALTHCHECK` in the Dockerfile. But in plain Docker/compose an unhealthy container is only marked as unhealthy, while Kubernetes also acts on it: it restarts the container or stops sending it traffic.

`/healthz` deliberately does not ask Ollama, RAG or Redis anything: a liveness probe should only answer "the process is alive". If it depended on an outside service, that service's failure would restart a perfectly healthy web pod.

## Known limitations

1. **It has not been run in a cluster.** All that was checked is the Kustomize build, the Kubernetes schemas, the `/healthz` tests and measurements of how fast the endpoints answer (see item 5).
2. **The image is `linux/amd64` only** (that is how the Dockerfile is written; the Essentia wheel is x86). On Apple Silicon, pods in kind/minikube run through emulation and are slow; I have not checked how that behaves overall. There is deliberately no `nodeSelector` for the architecture: on an arm node the pods would become unschedulable.
3. **Volume permissions.** The app does not run as root (uid 10001), so the pods set `runAsUser` and `fsGroup`. For local disk providers (kind/minikube/k3s) this works, as far as I know, but it has not been tested.
4. **LLM settings from the web form do not reach the worker.** This is a bug in the app itself, and it exists in compose too: the form changes settings in the web process's memory, but the worker builds the review. In a cluster, set the keys through a Secret.
5. **`/api/health` calls Ollama synchronously inside an `async` handler.** The probes use a separate lightweight `/healthz` (added in `app/main.py`), but `/api/health` itself is still a problem. We measured it with a "silent" Ollama: it answers in 2.0 s, and a parallel `/healthz` answered in 1.7 s instead of 0.6 ms, so a single call freezes the whole web process. The frontend calls `/api/health` when the page loads. The `HEALTHCHECK` in the Dockerfile also still hits `/api/health`. The fix is to run the provider checks in a thread (`asyncio.to_thread`); it has not been fixed in the app.
6. **Worker memory grows with the length of the track** (≈0.7 MB per second of audio). With a 1 GiB limit, a track of 15+ minutes will end in `OOMKilled`. Raise the limit, or cap the duration in the app.
7. **One node.** Growth Copilot's SQLite state and the RWO volumes need web, worker and the Job to live on the same node; with several nodes you would need PostgreSQL.
8. **The index-knowledge Job cannot be "updated".** Delete it before applying again (`kubectl -n muse-analyse delete job index-knowledge`).

## Useful commands

```bash
kubectl -n muse-analyse get pods,pvc,svc          # what is running
kubectl -n muse-analyse describe pod <name>       # the reason, if a pod will not start / OOMKilled
kubectl -n muse-analyse logs deploy/worker -f     # the worker's logs
kubectl -n muse-analyse top pod                   # resource usage (needs metrics-server)
kubectl kustomize k8s/base                        # show the final YAML without applying anything
kubectl delete namespace muse-analyse             # tear everything down, INCLUDING volumes and their data
```
