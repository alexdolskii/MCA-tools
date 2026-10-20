import json
import os
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import tifffile

from mca_tools.calibration import Calibration
from mca_tools.fiji_config import FIJI_ENDPOINT
from mca_tools.lif_export import save_stack
from mca_tools.run import Run

pytestmark = pytest.mark.imagej


def test_installed_commands_complete_with_full_fiji(
    native_imagej, lif_factory, tmp_path
):
    """Exercise cold JVM startup, the real gateway and worker exit via CLI."""
    if native_imagej is None:
        pytest.skip("Full Fiji is required; offline ImageJ1 is insufficient")
    import scyjava

    # The offline ImageJ1 fixture cannot satisfy this Bio-Formats check.
    assert scyjava.jimport("loci.formats.ImageReader") is not None
    source = tmp_path / "source"
    source.mkdir()
    pixels = np.zeros((3, 5, 7), dtype=np.uint16)
    pixels[:, 1:3, 2:5] = np.array([10, 20, 30], dtype=np.uint16)[
        :, None, None
    ]
    for name in ("sample", "sample_MERGED"):
        lif_path = lif_factory(source / f"{name}.lif", pixels)
        with lif_path.open("ab") as stream:
            stream.write(bytes(512))
    (source / "._sample.lif").write_bytes(b"ignored metadata")
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": [str(source)]}))
    env = {**os.environ, "MCA_RUNTIME_HOME": str(tmp_path / "runtime")}
    env.pop("MCA_WORKER", None)

    def run(command, *arguments):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mca_tools.cli",
                command,
                "-i",
                str(config),
                *arguments,
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    run("shg1_lif_to_tif")
    export = next(source.glob("output_*"))
    audit = json.loads((export / "run_status.json").read_text())
    assert audit["status"] == "SUCCESS"
    assert audit["counts"]["selected"] == 2
    channel = export / "channel_1"
    metadata = json.loads(next(channel.glob("*.tif.json")).read_text())
    assert metadata["lif_structure"]["verified_zero_padding_bytes"] == 512
    previous = set()
    for method, expected_signal in (("max", 180), ("sum", 360)):
        result = run(
            "shg2_intden_assay",
            "--input-source",
            "export",
            "--projection",
            method,
            "--threshold",
            "1",
            "10000",
            "--yes",
        )
        assert "IMAGEJ_READY" in result.stdout
        outputs = set(channel.glob("Mask_Intensity_Area_Results_*"))
        new_outputs = outputs - previous
        assert len(new_outputs) == 1
        output = new_outputs.pop()
        previous = outputs
        status = json.loads((output / "run_status.json").read_text())
        assert status["status"] == "SUCCESS"
        assert status["parameters"]["fiji_endpoint"] == FIJI_ENDPOINT
        for library in ("pyimagej", "scyjava", "jgo", "imagej1", "java"):
            assert status["software"][library] not in (None, "not installed")
        table = pd.read_csv(
            output / "Tables" / "Area_measurements_individual.csv"
        )
        merged = pd.read_csv(
            output / "Tables" / "Area_measurements_merged.csv"
        )
        assert len(merged) == 1
        assert merged.iloc[0]["Image_Group"] == "merged"
        assert status["counts"]["selected"] == 2
        assert len(table) == 1
        row = table.iloc[0]
        assert row["Total_Area_px2"] == 6
        assert row["Total_Area_um2"] == pytest.approx(0.75)
        assert row["Integrated_Density_raw"] == expected_signal
        assert row["Projection_Method"] == method.upper()

    # Independent TIFF mode must work through the real installed worker too.
    external = tmp_path / "external"
    external.mkdir()
    tiff = external / "single.tif"
    tifffile.imwrite(
        tiff,
        pixels,
        imagej=True,
        metadata={"axes": "ZYX", "unit": "um", "spacing": 2},
        resolution=(2, 4),
    )
    config.write_text(json.dumps({"paths_to_files": [str(tiff)]}))
    run(
        "shg2_intden_assay",
        "--input-source",
        "tiff",
        "--projection",
        "max",
        "--threshold",
        "1",
        "--yes",
    )
    result = next(external.glob("Mask_Intensity_Area_Results_*"))
    table = pd.read_csv(result / "Tables" / "Area_measurements_individual.csv")
    assert table.iloc[0]["Input_Source"] == "tiff"
    assert table.iloc[0]["Total_Area_um2"] == pytest.approx(0.75)


def process(
    tmp_path,
    pixels,
    method,
    calibration=Calibration(0.5, 0.25, 2, "test"),
    name="sample",
):
    from mca_tools.shg_analysis import process_image

    path = tmp_path / f"{name}.tif"
    save_stack(path, pixels, calibration, {})
    run = Run(tmp_path, "SHG", "shg_analysis", [path], {})
    with run:
        for directory in ("Tables", "Masks", "Masked_Images", "Metadata"):
            (run.directory / directory).mkdir()
        row, outputs = process_image(path, run, method, "manual", (1, 100000))
        run.record_success(run.data["images"][0], outputs)
    return row, run.directory


