"""Validate shared input configuration before starting image libraries."""

import json
from pathlib import Path


class ConfigurationError(ValueError):
    """The user supplied an invalid configuration or parameter."""


def load_folders(path: Path) -> list[Path]:
    """Resolve relative entries against the JSON and reject duplicates."""
    path = Path(path).expanduser()
    if path.name.startswith("._"):
        raise ConfigurationError("A macOS ._ file is not an input JSON.")
    path = path.resolve()
    if path.suffix.lower() != ".json":
        raise ConfigurationError("The input configuration must be JSON.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ConfigurationError(f"Cannot read '{path}': {error}") from error
    values = data.get("paths_to_files") if isinstance(data, dict) else None
    if not isinstance(values, list) or not values:
        raise ConfigurationError("Expected a nonempty 'paths_to_files' list.")
    folders = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError("Every input folder must be a string.")
        folder = Path(value).expanduser()
        if not folder.is_absolute():
            folder = path.parent / folder
        folder = folder.resolve()
        if folder.name.startswith("."):
            raise ConfigurationError(f"Hidden input folder: {folder}")
        if not folder.is_dir():
            raise ConfigurationError(f"Input folder does not exist: {folder}")
        if folder in folders:
            raise ConfigurationError(f"Repeated input folder: {folder}")
        folders.append(folder)
    return folders
