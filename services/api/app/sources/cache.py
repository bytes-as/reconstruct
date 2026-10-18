"""Disk cache for source responses. List endpoints expire; SPL and archives do not."""

import hashlib
import time
from pathlib import Path

LIST_TTL_S = 6 * 60 * 60


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_list(self, key: str, now: float | None = None) -> bytes | None:
        path = self._list_path(key)
        if not path.is_file():
            return None
        age = (time.time() if now is None else now) - path.stat().st_mtime
        if age > LIST_TTL_S:
            return None
        return path.read_bytes()

    def put_list(self, key: str, body: bytes) -> None:
        path = self._list_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def get_immutable(self, key: str) -> bytes | None:
        path = self._immutable_path(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def put_immutable(self, key: str, body: bytes) -> None:
        path = self._immutable_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def _list_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.root / "lists" / digest

    def _immutable_path(self, key: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "@._-" else "_" for char in key)
        return self.root / "immutable" / safe
