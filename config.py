import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

    # Lyrion Music Server
    LYRION_HOST = os.getenv("LYRION_HOST")

    # Database paths
    DB_PATH = os.getenv("DB_PATH")
    DB_PERSIST_PATH = os.getenv("DB_PERSIST_PATH")

    # Custom data directory
    CUSTOM_DATA_DIR = os.getenv("CUSTOM_DATA_DIR", "/opt/scripts/custom_data")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "1111"))
