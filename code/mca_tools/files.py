"""File inventories, portable names and atomic metadata publication."""

import hashlib
import json
import math
import os
import re
import uuid
from pathlib import Path


def image_files(folder: Path, extensions) -> list[Path]:
    """Use one inventory for counts and processing, excluding dot files."""
    return sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file()
            and not p.name.startswith(".")
            and p.suffix.lower() in extensions
        ),
        key=lambda p: (p.name.casefold(), p.name),
    )


def safe_label(value: str) -> str:
    """Normalize scene names without allowing embedded path separators."""
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "_", value).strip(". ")
    label = label or "unnamed"
    if len(label.encode("utf-8")) > 100:
        suffix = hashlib.sha256(value.encode()).hexdigest()[:10]
        label = label.encode()[:80].decode("utf-8", errors="ignore") + suffix
    return label


def sha256_file(path: Path) -> str:
    """Hash large images without loading them into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_safe(value):
    """Preserve available metadata while representing missing numbers as null."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def write_json(path: Path, data) -> None:
    """Replace JSON atomically on its destination filesystem."""
    write_text(
        path, json.dumps(json_safe(data), indent=2, allow_nan=False) + "\n"
    )


def write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def output_record(path: Path, root: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def checked_output(root: Path, record: dict) -> Path:
    """Validate a recorded output before a downstream stage uses it."""
    relative = Path(record["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Output path leaves its recorded run")
    path = root / relative
    if any(part.startswith(".") for part in relative.parts):
        raise ValueError("Hidden output in run inventory")
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Linked output leaves its recorded run")
    if (
        not path.is_file()
        or path.stat().st_size != record["size"]
        or sha256_file(path) != record["sha256"]
    ):
        raise ValueError(f"Missing or changed output: {path}")
    return path
