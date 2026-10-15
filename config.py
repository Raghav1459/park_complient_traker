import os
from pathlib import Path

INSTANCE_DIR = Path(__file__).resolve().parent / "instance"


class Config:
    SECRET_KEY = os.environ.get("PARKCARE_SECRET_KEY")
    if not SECRET_KEY:
        INSTANCE_DIR.mkdir(exist_ok=True)
        key_file = INSTANCE_DIR / "secret_key"
        if key_file.exists():
            SECRET_KEY = key_file.read_text(encoding="utf-8").strip()
        else:
            import secrets
            SECRET_KEY = secrets.token_urlsafe(48)
            key_file.write_text(SECRET_KEY, encoding="utf-8")
    DATABASE = INSTANCE_DIR / "parkcare.sqlite3"
    UPLOAD_FOLDER = INSTANCE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 + 256 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
