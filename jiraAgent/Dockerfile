FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn jiraAgent.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 300"]