# Архитектура Muse Analyse

## Общая схема

```
                    ┌─────────────────────┐
                    │    Веб-интерфейс    │
                    │   (index.html +     │
                    │    app.js/css)      │
                    └──────────┬──────────┘
                               │ HTTP
                               ▼
                    ┌─────────────────────┐
                    │   FastAPI сервер    │
                    │   (main.py)         │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
          ┌─────────────┐ ┌──────────┐ ┌────────────┐
          │ Essentia    │ │ LLM      │ │ Config     │
          │ Audio       │ │Providers │ │ Management │
          │ Analysis    │ │ Factory  │ │            │
          │ (python)    │ │ (python) │ │            │
          └─────────────┘ └──────────┘ └────────────┘
                │              │
                │              │
    ┌───────────┘              └───────────────┬──────────┬──────────┐
    │                                         │          │          │
    ▼                                         ▼          ▼          ▼
  Аудио                                   OpenAI    Claude    Ollama
  файл                                    API       API       (local)
                                                                │
                                                   ┌───────────┴──────────┐
                                                   │                      │
                                                   ▼                      ▼
                                                Nemotron              Шаблон
                                                  API              (fallback)
```

## Компоненты

### 1. **Frontend** (`static/`)

- **index.html** — главная страница с интерфейсом загрузки
- **app.js** — логика взаимодействия с API (drag-drop, отправка файлов, отображение результатов)
- **style.css** — оформление (тёмная тема, адаптивный дизайн)

### 2. **Backend** (`app/`)

#### `main.py` — FastAPI приложение

Основные эндпоинты:
- `GET /` — возвращает index.html
- `GET /api/health` — статус системы (Essentia, LLM провайдеры)
- `GET /api/providers` — список доступных LLM провайдеров
- `POST /api/analyze` — основной эндпоинт для анализа аудио

```python
# Поток обработки запроса:
# 1. Валидация файла (расширение, размер)
# 2. Сохранение в временную папку
# 3. analyze_audio() → признаки Essentia
# 4. generate_review() → обзор от LLM
# 5. Удаление временного файла
# 6. Возврат результата JSON
```

#### `audio_analysis.py` — Essentia анализ

Функция `analyze_audio(file_path)` возвращает словарь с параметрами:

```python
{
    "file": "track.mp3",
    "duration_sec": 180.5,
    "rhythm": {
        "bpm": 128.0,
        "beat_confidence": 0.95,
        "beats_count": 245,
        "onset_rate": 0.123
    },
    "tonal": {
        "key": "C",
        "scale": "minor",
        "key_strength": 0.88,
        "danceability": 0.72,
        "top_chords": [{"chord": "Cm", "count": 45}]
    },
    "dynamics": {
        "loudness_ebu128_lufs": -9.5,
        "loudness_db": -6.2,
        "dynamic_complexity": 0.38,
        "rms": 0.156
    },
    "spectral": {
        "spectral_centroid_hz": 2340.5,
        "spectral_brightness": 0.45,
        "spectral_rolloff_hz": 5600.0,
        "mfcc_coefficients": [...]
    },
    "energy": 0.64,
    "essentia_version": "2.1b6"
}
```

#### `llm_providers.py` — Фабрика LLM провайдеров

Архитектура провайдеров:

```python
LLMProvider (ABC)
├── OpenAIProvider
├── ClaudeProvider
├── OllamaProvider
└── NemotronProvider

LLMProviderFactory
├── get_provider(name) → инстанс провайдера
└── list_available_providers() → dict[str, bool]
```

Каждый провайдер:
- Реализует `is_available()` — проверка наличия ключей/доступности
- Реализует `generate_review()` — отправляет API запрос и парсит JSON

#### `review_generator.py` — Генерация обзоров

Функция `generate_review(features)`:

```
1. Попытка получить провайдер через LLMProviderFactory
2. Если успешно → вызов provider.generate_review()
3. Если ошибка → fallback на _build_template_review()
4. Всегда возвращает структурированный обзор
```

