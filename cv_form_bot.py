"""
CV Form Bot — автоматически заполняет эволюционирующую форму.

Зависимости:
    pip install playwright langchain-openai langchain-core python-dotenv
    playwright install chromium
"""

import asyncio
import re
import textwrap
from dotenv import load_dotenv
import os
from playwright.async_api import async_playwright, Page
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────
APP_URL = os.getenv("APP_URL", "http://localhost:5173/")
MAX_VERSIONS = 30          # защита от бесконечного цикла
MODEL = "anthropic/claude-opus-4.5"  # модель для анализа
HEADLESS = os.getenv("HEADLESS", "false").lower() in {"1", "true", "yes"}
PAGE_LOAD_TIMEOUT_MS = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "30000"))

SYSTEM_PROMPT = """
Ты — эксперт по Playwright и веб-автоматизации.
Тебе дают HTML формы и ты пишешь ТОЛЬКО Python-код для Playwright,
который заполняет все поля правдоподобными тестовыми данными и отправляет форму.

ПРАВИЛА:
1. Используй уже существующий объект `page` (Playwright Page), не создавай новый.
2. Заполни ВСЕ видимые поля (input, textarea, select) правдоподобными данными.
3. Обязательно поставь чекбокс "go to the next version" (если он есть) в checked=True.
4. В конце нажми кнопку submit.
5. После submit жди либо изменения URL, либо появления success-сообщения, либо смены версии — используй:
   await page.wait_for_timeout(2000)
6. НЕ импортируй ничего — все нужные импорты уже есть.
7. Оберни код в async def fill_and_submit(page): ...
8. Для radio/checkbox используй page.check() или page.click().
9. Для select используй page.select_option().
10. НЕ пиши никаких пояснений, ТОЛЬКО код функции.
11. Данные должны быть реалистичными (имя, email, опыт работы и т.д.).
"""


# ──────────────────────────────────────────────
# LLM-клиент
# ──────────────────────────────────────────────
llm = ChatOpenAI(
    model=MODEL,
    max_tokens=2048,
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
)


async def get_page_html(page: Page) -> str:
    """Получаем упрощённый HTML только формы (или всего body)."""
    html = await page.evaluate("""() => {
        const form = document.querySelector('form');
        return form ? form.outerHTML : document.body.innerHTML;
    }""")
    # Обрезаем до ~8000 символов, чтобы не перегружать контекст
    return html[:8000]


def get_version(html: str) -> str:
    """Извлекаем номер версии из текста страницы."""
    match = re.search(r'[Vv]ersion\s*(\d+)', html)
    return match.group(1) if match else "?"


async def generate_fill_script(html: str, version: str) -> str:
    """Просим LLM сгенерировать Playwright-сценарий для текущей версии."""
    prompt = f"""
Вот HTML формы (версия {version}):

```html
{html}
```

Напиши функцию `fill_and_submit(page)` для Playwright,
которая заполнит все поля и отправит форму.
Обязательно поставь чекбокс "go to the next version" в True перед отправкой.
"""
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    code = response.content

    # Вырезаем блок кода, если LLM обернул в ```
    code_match = re.search(r'```(?:python)?\n(.*?)```', code, re.DOTALL)
    if code_match:
        code = code_match.group(1)

    return code.strip()


async def execute_fill_script(page: Page, script: str) -> bool:
    """Выполняем сгенерированный скрипт."""
    namespace: dict = {"page": page, "asyncio": asyncio}
    full_code = textwrap.dedent(f"""
import asyncio

{script}
""")
    try:
        exec(compile(full_code, "<generated>", "exec"), namespace)  # noqa: S102
        fill_fn = namespace.get("fill_and_submit")
        if fill_fn is None:
            print("  [!] Функция fill_and_submit не найдена в скрипте")
            return False
        await fill_fn(page)
        return True
    except Exception as exc:
        print(f"  [!] Ошибка при выполнении скрипта: {exc}")
        return False


async def wait_for_version_change(page: Page, current_version: str, timeout: int = 8000) -> str:
    """Ждём смены версии на странице."""
    async def version_changed():
        body = await page.inner_text("body")
        v = get_version(body)
        return v != current_version and v != "?"

    deadline = asyncio.get_event_loop().time() + timeout / 1000
    while asyncio.get_event_loop().time() < deadline:
        if await version_changed():
            body = await page.inner_text("body")
            return get_version(body)
        await asyncio.sleep(0.5)
    return current_version  # версия не изменилась


# ──────────────────────────────────────────────
# Основной цикл
# ──────────────────────────────────────────────
async def main():
    async with async_playwright() as pw:
        print(f"Запуск бота: APP_URL={APP_URL} | HEADLESS={HEADLESS}")
        browser = await pw.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print(f"  → Открываем страницу: {APP_URL}")
            await page.goto(APP_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            await page.wait_for_selector("form", timeout=PAGE_LOAD_TIMEOUT_MS)
        except Exception as exc:
            print(f"  [!] Не удалось открыть форму по адресу {APP_URL}: {exc}")
            await browser.close()
            return

        for iteration in range(MAX_VERSIONS):
            # 1. Анализируем текущую версию
            html = await get_page_html(page)
            version = get_version(await page.inner_text("body"))
            print(f"\n{'='*50}")
            print(f"Итерация {iteration + 1} | Версия приложения: {version}")
            print("="*50)

            # 2. Генерируем инструмент заполнения
            print("  → Генерируем Playwright-скрипт для версии...")
            script = await generate_fill_script(html, version)
            print("  → Скрипт сгенерирован:")
            print(textwrap.indent(script, "      "))

            # 3. Выполняем сценарий
            print("  → Выполняем заполнение формы...")
            success = await execute_fill_script(page, script)

            if not success:
                print("  [✗] Не удалось выполнить скрипт. Пробуем ещё раз...")
                # Попытка №2: перегенерировать скрипт
                script = await generate_fill_script(html + "\n\n<!-- Предыдущая попытка упала, будь аккуратнее с селекторами -->", version)
                success = await execute_fill_script(page, script)
                if not success:
                    print("  [✗] Повторная попытка тоже провалилась. Останавливаемся.")
                    break

            # 4. Ждём смены версии
            print(f"  → Ждём смены версии (текущая: {version})...")
            new_version = await wait_for_version_change(page, version)

            if new_version == version:
                print(f"  [?] Версия не изменилась после отправки (осталась {version}).")
                print("      Возможно форма не была отправлена или версий больше нет.")
                # Проверяем, есть ли ещё чекбокс
                has_checkbox = await page.query_selector('input[type="checkbox"]')
                if not has_checkbox:
                    print("  [✓] Чекбокс отсутствует — возможно, это финальная версия.")
                    break
            else:
                print(f"  [✓] Версия успешно сменилась: {version} → {new_version}")

        print(f"\n{'='*50}")
        print(f"Финал: достигнута версия {version}")
        print("="*50)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())