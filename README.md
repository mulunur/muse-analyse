# Muse Analyse

**Музыкальный анализ и AI-критика** — веб-приложение для извлечения музыкальных признаков из аудиофайлов с помощью [Essentia](https://essentia.upf.edu/) и генерации структурированных обзоров на русском языке.

---

## Возможности

- Загрузка аудио через веб-интерфейс (drag & drop)
- Поддержка форматов: **MP3, WAV, FLAC, OGG, M4A**
- Извлечение признаков Essentia: темп, тональность, громкость, спектр, ритм, танцевальность, энергия
- Генерация музыкального обзора на **русском языке** с поддержкой **нескольких LLM провайдеров**:
  - **OpenAI** — GPT-4o-mini и другие модели (платно)
  - **Anthropic Claude** — Claude 3.5 Sonnet (платно)
  - **Ollama** — локальный запуск, бесплатно (приватность)
  - **NVIDIA Nemotron** — мощная API (платно или free tier)
  - **Шаблонный fallback** — без API ключей, всегда работает
- Возврат сырых параметров (JSON) и текста обзора

---

## Структура проекта

```
muse analyse/
├── app/
│   ├── __init__.py              # Версия пакета
│   ├── config.py                # Конфигурация из .env
│   ├── audio_analysis.py        # Essentia: извлечение признаков
│   ├── llm_providers.py         # Поддержка OpenAI, Claude, Ollama, Nemotron
│   ├── review_generator.py      # Генерация обзоров с fallback
│   └── main.py                  # FastAPI-приложение
├── static/
│   ├── index.html               # Веб-интерфейс
│   ├── style.css
│   └── app.js
├── uploads/                     # Временные файлы (gitignored)
├── examples_test_providers.py   # Примеры использования API
├── run.py                       # Запуск сервера
├── requirements.txt
├── .env.example
├── LLM_PROVIDERS.md             # Документация по провайдерам
├── .gitignore
└── README.md
```

---

## Быстрый старт

### 1. Системные зависимости (macOS)

```bash
brew install ffmpeg
```

### 2. Python-окружение

```bash
cd "/Users/mulunur/Documents/develop/muse analyse"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Установка Essentia на macOS

#### Рекомендуется: Conda

```bash
conda create -n muse-analyse python=3.10
conda activate muse-analyse
conda install -c conda-forge essentia
pip install -r requirements.txt
```

#### Или: pip (если работает для вашей версии Python)

```bash
pip install essentia
```

**Проверка:**
```bash
python -c "import essentia; print(essentia.__version__)"
```

### 4. Настройка

```bash
cp .env.example .env
# Отредактируйте .env — выберите провайдер и добавьте ключи (опционально)
```

### 5. Запуск

```bash
# Запуск (быстрое, рекомендованное)
python run.py

# Или запускайте напрямую uvicorn (без авто‑перезагрузки в продакшн):
/path/to/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info

# Если вы используете виртуальное окружение в проекте:
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Открыть: **http://localhost:8000**

---

## LLM Провайдеры

По умолчанию используется **OpenAI**, но вы можете выбрать любого из четырёх:

| Провайдер | Конфиг | Стоимость | Лучше для |
|-----------|--------|----------|----------|
| **OpenAI** | `LLM_PROVIDER=openai` | Платно | Быстрый старт, высокое качество |
| **Claude** | `LLM_PROVIDER=claude` | Платно | Глубокий анализ, структурированность |
| **Ollama** | `LLM_PROVIDER=ollama` | Бесплатно | Приватность, локальный запуск |
| **Nemotron** | `LLM_PROVIDER=nemotron` | Платно / Free tier | GPU оптимизация |

**Подробная настройка:** см. [LLM_PROVIDERS.md](LLM_PROVIDERS.md)

---

## API

### `GET /api/health`

Проверка состояния, доступности Essentia и LLM провайдеров.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "essentia_available": true,
  "llm_providers": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  }
}
```

### `GET /api/providers`

Список доступных LLM провайдеров.

```json
{
  "available": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  },
  "description": { ... }
}
```

### `POST /api/analyze`

Загрузка аудиофайла и получение анализа + обзора.

**Запрос:**
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

### Запуск MCP-инструмента (локально, пример)

Если вы хотите вызвать внутреннюю обёртку `mcp_server.py` (не требует запуска FastMCP транспорта):

```bash
# В одном терминале запустите API (см. выше):
source .venv311/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000

# В другом терминале выполните анализ файла через инструмент:
/path/to/project/.venv311/bin/python -c "from mcp_server import analyze_audio; print(analyze_audio('/absolute/path/to/track.mp3'))"
```

Если хотите запустить interactive FastMCP transport (stdin/stdout) для интеграции с внешними менеджерами MCP, используйте:

```bash
# Запуск FastMCP (пример):
/path/to/project/.venv311/bin/python mcp_server.py
```

**Ответ:**

```json
{
  "success": true,
  "filename": "track.mp3",
  "features": { ... },
  "review": {
    "source": "openai",
    "model": "gpt-4o-mini",
    "language": "ru",
    "score": 7.5,
    "sections": {
      "summary": "...",
      "rhythm": "...",
      "tonality": "...",
      "production": "...",
      "verdict": "..."
    },
    "full_text": "..."
  }
}
```

---

## Примеры использования

| Категория | Признаки |
|-----------|----------|
| **Ритм** | BPM, уверенность бита, количество ударов, onset rate, beat loudness |
| **Тональность** | Тоника, лад (мажор/минор), сила тональности, строй (Гц), аккорды |
| **Динамика** | LUFS (EBU R128), громкость (dB), динамическая сложность, RMS, replay gain |
| **Спектр** | Спектральный центроид, яркость, rolloff, flux, zero-crossing rate, MFCC |
| **Прочее** | Танцевальность (Danceability), энергия (композитная оценка 0–1) |

---

## OpenAI (опционально)

Если в `.env` задан `OPENAI_API_KEY`, обзоры генерируются через ChatGPT (`OPENAI_MODEL`, по умолчанию `gpt-4o-mini`).

Без ключа приложение работает полностью — используется встроенный шаблонный генератор обзоров на русском языке.

---

## Ограничения

- **Essentia на macOS** может потребовать conda или ручную сборку; pip не всегда работает.
- **Анализ длинных треков** (>5 мин) может занимать значительное время.
- **MP3/M4A** требуют установленного ffmpeg в системе.
- Загруженные файлы **удаляются сразу после анализа** (не сохраняются на диске).
- Оценка «энергии» — **прокси-метрика** на основе RMS, BPM, яркости и танцевальности (Essentia не имеет прямого алгоритма «energy» как Spotify).
- AI-обзор без API — **шаблонный**, не заменяет живого критика.

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `Essentia не установлена` | См. раздел установки Essentia выше |
| `Не удалось загрузить аудио` | Установите `brew install ffmpeg`, проверьте формат файла |
| `Пустой файл` / `повреждён` | Проверьте целостность аудиофайла |
| OpenAI ошибка | Проверьте ключ; приложение автоматически переключится на шаблон |

---

## Лицензия

MIT (при необходимости уточните для вашего проекта).

Essentia распространяется под лицензией AFFERO GPL v3.
