import datetime as dt
import hmac
import re
from typing import Optional

from werkzeug.security import check_password_hash

from dateutil import parser as date_parser


# Accept both 31-03-2026 and 31.03.2026 (we display with dots).
DATE_RE_DD_MM_YYYY = re.compile(r"^\s*(\d{2})[.-](\d{2})[.-](\d{4})\s*$")


def format_date_ddmmyyyy(value: Optional[object]) -> str:
    """
    Convert DB/Excel values to `dd.mm.YYYY` for UI.
    Supports `datetime/date` and `YYYY-MM-DD` strings.
    """
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, dt.date):
        return value.strftime("%d.%m.%Y")

    s = str(value).strip()
    if not s:
        return ""

    # SQLite TIMESTAMP often comes as 'YYYY-MM-DD HH:MM:SS'
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            d = dt.datetime.fromisoformat(s.replace(" ", "T")).date()
            return d.strftime("%d.%m.%Y")
        except Exception:
            pass

    # Try strict dd-mm-YYYY / dd.mm.YYYY
    m = DATE_RE_DD_MM_YYYY.match(s)
    if m:
        d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return d.strftime("%d.%m.%Y")

    # Fallback parse (best-effort)
    try:
        d = date_parser.parse(s, dayfirst=True).date()
        return d.strftime("%d.%m.%Y")
    except Exception:
        return s


def parse_date_from_ddmmyyyy(value: str) -> dt.date:
    value = (value or "").strip()
    if not value:
        raise ValueError("Дата не задана")
    m = DATE_RE_DD_MM_YYYY.match(value)
    if not m:
        raise ValueError("Неверный формат даты, ожидается dd.mm.YYYY")
    return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def normalize_sqlite_timestamp_date(value: object) -> str:
    """
    SQLite column is declared as TIMESTAMP. We store `YYYY-MM-DD 00:00:00`.
    """
    if value is None or str(value).strip() == "":
        return ""
    if isinstance(value, dt.datetime):
        d = value.date()
    elif isinstance(value, dt.date):
        d = value
    else:
        s = str(value).strip()
        # Accept 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', dd-mm-YYYY, or dd.mm.YYYY.
        s2 = format_date_ddmmyyyy(s)
        d = parse_date_from_ddmmyyyy(s2)
    return f"{d.isoformat()} 00:00:00"


def verify_worker_password(stored: Optional[object], provided: Optional[str]) -> bool:
    """
    Accepts plain-text passwords or Werkzeug hashes (pbkdf2 / scrypt) in DB.
    Empty stored password never matches.
    """
    p = "" if provided is None else str(provided)
    if stored is None:
        return False
    s = str(stored).strip()
    if not s:
        return False
    if s.startswith("pbkdf2:") or s.startswith("scrypt:"):
        try:
            return bool(check_password_hash(s, p))
        except Exception:
            return False
    return hmac.compare_digest(s, p)

