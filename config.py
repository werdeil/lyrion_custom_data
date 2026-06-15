import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

    # Lyrion Music Server
    LYRION_HOST = os.getenv("LYRION_HOST")

    # Database paths
    DB_PATH = os.path.join(os.getenv("DB_DIR", ""), "library.db")
    DB_PERSIST_PATH = os.path.join(os.getenv("DB_PERSIST_DIR", ""), "persist.db")

    # Custom data directory
    CUSTOM_DATA_DIR = os.getenv("CUSTOM_DATA_DIR", "/opt/scripts/custom_data")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "1111"))

    # Development helpers: when DEV=1, Jinja re-reads templates from disk on
    # every request and static files are served with no cache, so HTML/CSS
    # edits show up on a simple page refresh (no worker/container restart).
    DEV = os.getenv("DEV", "").lower() in ("1", "true", "yes")
    TEMPLATES_AUTO_RELOAD = DEV
    SEND_FILE_MAX_AGE_DEFAULT = 0 if DEV else None
