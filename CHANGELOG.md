# Changelog — Поддержка нескольких LLM провайдеров

## v1.1.0 — Множественные LLM провайдеры (2024)

### 🎯 Основные изменения

#### ✨ Новые провайдеры LLM

Добавлена поддержка четырёх LLM провайдеров:

1. **OpenAI GPT** (`openai`)
   - Модели: gpt-4o-mini, gpt-4, gpt-4-turbo
   - Статус: платно
   - Документация: https://platform.openai.com/api-keys

2. **Anthropic Claude** (`claude`)
   - Модели: claude-3-5-sonnet, claude-3-opus
   - Статус: платно
   - Документация: https://console.anthropic.com/

3. **Ollama локальный** (`ollama`)
   - Модели: mistral, llama2, neural-chat, orca-mini и другие
   - Статус: бесплатно (локальный запуск)
   - Документация: https://ollama.ai/

4. **NVIDIA Nemotron** (`nemotron`)
   - Модели: meta/llama-2-70b-chat и другие
   - Статус: платно / Free tier
   - Документация: https://docs.nvidia.com/

### 📁 Новые файлы

- **`app/llm_providers.py`** — модуль с реализацией всех провайдеров
  - `LLMProvider` — абстрактный базовый класс
  - `OpenAIProvider`, `ClaudeProvider`, `OllamaProvider`, `NemotronProvider` — конкретные реализации
  - `LLMProviderFactory` — фабрика для создания провайдеров

- **`LLM_PROVIDERS.md`** — подробная документация по конфигурации каждого провайдера

- **`ARCHITECTURE.md`** — описание архитектуры проекта

- **`MCP_INTEGRATION.md`** — гайд по интеграции как MCP сервера

- **`examples_test_providers.py`** — примеры использования API

- **`tests_test_llm_providers.py`** — тесты для провайдеров и API

### 🔄 Изменения в существующих файлах

#### `app/config.py`
- Добавлены новые переменные конфигурации для каждого провайдера:
  - `LLM_PROVIDER` — выбор провайдера (по умолчанию "openai")
  - `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
  - `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - `NEMOTRON_API_KEY`, `NEMOTRON_MODEL`, `NEMOTRON_BASE_URL`
  - `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`
- Добавлены константы `SUPPORTED_PROVIDERS`

#### `app/review_generator.py`
- Полностью переписана функция `generate_review()`
- Теперь использует `LLMProviderFactory.get_provider()` вместо прямого вызова OpenAI
- Автоматический fallback на шаблонный обзор при ошибке любого провайдера

#### `app/main.py`
- Добавлен импорт `LLMProviderFactory`
- Обновлён эндпоинт `GET /api/health` — добавлено поле `llm_providers`
- Добавлен новый эндпоинт `GET /api/providers` — возвращает список доступных провайдеров

#### `.env.example`
- Полностью переписан со всеми примерами конфигурации для каждого провайдера

#### `requirements.txt`
- Добавлены: `anthropic>=0.30.0`, `requests>=2.31.0`
- Добавлены для тестирования: `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`

#### `README.md`
- Переписан раздел о возможностях
- Добавлена таблица провайдеров с рекомендациями
- Обновлены примеры API
- Ссылки на новую документацию

### 🏗️ Архитектурные улучшения

1. **Паттерн Factory** — централизованное управление провайдерами
2. **Абстрактный интерфейс `LLMProvider`** — легко добавлять новые провайдеры
3. **Автоматическая проверка доступности** — каждый провайдер знает, доступен ли он
4. **Graceful fallback** — всегда работает на шаблонах даже без API

### 🔌 API изменения

#### Новый эндпоинт: `GET /api/providers`

**Запрос:**
```bash
curl http://localhost:8000/api/providers
```

**Ответ:**
```json
{
  "available": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  },
  "description": {
    "openai": "OpenAI GPT (требует OPENAI_API_KEY)",
    "claude": "Anthropic Claude (требует ANTHROPIC_API_KEY)",
    "ollama": "Локальный Ollama (требует ollama serve)",
    "nemotron": "NVIDIA Nemotron API (требует NEMOTRON_API_KEY)"
  }
}
```

#### Обновлённый эндпоинт: `GET /api/health`

Теперь возвращает статус каждого провайдера:
```json
{
  "status": "ok",
  "version": "1.1.0",
  "essentia_available": true,
  "essentia_error": null,
  "llm_providers": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  }
}
```

#### `POST /api/analyze` ответ

Поле `review` теперь содержит информацию о провайдере:
```json
{
  "review": {
    "source": "openai",
    "model": "gpt-4o-mini",
    "language": "ru",
    "score": 7.5,
    "sections": { ... },
    "full_text": "..."
  }
}
```

### 📚 Документация

Добавлены новые файлы:
- **LLM_PROVIDERS.md** — полный гайд по каждому провайдеру с примерами конфигурации
- **ARCHITECTURE.md** — технический документ для разработчиков
- **MCP_INTEGRATION.md** — как использовать как MCP сервер в Claude Desktop

### ✅ Тестирование

Добавлены тесты:
- Проверка загрузки конфигурации
- Проверка инициализации фабрики провайдеров
- Проверка доступности каждого провайдера
- Проверка обработки ошибок
- Проверка построения промптов
- Проверка генерации шаблонного обзора
- Проверка API эндпоинтов

**Запуск тестов:**
```bash
pytest tests/ -v
```

### 🔒 Безопасность

- API ключи не логируются
- Временные аудиофайлы удаляются после анализа
- Ollama — локальный запуск означает отсутствие отправки данных в интернет

### 📊 Рекомендации по использованию

| Сценарий | Рекомендуемый провайдер |
|----------|--------------------------|
| Быстрый старт | OpenAI (gpt-4o-mini) |
| Высокое качество анализа | Claude (claude-3-5-sonnet) |
| Приватный анализ | Ollama (mistral) |
| Бюджетный вариант | Ollama (бесплатно) |
| Production на GPU | Nemotron |

### 🚀 Примеры использования

#### Переключение провайдера
```bash
# Отредактируйте .env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxx

# Перезагрузите сервер
python run.py
```

#### Проверка доступности
```bash
curl http://localhost:8000/api/providers | jq
```

#### Анализ с текущим провайдером
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

### 🔄 Обратная совместимость

Все изменения 100% обратно совместимы:
- Если `OPENAI_API_KEY` установлен, используется OpenAI (как было раньше)
- Если `LLM_PROVIDER` не задан, используется "openai" по умолчанию
- Если провайдер недоступен, автоматический fallback на шаблон

### ⚡ Производительность

Нет изменений в производительности. Время анализа остаётся тем же:
- Essentia: 45-120 сек (не изменилось)
- LLM ответ: 5-45 сек в зависимости от провайдера

### 🐛 Исправления

- Более надёжная обработка ошибок при недоступности провайдера
- Лучшее логирование для отладки

### 📝 Миграция со старой версии

Если вы обновляете с v1.0.0:

1. **Установите новые зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Обновите .env:**
   ```bash
   cp .env.example .env
   # Отредактируйте .env
   ```

3. **Всё готово!** Ваш существующий `OPENAI_API_KEY` будет работать как раньше.

Ничего менять не требуется, система автоматически распознает старую конфигурацию.

---

## Благодарности

- Essentia — за мощный анализ аудио
- OpenAI, Anthropic, NVIDIA, Ollama — за доступ к моделям
