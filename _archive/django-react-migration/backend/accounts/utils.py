import hmac
from typing import Optional

from werkzeug.security import check_password_hash


def verify_legacy_password(stored: Optional[object], provided: Optional[str]) -> bool:
    """
    Совпадает с логикой Flask `utils.verify_worker_password`: plain или Werkzeug (pbkdf2/scrypt).
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
