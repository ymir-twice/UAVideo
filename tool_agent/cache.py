import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class DiskCache:
    root: Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def key_for_file(self, file_path: str, params: dict) -> str:
        p = dict(params)
        p["file_hash"] = _sha256_file(file_path)
        payload = json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return _sha256_bytes(payload)

    def key_for_bytes(self, b: bytes, params: dict) -> str:
        p = dict(params)
        p["bytes_hash"] = _sha256_bytes(b)
        payload = json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return _sha256_bytes(payload)

    def get_text(self, key: str) -> Optional[str]:
        p = self.root / f"{key}.txt"
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")

    def set_text(self, key: str, text: str) -> None:
        tmp = self.root / f"{key}.txt.tmp"
        dst = self.root / f"{key}.txt"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dst)

    def get_json(self, key: str) -> Optional[Any]:
        p = self.root / f"{key}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def set_json(self, key: str, obj: Any) -> None:
        tmp = self.root / f"{key}.json.tmp"
        dst = self.root / f"{key}.json"
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, dst)

