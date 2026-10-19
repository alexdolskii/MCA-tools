import json
import os
import subprocess
import sys


def test_invalid_manual_noninteractive_input_exits_without_fiji(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": [str(source)]}))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mca_tools.cli",
            "shg2_intden_assay",
            "-i",
            str(config),
            "--projection",
            "max",
            "--threshold-mode",
            "manual",
            "--yes",
        ],
        env={**os.environ, "MCA_WORKER": "1"},
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Noninteractive" in result.stderr
    assert "Initializing" not in result.stdout


def test_failed_export_keeps_owned_diagnostics_and_unrelated_files(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    (source / "bad.lif").write_bytes(b"broken")
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": [str(source)]}))
    runtime = tmp_path / "runtime"
    unrelated = runtime / "tmp" / "unrelated"
    unrelated.mkdir(parents=True)
    (unrelated / "keep.txt").write_text("keep")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mca_tools.cli",
            "shg1_lif_to_tif",
            "-i",
            str(config),
        ],
        env={**os.environ, "MCA_RUNTIME_HOME": str(runtime)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    record = json.loads(
        next((runtime / "runs").glob("*/run.json")).read_text()
    )
    assert record["cleanup"] == "RETAINED_FOR_INSPECTION"
    assert (unrelated / "keep.txt").read_text() == "keep"
    assert (runtime / "tmp" / record["run_id"] / ".mca-owner.json").is_file()
