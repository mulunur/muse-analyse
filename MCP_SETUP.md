# MCP Сервер Muse Analyse

Минимальная интеграция для использования с Claude Desktop и другими MCP-совместимыми инструментами.

## Установка

```bash
pip install -r requirements.txt
```

## Конфигурация Claude Desktop

### macOS
1. Отредактируйте:
```bash
~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. Добавьте:
```json
{
  "mcpServers": {
    "muse-analyse": {
      "command": "python",
      "args": ["/Users/your_username/Documents/develop/muse analyse/mcp_server.py"]
    }
  }
}
```

### Windows
`%APPDATA%\Claude\claude_desktop_config.json`

### Linux
`~/.config/Claude/claude_desktop_config.json`

## Использование

### 1. Запустите Muse Analyse
```bash
python run.py
```

### 2. Перезагрузите Claude Desktop

### 3. Используйте в Claude

```
Проанализируй трек ~/Music/song.mp3 и дай детальный обзор
```

Claude автоматически использует инструмент `analyze_audio` и получит:
- Все параметры Essentia
- AI-обзор от выбранного LLM провайдера
- Оценку 1-10

## Доступные инструменты

| Инструмент | Что делает |
|-----------|-----------|
| `analyze_audio` | Загрузить MP3/WAV/FLAC и получить анализ |
| `check_providers` | Список доступных LLM провайдеров |
| `get_status` | Статус системы (Essentia, провайдеры) |

## Примеры запросов

```
"Какие провайдеры доступны для анализа?"
→ Использует check_providers

"Проанализируй track.mp3 и скажи танцевальный ли это трек?"
→ Использует analyze_audio, затем LLM анализирует результаты

"Проверь статус сервиса анализа"
→ Использует get_status
```

## Тестирование

Запустите сервер в одном терминале:
```bash
python run.py
```

В другом:
```bash
python mcp_server.py
```

Проверьте логи MCP сервера.
