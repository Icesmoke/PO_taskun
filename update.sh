#!/usr/bin/env bash
#
# Po_Taskun — обновление на сервере сборкой из исходников (Путь A).
#
# Что делает:
#   1. git pull origin main   — забирает свежий код
#   2. docker compose build   — пересобирает образ po-taskun:latest
#   3. docker compose up -d    — перезапускает контейнер на новом образе
#   4. docker image prune -f   — убирает «висячие» старые образы
#   5. health-check /login     — ждёт, пока приложение поднимется
#
# База (taskun.sqlite) и сессии смонтированы отдельно и при обновлении не теряются.
#
# Использование:
#   chmod +x update.sh        # один раз
#   ./update.sh               # запускать из корня репозитория
#
# Переменные окружения (необязательно):
#   BRANCH   — ветка для pull (по умолчанию main)
#   PORT     — порт, на котором проверять health-check (по умолчанию 5000)
#   SKIP_GIT — 1, чтобы не делать git pull (обновить только пересборкой)

set -euo pipefail

# Всегда работаем из папки, где лежит скрипт (корень репозитория).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BRANCH="${BRANCH:-main}"
PORT="${PORT:-5000}"

# Выбираем доступную команду compose: "docker compose" (v2) или "docker-compose" (v1).
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "ОШИБКА: не найден ни 'docker compose', ни 'docker-compose'." >&2
  exit 1
fi

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

# 1. Свежий код
if [ "${SKIP_GIT:-0}" != "1" ]; then
  log "git pull origin ${BRANCH}"
  git pull origin "${BRANCH}"
else
  log "git pull пропущен (SKIP_GIT=1)"
fi

# 2. Сборка образа
log "Сборка образа (${COMPOSE} build)"
${COMPOSE} build

# 3. Перезапуск контейнера
log "Перезапуск контейнера (${COMPOSE} up -d)"
${COMPOSE} up -d

# 4. Уборка старых образов
log "Удаление висячих образов (docker image prune -f)"
docker image prune -f >/dev/null || true

# 5. Health-check: ждём 200 на /login до 60 секунд
log "Проверка доступности http://localhost:${PORT}/login"
ok=0
for i in $(seq 1 30); do
  code="$(curl -fsS -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/login" 2>/dev/null || true)"
  if [ "${code}" = "200" ]; then
    ok=1
    break
  fi
  sleep 2
done

if [ "${ok}" = "1" ]; then
  log "Готово: приложение отвечает (HTTP 200). Обновление завершено."
  ${COMPOSE} ps
else
  echo >&2
  echo "ОШИБКА: приложение не ответило 200 за отведённое время." >&2
  echo "Последние логи контейнера:" >&2
  ${COMPOSE} logs --tail=40 || true
  exit 1
fi
