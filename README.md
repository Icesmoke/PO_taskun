# Po_Taskun

Веб-приложение на **Flask** (Jinja2, SQLite) для учёта проектов, задач, доп. затрат и отчётов.

## Состояние (сентябрь 2026)

Рабочий контур — Flask. Эксперимент Django + React лежит в `_archive/` и в продакшен не входит.

**Ветка `main`:** после [PR #1](https://github.com/Icesmoke/PO_taskun/pull/1) (август 2026). Образ `ghcr.io/icesmoke/po-taskun:latest` собирается GitHub Actions при push в `main`.

| Готово | Как сейчас |
|--------|------------|
| Проекты | Список этапов с фильтрами и сортировкой. Директор создаёт этапы и правит **все поля**, кроме номера договора и этапа |
| Задачи | Карточки в карточке этапа: полное / частичное редактирование, загрузка из Excel, черновик в сессии до «Сохранить» |
| Отчёты | Гантт (период не больше 31 дня). Утилизация и экономика проектов — только директор; в утилизации все активные сотрудники, не только с задачами. **Выполнение задач** — иерархия пользователь → проект → задача, светофор сроков; доступен всем ролям |
| Ввод данных | Премии, командировки, подрядчики: создание, правка и удаление в диалогах |
| Пользователи | Администратор создаёт учётки и отключает (`enabled = 0`). Самого себя отключить нельзя |
| Интерфейс | Адаптивный shell, светлая/тёмная тема, карточки вместо широких таблиц, Flatpickr у всех полей дат (в диалогах календарь привязан к полю) |
| Деплой | Docker Compose, GHCR, `update.sh` для пересборки на сервере из исходников |

**Роли и видимость**

| Роль | Проекты | Задачи | Отчёты | Ввод данных | Пользователи |
|------|---------|--------|--------|-------------|--------------|
| Директор | все этапы; создание и полная правка | полное редактирование + Excel | Гантт, утилизация, экономика, выполнение задач | да | нет |
| Руководитель проекта | только свои этапы (`project_chief`) | полное редактирование + Excel | Гантт по своим проектам; выполнение задач по своим этапам | нет | нет |
| Консультант | этапы, где есть его задачи | даты, комментарий, рабочий файл, статус | выполнение задач (свои задачи) | нет | нет |
| Администратор | нет (сразу панель пользователей) | нет | выполнение задач | нет | создание и отключение |

Профиль (ФИО, роль, АРМ) доступен всем; фото в пилоте нет.

**Ограничения пилота:** нет автотестов у Flask-приложения; схема SQLite не создаётся из кода — нужна готовая `taskun.sqlite`; пароли хранятся в БД (Werkzeug или открытый текст для совместимости).

## Возможности

| Раздел | Что делает |
|--------|------------|
| **Проекты** | Фильтры (вид, исполнитель, статус, РП, период), сортировка, карточка этапа |
| **Проектное задание** | Просмотр / частичное или полное редактирование, загрузка из Excel, скачивание шаблона |
| **Отчёты** | Гантт; утилизация и экономика — только директор; выполнение задач — все роли |
| **Ввод данных** | Премии, командировки, подрядчики (директор) |
| **Пользователи** | Создание и отключение учёток (администратор) |

**Роли (АРМ):** Директор · Руководитель проекта · Консультант · Администратор.

Экономика проектов: совокупные затраты = трудозатраты по **рабочим дням** (пн–пт, праздники RU) × ставка + премии + командировки + подрядчики (`app.py`, отчёт `econ`).

## Что в репозитории

- Исходный код: `app.py`, `db.py`, `reports_service.py`, `workdays.py`, `excel_parser.py`, `utils.py`, `config.py`
- Шаблоны Jinja2 (`templates/`), статика (`static/css`, `static/js`)
- Excel-шаблоны в корне (в образ Docker попадают вместе с кодом). По умолчанию используется `Шаблон проектное задание 1.xlsx`
- **Docker**: образ без БД — `taskun.sqlite` монтируется с хоста
- `update.sh` — обновление сервера: `git pull` + пересборка Compose
- Архив эксперимента Django+React: `_archive/` (для запуска не нужен)

**Не в репозитории** (см. `.gitignore`):

- `taskun.sqlite` — БД с паролями и данными (переносите отдельно на сервер)
- `.env` — секреты

## Структура кода (кратко)

```
app.py              # маршруты, RBAC, сборка отчётов (в т.ч. экономика)
db.py               # SQL-доступ к SQLite (без ORM)
reports_service.py  # модели Гантта / утилизации
workdays.py         # рабочие дни (пн–пт, праздники RU)
excel_parser.py     # разбор xlsx задач
templates/          # страницы Jinja
static/js/          # theme, фильтры (Tom Select), календарь дат (Flatpickr)
update.sh           # пересборка контейнера на сервере
```

Интерфейс: Bulma, Inter, Tom Select, Flatpickr. Сессии — файловые (`Flask-Session`).

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

docker compose build
docker compose up -d
```

Приложение: `http://<IP-сервера>:5000`

Остановка: `docker compose down`

Обновление из исходников на сервере: `./update.sh` (pull `main`, сборка, health-check `/login`).

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
| `TASKUN_HOST` / `TASKUN_PORT` | Хост и порт (локальный запуск, по умолчанию `127.0.0.1:5000`) |

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

Приложение: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Структура данных

Файл `taskun.sqlite` не коммитится. Для нового сервера:

1. Скопируйте рабочую БД с существующей установки, **или**
2. Подготовьте пустую БД с нужной схемой (таблицы `workers`, `projects`, `tasks`, `bonuses`, `voyages`, `contracters` и каталоги статусов)

Без `taskun.sqlite` контейнер завершится с ошибкой на старте (проверка в `docker-entrypoint.sh`).

## Архив Django + React

Код в `_archive/django-react-migration/` — отложенный эксперимент, для продакшена не используется.

## Лицензия

Внутренний проект; уточните условия использования у владельца репозитория.
