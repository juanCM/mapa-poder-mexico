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
        if self._already_stored(response):
            return key
        response.raise_for_status()
        return key

    @staticmethod
    def _already_stored(response: httpx.Response) -> bool:
        """Un objeto repetido no es un error: la clave es el hash del contenido.

        Storage no responde 409 a un duplicado, sino 400 con `KeyAlreadyExists`
        en el cuerpo, así que mirar sólo el código HTTP rompía cualquier
        reingesta de una fuente que no ha cambiado.
        """
        if response.status_code == 409:
            return True
        if response.status_code != 400:
            return False
        try:
            body = response.json()
        except ValueError:
            return False
        return body.get("code") == "KeyAlreadyExists" or body.get("error") == "Duplicate"
