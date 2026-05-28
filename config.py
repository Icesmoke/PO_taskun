import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _default_db_path() -> str:
    return os.path.join(BASE_DIR, "taskun.sqlite")


DB_PATH = os.environ.get("TASKUN_DB_PATH", _default_db_path())

# Template file for download/use on stage 1.
EXCEL_TEMPLATE_PATH = os.environ.get(
    "TASKUN_EXCEL_TEMPLATE_PATH",
    os.path.join(BASE_DIR, "Шаблон проектное задание 1.xlsx"),
)

# Flask session (server-side) storage
SESSION_FILE_DIR = os.environ.get("TASKUN_SESSION_DIR", os.path.join(BASE_DIR, "flask_session"))

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Cookie flags (point 6). Secure cookies only behind HTTPS (TASKUN_SESSION_SECURE=1).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = _env_flag("TASKUN_SESSION_SECURE", False)

# Development-only secret key. For real multi-user deployment set TASKUN_SECRET_KEY.
SECRET_KEY = os.environ.get("TASKUN_SECRET_KEY", "dev-secret-change-me")

# App URL settings
HOST = os.environ.get("TASKUN_HOST", "127.0.0.1")
PORT = int(os.environ.get("TASKUN_PORT", "5000"))

