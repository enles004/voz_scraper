import json
import zipfile


def write_zip(records: list[dict], zip_path: str, failures: list[dict] | None = None, json_name: str = "posts.json") -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(json_name, json.dumps(records, ensure_ascii=False, indent=2))
        if failures:
            archive.writestr("failures.json", json.dumps(failures, ensure_ascii=False, indent=2))
