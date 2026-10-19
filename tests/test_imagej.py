import json
from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np
import pytest
import tifffile

from mca_tools.calibration import Calibration
from mca_tools.lif_export import save_stack
from mca_tools.run import Run

pytestmark = pytest.mark.imagej


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
        assert (result / "Tables" / "All_area_measurements.csv").is_file()
