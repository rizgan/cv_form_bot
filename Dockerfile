FROM python:3.12-slim

# Системные зависимости для Playwright (Chromium)
RUN apt-get update && apt-get install -y \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

CMD ["xvfb-run", "--auto-servernum", "python", "cv_form_bot.py"]
