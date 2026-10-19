import json
import os
import subprocess
import sys

import pytest

from mca_tools.cli import validate_threshold
from mca_tools.config import ConfigurationError, load_folders
from mca_tools.run import Run, unique_directory


def test_paths_are_relative_to_json_and_metadata_and_duplicates_rejected(
    tmp_path, monkeypatch
):
    (tmp_path / "images").mkdir()
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": ["images"]}))
    monkeypatch.chdir(tmp_path.parent)
    assert load_folders(config) == [tmp_path / "images"]
    config.write_text(json.dumps({"paths_to_files": ["images", "./images"]}))
    with pytest.raises(ConfigurationError, match="Repeated"):
        load_folders(config)
    with pytest.raises(ConfigurationError, match="macOS"):
        load_folders(tmp_path / "._input.json")


@pytest.mark.parametrize(
    "values",
    [[float("nan")], [float("inf")], [2, 1], [0, float("nan")], [1, 2, 3]],
)
def test_invalid_thresholds_are_rejected(values):
    with pytest.raises(ConfigurationError):
        validate_threshold(values)


def test_run_names_and_cancellation_preserve_previous_results(tmp_path):
    first, second = (
        unique_directory(tmp_path, "run"),
        unique_directory(tmp_path, "run"),
    )
    assert first != second
    run = Run(tmp_path, "test", "shg_analysis", [tmp_path / "image.tif"], {})
    with pytest.raises(KeyboardInterrupt):
        with run:
            raise KeyboardInterrupt
    assert (
        json.loads((run.directory / "run_status.json").read_text())["status"]
        == "CANCELLED"
    )
    assert not run.logger.handlers


def test_help_and_version_do_not_import_imaging_or_allocate_runs(tmp_path):
    code = """
import sys
from mca_tools.cli import lif_export, shg_analysis
for function in (lif_export, shg_analysis):
    for option in ('--help', '--version'):
        try:
            function([option])
        except SystemExit as error:
            assert error.code == 0
assert not any(name in sys.modules for name in ('imagej', 'scyjava', 'numpy', 'pandas'))
"""
    runtime = tmp_path / "runtime"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "MCA_RUNTIME_HOME": str(runtime)},
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert not runtime.exists()


def test_installed_export_cli_and_resource_cleanup(tmp_path, lif_factory):
    import numpy as np

    images = tmp_path / "images"
    images.mkdir()
    lif_factory(images / "sample.lif", np.ones((2, 5, 7), dtype=np.uint16))
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": ["images"]}))
    runtime = tmp_path / "runtime"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mca_tools.cli",
            "shg1_lif_to_tif",
            "-i",
            str(config),
        ],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        env={**os.environ, "MCA_RUNTIME_HOME": str(runtime)},
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(
        next((runtime / "runs").glob("*/run.json")).read_text()
    )
    if record["process_observation"] == "COMPLETE":
        assert record["cleanup"] == "COMPLETE"
        assert not list((runtime / "tmp").iterdir())
    else:
        # Restricted PID namespaces must retain evidence, not guess ownership.
        assert record["cleanup"] == "RETAINED_FOR_INSPECTION"
        assert not record["all_observed_processes_exited"]
        assert (
            runtime / "tmp" / record["run_id"] / ".mca-owner.json"
        ).is_file()
