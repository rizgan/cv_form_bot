FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Нужен xvfb-run для запуска Chromium в виртуальном дисплее.
RUN apt-get update && apt-get install -y \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["xvfb-run", "--auto-servernum", "python", "cv_form_bot.py"]
