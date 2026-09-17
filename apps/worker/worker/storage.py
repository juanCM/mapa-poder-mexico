from pathlib import Path

import httpx


class LocalSnapshotStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, content: bytes, mime_type: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)


class SupabaseSnapshotStorage:
    def __init__(self, url: str, service_key: str, bucket: str):
        self.url = url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket

    def put(self, key: str, content: bytes, mime_type: str) -> str:
        endpoint = f"{self.url}/storage/v1/object/{self.bucket}/{key}"
        response = httpx.post(
            endpoint,
            content=content,
            headers={
                # Las secret keys modernas (sb_secret_...) no son JWT. Enviarlas
                # como Bearer provoca "Invalid Compact JWS" en Storage.
                "apikey": self.service_key,
                "Content-Type": mime_type,
                "x-upsert": "false",
            },
            timeout=30,
        )
        if response.status_code == 409:
            return key
        response.raise_for_status()
        return key
