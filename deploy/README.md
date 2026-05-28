# Развёртывание Po_Taskun из Docker Registry

Готовый образ публикуется в **GitHub Container Registry** при каждом push в ветку `main`:

```
ghcr.io/icesmoke/po-taskun:latest
```

Исходный код: https://github.com/Icesmoke/PO_taskun

## Что нужно на сервере (Linux)

- Docker Engine + Docker Compose v2
- Файл `taskun.sqlite` (не в образе)
- Файл `.env` с `TASKUN_SECRET_KEY`

## Быстрый старт

```bash
mkdir -p /opt/po-taskun && cd /opt/po-taskun

# Минимальный набор для запуска (можно скопировать из репозитория deploy/)
curl -fsSL -o docker-compose.yml \
  https://raw.githubusercontent.com/Icesmoke/PO_taskun/main/deploy/docker-compose.yml
curl -fsSL -o .env.example \
  https://raw.githubusercontent.com/Icesmoke/PO_taskun/main/deploy/.env.example
cp .env.example .env
nano .env

# База данных — скопируйте с рабочей машины
# scp user@host:/path/taskun.sqlite ./taskun.sqlite

# Приватный образ GitHub: один раз войти в registry
echo "<GITHUB_PAT>" | docker login ghcr.io -u Icesmoke --password-stdin

docker compose pull
docker compose up -d
```

Приложение: `http://<сервер>:5000`

## Обновление версии

```bash
docker compose pull
docker compose up -d
```

## Публичный vs приватный образ

- Если репозиторий **приватный**, образ в GHCR тоже приватный — нужен `docker login ghcr.io` (PAT с `read:packages`).
- Чтобы образ был публичным: GitHub → репозиторий → **Packages** → `po-taskun` → **Package settings** → **Change visibility**.

## Сборка образа локально (без registry)

Из корня репозитория:

```bash
docker compose build
docker compose up -d
```
