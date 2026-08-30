# Quick Start Мuse Analyse

# tldr:
```
cd /path/to/muse-analyse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning --no-access-log
```
открыть http://localhost:8000

### 1. Клонируем / открываем проект

```bash
cd /path/to/muse-analyse
```

### 2. Конфигурация

```bash
cp .env.example .env
```

Добавьте в `.env` API-ключ выбранного LLM-провайдера. Без ключа приложение использует шаблонный fallback.

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

### 3. Запуск контейнера

```bash
docker compose up --build
```

Для старой standalone-установки Compose используйте `docker-compose` вместо `docker compose`.

Открыть: **http://localhost:8000**

### 4. Проверка

```bash
curl http://localhost:8000/api/health
```

Логи:

```bash
docker compose logs -f muse-analyse
```

---

## Использование

### Веб-интерфейс

1. Перетащите MP3/WAV/FLAC/OGG/M4A на главную страницу
2. Ждите анализа (1-3 мин в зависимости от длины трека)
3. Получите параметры + AI-обзор

### API

```bash
# Проверить доступные провайдеры
curl http://localhost:8000/api/providers

# Загрузить трек
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

---

## Документация

- **[README.md](README.md)** — основная информация
- **[LLM_PROVIDERS.md](LLM_PROVIDERS.md)** — подробно по каждому провайдеру
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — для разработчиков
- **[CHANGELOG.md](CHANGELOG.md)** — что нового в v1.1.0
- **[MCP_INTEGRATION.md](MCP_INTEGRATION.md)** — интеграция с Claude Desktop

---

## RAG-профиль

Базовый контейнер запускается без тяжёлых RAG-зависимостей. Для RAG:

```bash
docker compose down
docker compose --profile rag up --build muse-analyse-rag
docker compose --profile rag run --rm muse-analyse-rag python scripts/index_knowledge.py
```

Индекс сохраняется в Docker volume.

## Разрешение проблем

### Essentia не установилась

```bash
docker compose logs muse-analyse
docker compose build --no-cache muse-analyse
```

### API ключ не работает

```bash
# Проверьте конфиг
curl http://localhost:8000/api/health

# Ключ должен быть в поле llm_providers
```

### Ollama недоступна

Проверьте, что Ollama доступна из контейнера, и укажите корректный `OLLAMA_BASE_URL`.

### Медленный анализ

Это нормально! Essentia обрабатывает весь аудиофайл:
- 3 мин трека = 45-120 сек анализа
- + 5-45 сек LLM ответ

---

## Переключение провайдера во время работы

Достаточно:
1. Отредактировать `.env` (изменить `LLM_PROVIDER`)
2. Пересоздать контейнер: `docker compose up -d --force-recreate`

Никакой переустановки не нужна.

---

## Рекомендации

| Ситуация | Команда |
|----------|---------|
| Первый запуск | `LLM_PROVIDER=openai` |
| Хочу сэкономить | `LLM_PROVIDER=ollama` |
| Хочу лучший результат | `LLM_PROVIDER=claude` |
| Работаю локально | `LLM_PROVIDER=ollama` |
| Production | `LLM_PROVIDER=openai` или `nemotron` |

---

## Возможности MCP (опционально)

Если хотите использовать анализ в Claude Desktop:

1. Установите MCP SDK: `pip install mcp httpx`
2. Скопируйте `mcp_server.py` в проект (см. MCP_INTEGRATION.md)
3. Добавьте в Claude Desktop конфиг
4. Используйте инструменты прямо в Claude

---

## Примеры на Python

```python
import requests

# Проверить статус
response = requests.get("http://localhost:8000/api/health")
print(response.json())

# Загрузить трек
with open("track.mp3", "rb") as f:
    files = {"file": f}
    response = requests.post("http://localhost:8000/api/analyze", files=files)
    result = response.json()
    print(f"Оценка: {result['review']['score']}/10")
    print(f"Обзор: {result['review']['full_text']}")
```

---

## API документация

Полная интерактивная документация: **http://localhost:8000/docs**

---

## Нужна помощь?

1. Прочитайте [ARCHITECTURE.md](ARCHITECTURE.md)
2. Проверьте логи сервера
3. Запустите тесты: `pytest tests/ -v`
4. Проверьте конфиг: `curl http://localhost:8000/api/health`

---

**Готовы к использованию!** 🎵
