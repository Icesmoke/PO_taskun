# Po_Taskun — Flask-приложение
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /data/flask_session \
    && groupadd -r app \
    && useradd -r -g app -d /app app \
    && chown app:app /data

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY . .
RUN chown -R app:app /app

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV TASKUN_DB_PATH=/data/taskun.sqlite \
    TASKUN_SESSION_DIR=/data/flask_session \
    TASKUN_EXCEL_TEMPLATE_PATH="/app/Шаблон проектное задание 1.xlsx" \
    TASKUN_HOST=0.0.0.0 \
    TASKUN_PORT=5000

EXPOSE 5000

# БД монтируется с хоста (docker-compose volumes), в образ не включается.
ENTRYPOINT ["/docker-entrypoint.sh"]
