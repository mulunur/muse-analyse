# ✅ Checklist — First Run

## Пред-требования ✓

- [ ] Docker Desktop (macOS/Windows) или Docker Engine (Linux VPS)
- [ ] Docker Compose plugin
- [ ] Git (опционально)

## 1. Окружение

```bash
cd /path/to/muse-analyse
cp .env.example .env
```

- [ ] `.env` создан

## 2. Конфигурация

**Выберите вариант (отредактируйте `.env`):**

### Вариант A: OpenAI (рекомендуется для первого запуска)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```
- [ ] API ключ получен (https://platform.openai.com/api-keys)
- [ ] Ключ добавлен в `.env`

### Вариант B: Claude
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```
- [ ] API ключ получен (https://console.anthropic.com/)
- [ ] Ключ добавлен в `.env`

### Вариант C: Ollama (локально, бесплатно)
```bash
# Установите Ollama: https://ollama.ai/download
# Запустите в другом терминале:
ollama serve

# Скачайте модель в третьем терминале:
ollama pull mistral
```

`.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

- [ ] Ollama установлена
- [ ] `ollama serve` запущена в отдельном терминале
- [ ] `ollama pull mistral` выполнена
- [ ] `.env` обновлен

### Вариант D: Nemotron
```env
LLM_PROVIDER=nemotron
NEMOTRON_API_KEY=nvapi_your_api_key_here
NEMOTRON_MODEL=meta/llama-2-70b-chat
```
- [ ] API ключ получен (https://developer.nvidia.com/)
- [ ] Ключ добавлен в `.env`

## 3. Запуск контейнера

```bash
docker compose up --build -d
```

- [ ] Образ собран
- [ ] Контейнер запущен

## 4. Проверка здоровья

```bash
curl http://localhost:8000/api/health
```

- [ ] Essentia доступна
- [ ] Контейнер имеет статус healthy

## 5. Проверка провайдеров

```bash
curl http://localhost:8000/api/providers | jq
```

- [ ] Список провайдеров возвращается

## 6. Первый тест в браузере

Откройте: **http://localhost:8000**

- [ ] Веб-интерфейс загружается
- [ ] Видна зона для загрузки файлов

## 7. Первый анализ

Найдите MP3/WAV файл и либо:

### Вариант A: Веб-интерфейс
1. Перетащите файл на страницу
2. Ждите анализа (1-3 минуты)
3. Смотрите результаты

- [ ] Файл загружен
- [ ] Анализ запущен
- [ ] Результаты отображаются

### Вариант B: Command line
```bash
curl -X POST -F "file=@/path/to/track.mp3" http://localhost:8000/api/analyze | jq
```

- [ ] Ответ получен
- [ ] В ответе есть `review` с оценкой и текстом

## 8. Проверка результатов

В ответе должны быть:
```json
{
  "success": true,
  "filename": "track.mp3",
  "features": {
    "duration_sec": ...,
    "rhythm": { "bpm": ... },
    "tonal": { "key": ... },
    ...
  },
  "review": {
    "source": "openai",  // или claude/ollama/nemotron
    "model": "gpt-4o-mini",
    "score": 7.5,
    "sections": { ... },
    "full_text": "..."
  }
}
```

- [ ] `features` содержит параметры анализа
- [ ] `review.source` указывает используемый провайдер
- [ ] `review.score` — число 1-10
- [ ] `review.full_text` содержит обзор на русском

## ✨ Готово!

Если все пункты выше отмечены — система работает корректно!

## 🐛 Решение проблем

### Essentia не установилась
→ Проверьте архитектуру: production-образ рассчитан на `linux/amd64`.
→ Посмотрите логи: `docker compose logs muse-analyse`

### LLM провайдер отмечен как false
→ Проверьте API ключ в `.env`

### Ollama не подключается
→ Убедитесь что `ollama serve` запущена
→ Проверьте `OLLAMA_BASE_URL` в `.env`

### Медленный первый анализ
→ Это нормально, Essentia обрабатывает весь файл
→ 3 мин трека = 45-120 сек анализа

### API ошибка 503
→ Essentia не загрузилась внутри контейнера
→ Пересоберите образ: `docker compose build --no-cache muse-analyse`

## 📚 Дальше

- Прочитайте [QUICKSTART.md](QUICKSTART.md)
- Изучите [LLM_PROVIDERS.md](LLM_PROVIDERS.md)
- Смотрите примеры в [examples_test_providers.py](examples_test_providers.py)

## 🚀 Готовы начать?

```bash
docker compose up --build -d
```

Откройте браузер на **http://localhost:8000** и загружайте треки! 🎵
