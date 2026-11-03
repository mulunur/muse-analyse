# Kubernetes-манифесты Muse Analyse

Практические манифесты. **В реальном кластере они не запускались**: проверено
только, что Kustomize их собирает, что результат проходит валидацию схем
Kubernetes 1.31 (`kubeconform`) и что патчи применяются как задумано.
Всё остальное — рассуждения по коду и замерам, помечено ниже.

## Что здесь

```
k8s/
  base/                  всё, что нужно приложению (без RAG)
    namespace.yaml         Namespace muse-analyse
    configmap.yaml         обычные настройки (≈ environment: в compose)
    secret.example.yaml    ОБРАЗЕЦ секрета с ключами — в сборку не входит
    pvc.yaml               тома: uploads, growth-state, redis-data
    redis.yaml             Deployment + Service
    web.yaml               Deployment + Service (FastAPI/uvicorn)
    worker.yaml            Deployment (Celery)
  overlays/
    k3s/                   база + Ingress для Traefik
    local-rag/             база + RAG, для kind/minikube
  components/rag/          «опция RAG»: образ :rag, тома индекса, Job индексации
```

Соответствие `docker-compose.yml`:

| compose | Kubernetes |
|---|---|
| сервис `muse-analyse` | `Deployment web` + `Service web` |
| сервис `worker` | `Deployment worker` |
| сервис `redis` | `Deployment redis` + `Service redis` |
| `.env`, `environment:` | `ConfigMap muse-config` + `Secret muse-secrets` |
| тома `growth_state`, `redis_data`, `uploads` | `PersistentVolumeClaim` |
| профиль `rag` | `components/rag` |
| `compose run … index_knowledge.py` | `Job index-knowledge` |

## Одни и те же манифесты для kind, minikube и k3s?

Да. Deployment, Service, ConfigMap и PVC — это стандартный API Kubernetes, и он
одинаков везде. Различается то, что вокруг манифестов:

| | kind | minikube | k3s |
|---|---|---|---|
| Что это | кластер внутри Docker-контейнеров, для разработки | локальный кластер (VM/Docker); по документации — «для обучения и разработки» | лёгкий кластер, годится для production |
| Как попасть образу в кластер | `kind load docker-image muse-analyse:local` | `minikube image load muse-analyse:local` | `docker save muse-analyse:local \| sudo k3s ctr images import -` или реестр |
| Как открыть приложение | `kubectl port-forward` (Ingress-контроллера нет) | `port-forward`, `minikube service` или аддон `ingress` | Traefik из коробки → `overlays/k3s` |
| Диск (StorageClass) | есть «по умолчанию» | есть «по умолчанию» | есть «по умолчанию» (local-path) |
| Минимум по документации | ресурсы вашего Docker | 2 CPU, 2 ГБ свободной памяти, 20 ГБ диска | сервер: 2 ядра, 2 ГБ RAM |

`storageClassName` в `pvc.yaml` не указан специально — берётся класс по умолчанию
(насколько я знаю, он есть во всех трёх; не проверял), поэтому манифесты переносимы.

## Запуск

Во всех вариантах порядок один: образ → namespace → секрет → применить.

### kind (или minikube) на вашем компьютере

```bash
# 1. Образ (target runtime — как в docker-compose.yml)
docker build --target runtime -t muse-analyse:local .

# 2. Кластер и загрузка образа
kind create cluster --name muse
kind load docker-image muse-analyse:local --name muse
#   minikube:  minikube start --cpus=2 --memory=4096 && minikube image load muse-analyse:local

# 3. Namespace, секрет (ключи — по желанию, без них будет шаблонный обзор)
kubectl apply -f k8s/base/namespace.yaml
kubectl -n muse-analyse create secret generic muse-secrets \
  --from-literal=LLM_PROVIDER=claude \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-...

# 4. Применить и дождаться
kubectl apply -k k8s/base
kubectl -n muse-analyse get pods -w

# 5. Открыть http://localhost:8000
kubectl -n muse-analyse port-forward svc/web 8000:8000
```

С RAG: соберите `docker build --target rag -t muse-analyse:rag .`, загрузите **этот**
образ в кластер и применяйте `kubectl apply -k k8s/overlays/local-rag`.
Ход индексации: `kubectl -n muse-analyse logs job/index-knowledge -f`.

### k3s на сервере

```bash
curl -sfL https://get.k3s.io | sh -               # ставит k3s (нужен root)
docker save muse-analyse:local | sudo k3s ctr images import -   # образ, собранный в другом месте
sudo k3s kubectl apply -f k8s/base/namespace.yaml
sudo k3s kubectl -n muse-analyse create secret generic muse-secrets --from-literal=...
sudo k3s kubectl apply -k k8s/overlays/k3s
```

Нужен открытый порт 80 (Traefik) и, если ходите с другой машины, 6443 (API
Kubernetes). Всё это не проверялось.

## Секреты и ключи LLM

Ключи — только через `Secret` (см. `base/secret.example.yaml`). Не кладите их в
ConfigMap и не коммитьте файл с настоящими значениями. После создания или
изменения секрета поды нужно перезапустить:

```bash
kubectl -n muse-analyse rollout restart deployment/web deployment/worker
```

## Ресурсы: влезет ли на маленький сервер

Запросы памяти (`requests`) в базе: web 256 МиБ + worker 512 МиБ + redis 32 МиБ ≈ **0,8 ГиБ**,
с RAG ≈ 2 ГиБ (замер на macOS: воркер после первого RAG-запроса ~1,37 ГБ).
Сам Kubernetes сверху:

