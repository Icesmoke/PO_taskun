import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _default_db_path() -> str:
    # Keep exactly as in TЗ. For portability allow override via env var.
    return r"C:\Users\Master\Cursor projects\PO_taskun\taskun.sqlite"


DB_PATH = os.environ.get("TASKUN_DB_PATH", _default_db_path())

# Template file for download/use on stage 1.
EXCEL_TEMPLATE_PATH = os.environ.get(
    "TASKUN_EXCEL_TEMPLATE_PATH",
    r"C:\Users\Master\Cursor projects\PO_taskun\Шаблон проектное задание 1.xlsx",
)

# Flask session (server-side) storage
SESSION_FILE_DIR = os.environ.get("TASKUN_SESSION_DIR", os.path.join(BASE_DIR, "flask_session"))

# Development-only secret key. For real multi-user deployment set TASKUN_SECRET_KEY.
SECRET_KEY = os.environ.get("TASKUN_SECRET_KEY", "dev-secret-change-me")

# App URL settings
HOST = os.environ.get("TASKUN_HOST", "127.0.0.1")
PORT = int(os.environ.get("TASKUN_PORT", "5000"))

