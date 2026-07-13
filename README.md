# Muse Analyse

**Музыкальный анализ и AI-критика** — веб-приложение для извлечения музыкальных признаков из аудиофайлов с помощью [Essentia](https://essentia.upf.edu/) и генерации структурированных обзоров на русском языке.

---

## Возможности

- Загрузка аудио через веб-интерфейс (drag & drop)
- Поддержка форматов: **MP3, WAV, FLAC, OGG, M4A**
- Извлечение признаков Essentia: темп, тональность, громкость, спектр, ритм, танцевальность, энергия
- Генерация музыкального обзора на **русском языке**:
  - через **OpenAI API** (если задан `OPENAI_API_KEY`)
  - или **шаблонный fallback** без внешних API
- Возврат сырых параметров (JSON) и текста обзора

---

## Структура проекта

```
muse analyse/
├── app/
│   ├── __init__.py          # Версия пакета
│   ├── config.py            # Конфигурация из .env
│   ├── audio_analysis.py    # Essentia: извлечение признаков
│   ├── review_generator.py  # OpenAI / шаблонный обзор
│   └── main.py              # FastAPI-приложение
├── static/
│   ├── index.html           # Веб-интерфейс
│   ├── style.css
│   └── app.js
├── uploads/                 # Временные файлы (gitignored)
├── run.py                   # Запуск сервера
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Установка

### 1. Системные зависимости (macOS)

Essentia требует **ffmpeg** для декодирования MP3, M4A и других сжатых форматов:

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

Essentia — самая сложная часть установки. Есть несколько вариантов:

#### Вариант A: pip (рекомендуется попробовать первым)

```bash
pip install essentia
```

На Apple Silicon (M1/M2/M3) и Intel pip-колеса доступны не для всех версий Python. Если установка не удалась — переходите к варианту B.

#### Вариант B: Conda (наиболее надёжный на macOS)

```bash
conda create -n muse-analyse python=3.10
conda activate muse-analyse
conda install -c conda-forge essentia
pip install -r requirements.txt
```

#### Вариант C: Сборка из исходников

См. [официальную документацию Essentia](https://essentia.upf.edu/installing.html). На macOS потребуются Xcode CLI tools, cmake, ffmpeg и зависимости MTG.

#### Проверка установки

```bash
python -c "import essentia; print(essentia.__version__)"
```

### 4. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env — добавьте OPENAI_API_KEY (опционально)
```

---

## Запуск

```bash
source .venv/bin/activate
python run.py
```

Откройте в браузере: **http://localhost:8000**

API-документация: **http://localhost:8000/docs**

### Альтернативный запуск

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API

### `GET /api/health`

Проверка состояния сервиса и доступности Essentia.

### `POST /api/analyze`

Загрузка аудиофайла (`multipart/form-data`, поле `file`).

**Ответ:**

```json
{
  "success": true,
  "filename": "track.mp3",
  "features": { ... },
  "review": {
    "source": "template",
    "language": "ru",
    "score": 7.2,
    "sections": { ... },
    "full_text": "..."
  }
}
```

---

## Извлекаемые признаки

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
