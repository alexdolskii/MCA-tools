"""Select the latest verified export; never treat an empty folder as success."""

import json
from dataclasses import dataclass
from pathlib import Path

from .files import checked_output, image_files


@dataclass
class ExportSelection:
    directory: Path
    files: list[Path]
    status: str
    warnings: list[str]


def validate_export(directory, channel=1, allow_partial=False):
    status_path = directory / "run_status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("workflow") != "lif_export":
        raise ValueError("Not a supported LIF export record")
    allowed = {"SUCCESS", "PARTIAL"} if allow_partial else {"SUCCESS"}
    if data.get("status") not in allowed:
        raise ValueError(f"Export status is {data.get('status')!r}")
    records = data.get("images")
    if not isinstance(records, list) or not records:
        raise ValueError("No input audit in export")
    statuses = [record.get("status") for record in records]
    if any(state not in {"SUCCESS", "FAILED"} for state in statuses):
        raise ValueError("Export contains unfinished inputs")
    successes = statuses.count("SUCCESS")
    expected = (
        "SUCCESS"
        if successes == len(records)
        else "PARTIAL"
        if successes
        else "FAILED"
    )
    if (
        expected != data["status"]
        or data.get("counts", {}).get("succeeded") != successes
    ):
        raise ValueError("Export status disagrees with its input audit")
    files = []
    for record in records:
        if record["status"] != "SUCCESS":
            continue
        outputs = record.get("outputs", [])
        if not outputs:
            raise ValueError("Successful LIF has no saved outputs")
        verified = [checked_output(directory, item) for item in outputs]
        selected = [
            p
            for p in verified
            if p.parent.name == f"channel_{channel}"
            and p.suffix.lower() in {".tif", ".tiff"}
        ]
        for path in selected:
            if path.with_suffix(path.suffix + ".json") not in verified:
                raise ValueError(
                    "Exported TIFF has no verified metadata sidecar"
                )
        files.extend(selected)
    if not files or len(files) != len(set(files)):
        raise ValueError("No selected channel images or duplicate outputs")
    return sorted(files), data["status"]


def select_export(folder, channel=1, allow_partial=False, allow_legacy=False):
    warnings = []
    candidates = sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_dir()
            and not p.is_symlink()
            and p.name.startswith("output_")
            and not p.name.startswith("output_processed_")
        ),
        key=lambda p: p.name,
        reverse=True,
    )
    for directory in candidates:
        try:
            if allow_legacy and not (directory / "run_status.json").exists():
                channel_folder = directory / f"channel_{channel}"
                files = image_files(channel_folder, {".tif", ".tiff", ".nd2"})
                if not files:
                    raise ValueError("No legacy channel images")
                warnings.append(
                    f"LEGACY_UNVERIFIED: {directory}; completion is unknown"
                )
                return ExportSelection(
                    directory, files, "LEGACY_UNVERIFIED", warnings
                )
            files, status = validate_export(directory, channel, allow_partial)
        except (OSError, ValueError, KeyError, TypeError) as error:
            warnings.append(f"Skipped {directory.name}: {error}")
            continue
        if status == "PARTIAL":
            warnings.append(
                "PARTIAL export: only files from successful LIF inputs are selected"
            )
        return ExportSelection(directory, files, status, warnings)
    details = "; ".join(warnings) or "no export directories found"
    raise ValueError(
        f"No verified channel_{channel} export in {folder}: {details}"
    )
