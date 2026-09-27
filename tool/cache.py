import hashlib
import json
from pathlib import Path


def file_fingerprint(path: str | Path) -> dict[str, str | int]:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = file_path.stat()
    return {
        "path": str(file_path.resolve()),
        "size": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def write_metadata(path: str | Path, metadata: dict) -> None:
    Path(path).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
