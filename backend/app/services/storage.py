from pathlib import Path
from uuid import uuid4
from app.config import settings
class ImageStorage:
    def __init__(self): Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    def save(self, filename: str, data: bytes) -> str:
        ext = Path(filename).suffix.lower() or ".jpg"
        name = f"{uuid4().hex}{ext}"
        path = Path(settings.storage_dir) / name
        path.write_bytes(data)
        return str(path)