@pytest.mark.parametrize("method,expected", [("max", 30), ("sum", 60)])
@pytest.mark.parametrize("name", ["image", "merged_image"])
def test_native_rectangular_pixels_projection_and_physical_area(
    native_imagej, tmp_path, method, expected, name
):
    pixels = np.zeros((3, 5, 7), dtype=np.uint16)
    pixels[:, 1:3, 2:5] = np.array([10, 20, 30], dtype=np.uint16)[
        :, None, None
    ]
    row, folder = process(tmp_path, pixels, method, name=name)
    assert (row["Original_Width_px"], row["Original_Height_px"]) == (7, 5)
    assert row["Particle_Count"] == 1
    assert row["Total_Area_px2"] == 6
    assert row["Total_Area_um2"] == pytest.approx(0.75)
    assert row["Mean_Intensity"] == expected
    assert row["Integrated_Density_raw"] == expected * 6
    assert row["Integrated_Density_um2"] == pytest.approx(expected * 0.75)
    with tifffile.TiffFile(folder / f"{name}_processed.tif") as tif:
        projected = tif.asarray()
        np.testing.assert_array_equal(
            projected,
            pixels.max(axis=0) if method == "max" else pixels.sum(axis=0),
        )
        assert projected.dtype == (
            np.uint16 if method == "max" else np.float32
        )
    for path in [
        folder / f"{name}_processed.tif",
        folder / "Masks" / f"{name}_mask.tif",
        folder / "Masked_Images" / f"{name}_masked.tif",
    ]:
        with tifffile.TiffFile(path) as tif:
            assert tif.asarray().shape == (5, 7)
            assert "input_sha256" in str(tif.imagej_metadata.get("Info"))
            assert tif.imagej_metadata["unit"] in {
                "um",
                "micron",
                "\u00b5m",
                r"\u00B5m",
            }
            assert tif.pages[0].tags["XResolution"].value[0] / tif.pages[
                0
            ].tags["XResolution"].value[1] == pytest.approx(2)
            assert tif.pages[0].tags["YResolution"].value[0] / tif.pages[
                0
            ].tags["YResolution"].value[1] == pytest.approx(4)


def test_missing_calibration_and_zero_signal_are_distinct(
    native_imagej, tmp_path
):
    row, _ = process(
        tmp_path, np.zeros((1, 5, 7), dtype=np.uint16), "sum", Calibration()
    )
    assert row["Total_Area_px2"] == 0
    assert row["Integrated_Density_raw"] == 0
    assert row["Total_Area_um2"] is None
    assert row["Calibration_Status"] == "MISSING_XY_CALIBRATION"
    assert row["Projection_Bit_Depth"] == 32


def test_8bit_native_intensities_are_not_rescaled(native_imagej, tmp_path):
    pixels = np.full((1, 6, 9), 123, dtype=np.uint8)
    row, folder = process(tmp_path, pixels, "max")
    assert row["Original_Bit_Depth"] == row["Projection_Bit_Depth"] == 8
    assert row["Total_Area_px2"] == 54
    assert row["Integrated_Density_raw"] == 123 * 54
    np.testing.assert_array_equal(
        tifffile.imread(folder / "sample_processed.tif"), pixels[0]
    )


