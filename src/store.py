import hashlib
import json
import os
import shutil


class CheckpointStore:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir

    def _path(self, url: str) -> str:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.work_dir, f"{digest}.json")

    def ensure(self) -> None:
        os.makedirs(self.work_dir, exist_ok=True)

    def has(self, url: str) -> bool:
        return os.path.exists(self._path(url))

    def load(self, url: str) -> dict | None:
        path = self._path(url)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def is_complete(self, url: str) -> bool:
        data = self.load(url)
        return data is not None and not data.get("failed")

    def save(self, url: str, record: dict, failed: list) -> None:
        self.ensure()
        path = self._path(url)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"record": record, "failed": failed}, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def clear(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)