- **k3s**: по документации минимум для сервера — 2 ядра и 2 ГБ RAM; в их тесте
  (с Prometheus и Grafana, поэтому цифра завышена для нас) сервер занимал 1,4–1,6 ГБ.
- **minikube**: по документации минимум 2 CPU и 2 ГБ свободной памяти *на сам
  кластер*, плюс он создан для разработки, а не для сервера.

Вывод (оценка): без RAG нужна машина от 4 ГБ, с RAG — от 6 ГБ. На сервере с
1 vCPU / 1–2 ГБ ни minikube, ни k3s с этим приложением не поместятся — там
остаётся `docker compose`.

## Масштабирование воркеров по очереди (набросок, не проверялось)

CPU — плохая метрика для воркера, нагрузку показывает длина очереди в Redis.
Для этого нужен [KEDA](https://keda.sh) (ставится в кластер отдельно):

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
        listName: celery        # очередь Celery по умолчанию
        listLength: "2"
        databaseIndex: "0"
```

## Что такое пробы (probes)

Проба — периодическая проверка, которую Kubernetes сам делает контейнеру
(«пульс»). Бывает три вида:

| Проба | Вопрос | Если не прошла |
|---|---|---|
| `startupProbe` | «Уже запустился?» (пока она не прошла, остальные не работают) | контейнер перезапускается, если не успел за отведённое время |
| `readinessProbe` | «Готов принимать запросы?» | под исключается из `Service` — трафик на него не идёт, но он **не перезапускается** |
| `livenessProbe` | «Жив, не завис?» | контейнер **перезапускается** |

Проверять можно тремя способами: `httpGet` (GET на путь, ответ 2xx/3xx — успех),
`tcpSocket` (порт открыт) и `exec` (команда внутри контейнера, код 0 — успех).
У нас: `web` — `httpGet /healthz`, `redis` — `exec redis-cli ping`, у `worker`
проб нет (причина — в комментарии в `worker.yaml`).

Аналог в compose — `HEALTHCHECK` в Dockerfile, но в обычном Docker/compose
нездоровый контейнер лишь помечается как unhealthy, а Kubernetes ещё и действует:
перезапускает или перестаёт слать трафик.

`/healthz` намеренно не опрашивает Ollama, RAG и Redis: liveness-проба должна
отвечать только «процесс жив». Если бы она зависела от внешнего сервиса, его
сбой перезапускал бы совершенно здоровый веб-под.

## Известные ограничения

1. **Не запускалось в кластере.** Проверены только сборка Kustomize, схемы
   Kubernetes, тесты `/healthz` и замеры ответа эндпоинтов (см. п. 5).
2. **Образ только `linux/amd64`** (так в Dockerfile; wheel Essentia — x86). На
   Apple Silicon поды в kind/minikube идут через эмуляцию — медленно; как это
   поведёт себя в целом, не проверял. `nodeSelector` на архитектуру не задан
   специально — на arm-узле поды стали бы неразмещаемыми.
3. **Права на тома.** Приложение работает не от root (uid 10001), поэтому в
   подах заданы `runAsUser` и `fsGroup`. Для локальных провайдеров дисков
   (kind/minikube/k3s) это, по моим сведениям, работает, но не проверялось.
4. **Настройки LLM из веб-формы не доходят до воркера** (баг в самом
   приложении, в compose он тоже есть): форма меняет настройки в памяти
   веб-процесса, а обзор строит воркер. В кластере ключи задавайте через Secret.
5. **`/api/health` синхронно ходит в Ollama внутри `async`-обработчика.** Пробы
   используют отдельный лёгкий `/healthz` (добавлен в `app/main.py`), но сам
   `/api/health` остаётся проблемным: замер при «молчащей» Ollama — он отвечает
   за 2,0 с, а параллельный `/healthz` в это время ответил за 1,7 с вместо
   0,6 мс, то есть единственный вызов замораживает весь веб-процесс. Фронтенд
   вызывает `/api/health` при загрузке страницы. `HEALTHCHECK` в Dockerfile тоже
   всё ещё бьёт в `/api/health`. Лечится запуском проверок провайдеров в потоке
   (`asyncio.to_thread`) — в приложении не исправлено.
6. **Память воркера растёт с длиной трека** (≈0,7 МБ на секунду аудио). При
   лимите 1 ГиБ трек ~15+ минут приведёт к `OOMKilled`. Поднимите лимит или
   ограничьте длительность в приложении.
7. **Один узел.** SQLite-состояние Growth Copilot и тома RWO требуют, чтобы web,
   worker и Job жили на одном узле; для нескольких узлов нужен PostgreSQL.
8. **Job index-knowledge нельзя «обновить»**: перед повторным `apply` удалите его
   (`kubectl -n muse-analyse delete job index-knowledge`).

## Полезные команды

```bash
kubectl -n muse-analyse get pods,pvc,svc          # что запущено
kubectl -n muse-analyse describe pod <имя>        # причина, если под не стартует / OOMKilled
kubectl -n muse-analyse logs deploy/worker -f     # логи воркера
kubectl -n muse-analyse top pod                   # потребление (нужен metrics-server)
kubectl kustomize k8s/base                        # посмотреть итоговый YAML, ничего не применяя
kubectl delete namespace muse-analyse             # снести всё, ВКЛЮЧАЯ тома и их данные
```