Обзор содержит:
- `source` — откуда пришёл ("openai", "claude", "ollama", "nemotron", "template")
- `model` — название модели
- `language` — "ru" (русский)
- `score` — 1-10
- `sections` — структурированные части (summary, rhythm, tonality, production, verdict)
- `full_text` — полный текст обзора

#### `config.py` — Конфигурация

Загружает из .env:
- LLM_PROVIDER — выбранный провайдер
- Ключи API для каждого провайдера
- URL/модели для каждого провайдера
- Параметры LLM (temperature, max_tokens)
- Параметры сервера (HOST, PORT)

## Поток данных для анализа трека

```
Пользователь загружает MP3
    │
    ▼
Валидация (формат, размер)
    │
    ▼
Сохранение в /uploads/
    │
    ▼
Essentia анализ (45-120 сек в зависимости от длины)
    │
    ├─→ Спектральный анализ
    ├─→ Ритмический анализ
    ├─→ Тональный анализ
    ├─→ Динамический анализ
    └─→ Энергия и прочее
    │
    ▼
Получение словаря признаков
    │
    ▼
LLMProviderFactory.get_provider()
    │
    ├─→ Если доступен выбранный → используем его
    │   ├─→ OpenAI: POST к api.openai.com
    │   ├─→ Claude: POST к api.anthropic.com
    │   ├─→ Ollama: POST к localhost:11434
    │   └─→ Nemotron: POST к NVIDIA API
    │
    └─→ Если недоступен → fallback к шаблону
    │
    ▼
Получение структурированного обзора (JSON)
    │
    ▼
Удаление временного файла
    │
    ▼
Возврат JSON с features + review
    │
    ▼
Frontend отображает результат
```

## Определение провайдера

```python
# В config.py:
LLM_PROVIDER = "openai"  # можно изменить на claude, ollama, nemotron

# При запуске:
def generate_review(features):
    try:
        provider = LLMProviderFactory.get_provider()  # читает LLM_PROVIDER
        return provider.generate_review(features)
    except ValueError:
        # Провайдер недоступен или ключи не установлены
        return _build_template_review(features)
```

## Расширение архитектуры

### Добавить новый LLM провайдер

1. **Создать класс в `llm_providers.py`:**
```python
class MyLLMProvider(LLMProvider):
    def is_available(self) -> bool:
        return bool(os.getenv("MY_API_KEY"))
    
    def generate_review(self, features):
        # Реализация вызова API
        pass
```

2. **Зарегистрировать в фабрике:**
```python
class LLMProviderFactory:
    _providers = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
        "nemotron": NemotronProvider,
        "my_llm": MyLLMProvider,  # ← добавить здесь
    }
```

3. **Добавить конфиг в `config.py`:**
```python
MY_API_KEY = os.getenv("MY_API_KEY", "").strip()
MY_MODEL = os.getenv("MY_MODEL", "default-model")
```

4. **Обновить `.env.example`**

### Добавить новый признак Essentia

1. **Добавить в `audio_analysis.py`:**
```python
def _new_feature(audio):
    # вычисление параметра
    return value

result = analyze_audio(path)
result["new_feature"] = _new_feature(audio)
```

2. **Обновить промпт в `llm_providers.py`** для учёта нового признака

---

## Тестирование

### Проверить состояние
```bash
curl http://localhost:8000/api/health
```

### Проверить провайдеры
```bash
curl http://localhost:8000/api/providers
```

### Анализировать трек
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze | jq .
```

### Тестовый скрипт
```bash
python examples_test_providers.py track.mp3
```

---

## Производительность

| Операция | Время |
|----------|-------|
| Essentia анализ (3 мин трека) | 45-120 сек |
| OpenAI API ответ | 5-15 сек |
| Claude API ответ | 10-20 сек |
| Ollama ответ (mistral) | 15-45 сек |
| Nemotron API ответ | 10-30 сек |
| **Итого** | **60-180 сек** |

Самый медленный этап — Essentia (аудио файл обрабатывается полностью).

---

## Безопасность

- Все загруженные файлы удаляются после анализа
- Поддержка лимитов размера файла (по умолчанию 50 МБ)
- Валидация расширений файлов
- Нет хранения истории анализов на сервере
- При использовании Ollama — данные не выходят из локальной сети
