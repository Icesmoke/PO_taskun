#!/bin/sh
set -e
mkdir -p /data/flask_session
chown -R app:app /data

# Пустой файл SQLite без схемы даёт 500 на /login — проверяем до запуска Gunicorn
python3 <<'PY'
import os
import sqlite3
import sys

path = os.environ.get("TASKUN_DB_PATH", "/data/taskun.sqlite")
con = None
try:
    con = sqlite3.connect(path)
    con.execute("SELECT 1 FROM workers LIMIT 1")
except Exception as e:
    print("Po_Taskun: база данных недоступна или без схемы:", e, file=sys.stderr)
    print("", file=sys.stderr)
    print("Нужен файл taskun.sqlite с таблицами (в т.ч. workers).", file=sys.stderr)
    print("Смонтируйте taskun.sqlite с хоста (docker-compose volumes).", file=sys.stderr)
    print("  volumes:", file=sys.stderr)
    print("    - ./taskun.sqlite:/data/taskun.sqlite", file=sys.stderr)
    print("Путь в контейнере:", path, file=sys.stderr)
    sys.exit(1)
finally:
    if con is not None:
        con.close()
PY

exec gosu app gunicorn \
  --bind "${TASKUN_HOST:-0.0.0.0}:${TASKUN_PORT:-5000}" \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  wsgi:app
