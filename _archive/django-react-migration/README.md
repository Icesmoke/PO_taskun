# Django + React (NextUI) — архив

Этот каталог **не используется** в текущей работе. Здесь сохранён каркас миграции на Django REST + JWT и React (Vite + NextUI).

## Содержимое

- `backend/` — проект Django (`taskun_backend`, приложение `api`, `accounts` с JWT и импортом пользователей из `taskun.sqlite`).
- `frontend/` — SPA на React.

## Если понадобится снова

1. Установить зависимости: `backend/requirements.txt`, во `frontend` — `npm install`.
2. Миграции: из каталога `backend` выполнить `manage.py migrate` (при смене модели пользователя может понадобиться удалить локальный `db.sqlite3`).
3. Импорт пользователей: `manage.py import_workers_from_legacy` (путь к `taskun.sqlite` — родитель каталога `backend` в корне репозитория Po_Taskun).

Подробности по эндпоинтам и ветке разработки смотрите в истории коммитов ветки `django-react-migration`.
