"""Unique output directories, persistent logs and per-input outcomes."""

import logging
import platform
import sys
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import package_version
from .files import write_json


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def unique_directory(parent: Path, prefix: str) -> Path:
    if not parent.is_dir():
        raise FileNotFoundError(f"Missing input directory: {parent}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    for _ in range(10):
        path = parent / f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise FileExistsError("Cannot allocate a unique output directory")


def software_versions():
    result = {
        "mca-tools": package_version(),
        "python": platform.python_version(),
    }
    for name in (
        "readlif",
        "tifffile",
        "numpy",
        "pandas",
        "pyimagej",
        "scyjava",
        "jgo",
    ):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not installed"
    return result


class Run:
    """Publish success only after all required files have been written."""

    def __init__(self, parent, prefix, workflow, inputs, parameters):
        self.directory = unique_directory(parent, prefix)
        self.logger = logging.Logger(str(self.directory), logging.INFO)
        for handler in (
            logging.FileHandler(self.directory / "run.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ):
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            self.logger.addHandler(handler)
        self.data = {
            "schema_version": 1,
            "workflow": workflow,
            "run_id": self.directory.name,
            "source_folder": str(parent),
            "started_utc": utc_now(),
            "status": "RUNNING",
            "software": software_versions(),
            "parameters": parameters,
            "images": [
                {"input": str(p), "status": "PENDING", "outputs": []}
                for p in inputs
            ],
        }

    def save(self):
        write_json(self.directory / "run_status.json", self.data)

    def __enter__(self):
        try:
            self.save()
            self.logger.info(
                "RUN_STARTED | %s | selected=%d",
                self.directory,
                len(self.data["images"]),
            )
            self.logger.info("PARAMETERS | %s", self.data["parameters"])
            return self
        except BaseException:
            self.close()
            raise

    def record_success(self, record, outputs, **metadata):
        record.update(status="SUCCESS", outputs=outputs, **metadata)
        self.save()
        self.logger.info(
            "SAVED | %s | outputs=%d", record["input"], len(outputs)
        )

    def record_failure(self, record, error):
        record.update(status="FAILED", error=str(error))
        self.save()
        self.logger.exception("FAILED | %s", record["input"])

    def close(self):
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)

    def __exit__(self, kind, error, traceback):
        rows = self.data["images"]
        success = sum(r["status"] == "SUCCESS" for r in rows)
        failed = sum(r["status"] == "FAILED" for r in rows)
        cancelled = kind is not None and issubclass(
            kind, (KeyboardInterrupt, EOFError)
        )
        state = (
            "CANCELLED"
            if cancelled
            else "FAILED"
            if error
            else "NO_INPUT"
            if not rows
            else "PARTIAL"
            if success and failed
            else "SUCCESS"
            if success == len(rows)
            else "FAILED"
        )
        if error:
            self.data["error"] = str(error)
            self.logger.log(
                logging.WARNING if cancelled else logging.ERROR,
                "%s | %s",
                state,
                error,
                exc_info=None if cancelled else (kind, error, traceback),
            )
        self.data.update(
            status=state,
            finished_utc=utc_now(),
            counts={
                "selected": len(rows),
                "succeeded": success,
                "failed": failed,
                "unprocessed": len(rows) - success - failed,
            },
        )
        try:
            self.save()
            self.logger.info(
                "%s | succeeded=%d | failed=%d | selected=%d",
                state,
                success,
                failed,
                len(rows),
            )
        finally:
            self.close()
        return False
