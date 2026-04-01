# Po_Taskun

Рабочее приложение — **Flask** (шаблоны Jinja2, SQLite `taskun.sqlite`).

## Запуск

```powershell
cd "C:\Users\Master\Cursor projects\PO_taskun"
& "C:\Users\Master\Cursor projects\.venv\Scripts\python.exe" app.py
```

Откройте в браузере: `http://127.0.0.1:5000`

## Зависимости

Используется venv: `C:\Users\Master\Cursor projects\.venv\Scripts\python.exe`. При необходимости:

```powershell
& "C:\Users\Master\Cursor projects\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

## Архив Django + React

Эксперимент с миграцией на Django и React **отложен**. Код лежит в `_archive/django-react-migration/` и для повседневной работы не нужен.

## Данные

Файл `taskun.sqlite` с данными и паролями в репозиторий не коммитится (см. `.gitignore`).
