# Использование разных LLM провайдеров в Muse Analyse

После реализации поддержки множественных LLM провайдеров, теперь вы можете выбрать любого провайдера в зависимости от ваших нужд.

## Быстрый старт

### 1. Копируем конфиг
```bash
cp .env.example .env
```

### 2. Выбираем провайдера
Отредактируйте `.env` и установите `LLM_PROVIDER` одному из:
- `openai` (по умолчанию)
- `claude`
- `ollama`
- `nemotron`

### 3. Запускаем
```bash
pip install -r requirements.txt
python run.py
```

---

## Конфигурация каждого провайдера

### OpenAI GPT
**Лучше для:** универсального использования, высокого качества обзоров

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini  # или gpt-4, gpt-4-turbo и т.д.
```

**Установка:**
```bash
pip install openai>=1.55.0
```

**Получить API ключ:** https://platform.openai.com/api-keys

**Стоимость:** платное, ~$0.15 за 1M входных токенов (GPT-4o-mini)

---

### Anthropic Claude
**Лучше для:** глубокого анализа музыки, сложных структурированных ответов

```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CLAUDE_MODEL=claude-3-5-sonnet-20241022  # или claude-3-opus-20240229
```

**Установка:**
```bash
pip install anthropic>=0.30.0
```

**Получить API ключ:** https://console.anthropic.com/

**Стоимость:** платное, ~$3 за 1M входных токенов (Claude 3.5 Sonnet)

---

### Ollama (локальный)
**Лучше для:** приватности, без коммерческих ограничений, бесплатного локального запуска

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral  # или llama2, neural-chat, etc.
```

**Установка Ollama:**
1. Скачайте с https://ollama.ai/download
2. Запустите: `ollama serve`
3. В другом терминале скачайте модель: `ollama pull mistral`

**Доступные модели:**
- `mistral` — 7B, быстрая, хорошее качество
- `llama2` — 7B, универсальная
- `neural-chat` — 7B, оптимизирована для диалога
- `orca-mini` — 3B, легкая
- Полный список: https://ollama.ai/library

**Стоимость:** бесплатно (локальный запуск)

---

### NVIDIA Nemotron API
**Лучше для:** баланса между качеством и скоростью на NVIDIA инфраструктуре

```env
LLM_PROVIDER=nemotron
NEMOTRON_API_KEY=nvapi_your_api_key_here
NEMOTRON_MODEL=meta/llama-2-70b-chat
NEMOTRON_BASE_URL=https://integrate.api.nvidia.com/v1
```

**Установка:**
```bash
pip install requests>=2.31.0  # уже есть в requirements.txt
```

**Получить API ключ:** 
1. Зарегистрируйтесь на https://developer.nvidia.com/
2. Создайте API ключ в https://docs.nvidia.com/cloud/cloud-docs/getting-started/quickstart.html

**Доступные модели:**
- `meta/llama-2-70b-chat` — мощная, качественная
- `mistralai/mixtral-8x7b-instruct-v0.1` — быстрая
- Полный список: https://docs.nvidia.com/cloud/cloud-docs/getting-started/quickstart.html

**Стоимость:** часто бесплатно для новых пользователей, затем платно

---

## API эндпоинты

### Проверить доступные провайдеры
```bash
curl http://localhost:8000/api/providers
```

Ответ:
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

### Загрузить аудио и получить обзор
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

Ответ включит:
- `features` — все параметры Essentia
- `review` — обзор от выбранного LLM провайдера
  - `source` — название провайдера
  - `model` — использованная модель
  - `score` — оценка 1-10
  - `sections` — структурированный обзор
  - `full_text` — полный текст обзора

---

## Рекомендации

| Сценарий | Провайдер | Причина |
|----------|-----------|---------|
| Быстрый старт | OpenAI | Наиболее стабильный, хорошее качество |
| Приватный анализ | Ollama | Локальный запуск, нет отправки данных |
| Лучшее качество | Claude | Самые мощные рассуждения |
| Бюджетный вариант | Ollama (mistral) | Бесплатно локально |
| Production на GPU | Nemotron | Оптимизирована для NVIDIA железа |

---

## Fallback механизм

Если выбранный провайдер недоступен или произойдёт ошибка, система автоматически вернёт **шаблонный обзор** (template) на основе параметров Essentia.

Это гарантирует, что анализ аудио всегда работает, даже без интернета и API ключей.

---

## Примеры .env

### Для локального использования (Ollama)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### Для production с OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```

### Для production с Claude
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxx
CLAUDE_MODEL=claude-3-5-sonnet-20241022
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```
