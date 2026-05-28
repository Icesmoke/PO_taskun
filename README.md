# Po_Taskun

Веб-приложение на **Flask** (Jinja2, SQLite) для учёта проектов, задач и отчётов.

## Что в репозитории

- Исходный код приложения (`app.py`, `db.py`, шаблоны, статика)
- **Docker**: образ без базы данных — `taskun.sqlite` монтируется с хоста
- Архив эксперимента Django+React: `_archive/` (не нужен для запуска)

**Не в репозитории** (см. `.gitignore`):

- `taskun.sqlite` — БД с паролями и данными (переносите отдельно на сервер)
- `Шаблон проектное задание 1.xlsx` — шаблон Excel для загрузки задач (положите рядом с проектом или задайте `TASKUN_EXCEL_TEMPLATE_PATH`)
- `.env` — секреты

## Быстрый старт (Linux, Docker)

Требования: Docker Engine и Docker Compose v2.

```bash
git clone https://github.com/Icesmoke/PO_taskun.git
cd PO_taskun

# Секреты (обязательно смените TASKUN_SECRET_KEY)
cp .env.example .env
nano .env

# База данных — скопируйте свой taskun.sqlite в каталог проекта
# (файл должен содержать таблицу workers и остальную схему)
ls -la taskun.sqlite

# Шаблон Excel (если нужна загрузка из xlsx)
# cp /path/to/Шаблон\ проектное\ задание\ 1.xlsx .

docker compose build
docker compose up -d
```

Приложение: `http://<IP-сервера>:5000`

Остановка: `docker compose down`

## Docker-образ в GitHub Container Registry

При push в `main` GitHub Actions собирает образ и публикует его:

**`ghcr.io/icesmoke/po-taskun:latest`**

Просмотр: репозиторий → **Packages** → `po-taskun`.

### Развёртывание только контейнера (без сборки на сервере)

```bash
git clone https://github.com/Icesmoke/PO_taskun.git
cd PO_taskun
cp .env.example .env && nano .env
# положите taskun.sqlite в каталог

# Приватный репозиторий: docker login ghcr.io -u Icesmoke
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

Минимальный набор файлов для сервера — каталог [`deploy/`](deploy/README.md) (compose + `.env.example`).

Подробнее: [deploy/README.md](deploy/README.md).

### Переменные окружения

| Переменная | Описание |
|------------|----------|
| `TASKUN_SECRET_KEY` | Ключ подписи сессий Flask (длинная случайная строка) |
| `TASKUN_DB_PATH` | Путь к SQLite в контейнере (по умолчанию `/data/taskun.sqlite`) |
| `TASKUN_SESSION_DIR` | Каталог файловых сессий |
| `TASKUN_SESSION_SECURE` | `1` за HTTPS (secure cookie) |
| `TASKUN_EXCEL_TEMPLATE_PATH` | Путь к xlsx-шаблону в контейнере |

### Перенос образа без Git

На машине сборки:

```bash
docker save po-taskun:latest -o po-taskun-latest.tar
```

На сервере:

```bash
docker load -i po-taskun-latest.tar
docker run -d --name po-taskun -p 5000:5000 \
  -v /opt/po-taskun/taskun.sqlite:/data/taskun.sqlite \
  -v po-taskun-session:/data/flask_session \
  -e TASKUN_SECRET_KEY='...' \
  po-taskun:latest
```

## Локальный запуск без Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.lock

export TASKUN_SECRET_KEY='dev-only-change-me'
# taskun.sqlite — в корне проекта
python app.py
```

Отладка: `FLASK_DEBUG=1 python app.py` (только на dev-машине).

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.lock
$env:TASKUN_SECRET_KEY = "dev-only"
python app.py
```

## Структура данных

Файл `taskun.sqlite` не коммитится. Для нового сервера:

1. Скопируйте рабочую БД с существующей установки, **или**
2. Подготовьте пустую БД с нужной схемой (таблицы `workers`, `projects`, `tasks` и др.)

Без `taskun.sqlite` контейнер завершится с ошибкой на старте (проверка в `docker-entrypoint.sh`).

## Архив Django + React

Код в `_archive/django-react-migration/` — отложенный эксперимент, для продакшена не используется.

## Лицензия

Внутренний проект; уточните условия использования у владельца репозитория.