def test_two_folders_share_one_fiji_lifecycle_and_record_partial_failure(
    native_imagej, tmp_path, monkeypatch
):
    from mca_tools import shg_analysis

    calls = []

    @contextmanager
    def reuse(_logger):
        calls.append("start")
        yield
        calls.append("close")

    monkeypatch.setattr(shg_analysis, "session", reuse)
    folders = []
    for name in ("first", "second"):
        folder = tmp_path / name
        channel = folder / "output_legacy" / "channel_1"
        channel.mkdir(parents=True)
        save_stack(
            channel / "valid.tif",
            np.ones((2, 5, 7), dtype=np.uint16),
            Calibration(0.5, 0.25, 2),
            {},
        )
        (channel / "broken.tif").write_bytes(b"invalid TIFF")
        (channel / "._valid.tif").write_bytes(b"ignored")
        folders.append(folder)
    args = SimpleNamespace(
        input_source="export",
        input=tmp_path / "input.json",
        projection="max",
        threshold_mode="manual",
        threshold=(1, 10),
        channel=1,
        allow_partial_export=False,
        allow_legacy_export=True,
    )
    assert shg_analysis.run_analysis(folders, args) == 1
    assert calls == ["start", "close"]
    for folder in folders:
        result = next(
            (folder / "output_legacy" / "channel_1").glob(
                "Mask_Intensity_Area_Results_*"
            )
        )
        data = json.loads((result / "run_status.json").read_text())
        assert data["status"] == "PARTIAL"
        assert data["counts"]["selected"] == 2
        assert data["counts"]["succeeded"] == data["counts"]["failed"] == 1
        assert (
            result / "Tables" / "Area_measurements_individual.csv"
        ).is_file()


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.float32])
@pytest.mark.parametrize("method", ["max", "sum"])
def test_auto_threshold_keeps_bright_signal_and_native_values(
    native_imagej, tmp_path, dtype, method
):
    from mca_tools.shg_analysis import process_image

    pixels = np.full((2, 20, 30), 5, dtype=dtype)
    pixels[:, 5:10, 8:14] = 200
    path = tmp_path / "bright.tif"
    tifffile.imwrite(path, pixels, imagej=True, metadata={"axes": "ZYX"})
    run = Run(tmp_path, "auto", "shg_analysis", [path], {})
    with run:
        for name in ("Tables", "Masks", "Masked_Images", "Metadata"):
            (run.directory / name).mkdir()
        row, outputs = process_image(path, run, method, "auto", None, "tiff")
        run.record_success(run.data["images"][0], outputs)
    mask = tifffile.imread(run.directory / "Masks" / "bright_mask.tif")
    expected = np.zeros((20, 30), dtype=np.uint8)
    expected[5:10, 8:14] = 255
    np.testing.assert_array_equal(mask, expected)
    assert row["Particle_Count"] == 1
    assert row["Total_Area_px2"] == 30
    assert row["Integrated_Density_raw"] == 30 * (
        200 if method == "max" else 400
    )
    assert row["Threshold_Method"] == "Moments dark"
    assert row["Total_Area_um2"] is None


@pytest.mark.parametrize("files_only", [False, True])
def test_independent_tiffs_split_merged_rows_and_audit_failures(
    native_imagej, tmp_path, monkeypatch, files_only
):
    from mca_tools import shg_analysis

    @contextmanager
    def reuse(_logger):
        yield

    monkeypatch.setattr(shg_analysis, "session", reuse)
    folder = tmp_path / "raw_tiffs"
    folder.mkdir()
    paths = []
    for name in ("single", "sample_MeRgEd"):
        path = folder / f"{name}.tif"
        tifffile.imwrite(
            path,
            np.full((2, 5, 7), 10, dtype=np.uint16),
            imagej=True,
            metadata={"axes": "ZYX", "unit": "um"},
            resolution=(2, 4),
        )
        paths.append(path)
    broken = folder / "broken.tif"
    broken.write_bytes(b"invalid TIFF")
    paths.append(broken)
    (folder / "._single.tif").write_bytes(b"ignored")
    args = SimpleNamespace(
        input_source="tiff",
        input=tmp_path / "input.json",
        projection="sum",
        threshold_mode="manual",
        threshold=(1, 100),
        channel=None,
        allow_partial_export=False,
        allow_legacy_export=False,
    )
    assert (
        shg_analysis.run_analysis(paths if files_only else [folder], args) == 1
    )
    result = next(folder.glob("Mask_Intensity_Area_Results_*"))
    status = json.loads((result / "run_status.json").read_text())
    assert status["status"] == "PARTIAL"
    assert status["counts"]["selected"] == 3
    assert status["counts"]["succeeded"] == 2
    assert status["counts"]["failed"] == 1
    assert status["parameters"]["export_run"] is None
    assert not (result / "Tables" / "All_area_measurements.csv").exists()
    for group, name in (
        ("individual", "single.tif"),
        ("merged", "sample_MeRgEd.tif"),
    ):
        table = pd.read_csv(
            result / "Tables" / f"Area_measurements_{group}.csv"
        )
        assert len(table) == status["summaries"][group]["rows"] == 1
        row = table.iloc[0]
        assert row["Image_Filename"] == name
        assert row["Image_Group"] == group
        assert row["Input_Source"] == "tiff"
        assert row["Total_Area_um2"] == pytest.approx(35 * 0.125)
        assert row["Integrated_Density_raw"] == 35 * 20


def test_empty_independent_folder_is_recorded_without_starting_fiji(
    tmp_path, monkeypatch
):
    from mca_tools import shg_analysis

    def unexpected(_logger):
        raise AssertionError("No JVM should start for an empty inventory")

    monkeypatch.setattr(shg_analysis, "session", unexpected)
    args = SimpleNamespace(
        input_source="tiff",
        input=tmp_path / "input.json",
        projection="max",
        threshold_mode="auto",
        threshold=None,
        channel=None,
        allow_partial_export=False,
        allow_legacy_export=False,
    )
    assert shg_analysis.run_analysis([tmp_path], args) == 1
    result = next(tmp_path.glob("Mask_Intensity_Area_Results_*"))
    record = json.loads((result / "run_status.json").read_text())
    assert record["status"] == "FAILED"
    assert record["counts"]["selected"] == 0
    assert "No TIFF inputs" in record["error"]
