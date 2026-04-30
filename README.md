# CV Form Bot

Скрипт автоматически заполняет и отправляет эволюционирующую форму на каждой версии приложения без вмешательства человека.

## Как это работает

1. Playwright открывает браузер и загружает форму
2. LLM анализирует HTML текущей версии и генерирует Playwright-сценарий заполнения
3. Сценарий выполняется: поля заполняются, чекбокс "go to the next version" ставится, форма отправляется
4. Скрипт ждёт смены версии и повторяет процесс

## Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| `playwright` | 1.44.0 | Управление браузером (Chromium) |
| `langchain-openai` | 0.1.8 | LangChain-провайдер для OpenRouter API |
| `langchain-core` | 0.2.10 | Базовые абстракции LangChain (Messages и др.) |
| `python-dotenv` | 1.0.1 | Загрузка переменных окружения из `.env` |

### AI-инструментарий

- **LLM-провайдер:** [OpenRouter](https://openrouter.ai) — единый API для доступа к разным моделям
- **Модель:** `claude-opus-4-5` (Anthropic Claude) через OpenRouter
- **Фреймворк:** [LangChain](https://python.langchain.com) — оркестрация вызовов к LLM

LLM используется для одной задачи: получить HTML формы → вернуть готовый Python/Playwright-код заполнения. Код выполняется динамически через `exec()`.

## Запуск

### Локально

```bash
# 1. Установить зависимости
pip install -r requirements.txt
playwright install chromium

# 2. Создать .env файл
cp .env.example .env
# вставить свой OPENROUTER_API_KEY в .env

# 3. Запустить (приложение должно быть доступно на localhost:5173)
python cv_form_bot.py
```

### Docker

```bash
# Приложение на localhost:5173 должно быть уже запущено на хосте

docker-compose up --build
```

## Конфигурация `.env`

```
OPENROUTER_API_KEY=sk-or-...
```

Получить ключ: [openrouter.ai/keys](https://openrouter.ai/keys)

## Структура проекта

```
.
├── cv_form_bot.py      # основной скрипт
├── requirements.txt    # Python-зависимости
├── Dockerfile
├── docker-compose.yml
├── .env                # ключи (не коммитить!)
├── .env.example        # шаблон для .env
└── README.md
```
