import json

import numpy as np
import pytest
import tifffile

from mca_tools.calibration import Calibration
from mca_tools.discovery import select_export
from mca_tools.files import image_files
from mca_tools.lif_export import run_export, save_stack


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_real_lif_reader_preserves_native_pixels_and_calibration(
    tmp_path, lif_factory, dtype
):
    pixels = np.arange(3 * 5 * 7, dtype=dtype).reshape(3, 5, 7)
    lif_factory(tmp_path / "image.lif", pixels)
    (tmp_path / "._image.lif").write_bytes(b"not an image")
    (tmp_path / ".hidden.lif").write_bytes(b"not an image")
    (tmp_path / "directory.lif").mkdir()
    assert len(image_files(tmp_path, {".lif"})) == 1
    assert run_export([tmp_path], tmp_path / "input.json") == 0
    selection = select_export(tmp_path)
    assert len(selection.files) == 1
    output = selection.files[0]
    with tifffile.TiffFile(output) as tif:
        np.testing.assert_array_equal(tif.asarray(), pixels)
        assert tif.asarray().dtype == dtype
        assert tif.imagej_metadata["spacing"] == 2
        assert tif.imagej_metadata["unit"] == "um"
    metadata = json.loads(output.with_suffix(".tif.json").read_text())
    assert metadata["calibration"]["pixel_width_um"] == pytest.approx(0.5)
    assert metadata["calibration"]["pixel_height_um"] == pytest.approx(0.25)
    assert metadata["calibration"]["pixel_depth_um"] == pytest.approx(2)
    assert (selection.directory / metadata["source_xml"]).is_file()
    assert "/" not in output.name


def test_partial_export_requires_opt_in_and_never_uses_failed_outputs(
    tmp_path, lif_factory
):
    lif_factory(tmp_path / "good.lif", np.ones((2, 5, 7), dtype=np.uint16))
    (tmp_path / "bad.lif").write_bytes(b"broken")
    assert run_export([tmp_path], tmp_path / "input.json") == 1
    with pytest.raises(ValueError, match="No verified"):
        select_export(tmp_path)
    selection = select_export(tmp_path, allow_partial=True)
    assert selection.status == "PARTIAL"
    assert len(selection.files) == 1
    run = json.loads((selection.directory / "run_status.json").read_text())
    assert run["counts"] == {
        "selected": 2,
        "succeeded": 1,
        "failed": 1,
        "unprocessed": 0,
    }
    assert "Traceback" in (selection.directory / "run.log").read_text()
    selection.files[0].write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed output"):
        select_export(tmp_path, allow_partial=True)


def test_new_empty_run_does_not_hide_previous_valid_export(
    tmp_path, lif_factory
):
    source = lif_factory(
        tmp_path / "good.lif", np.ones((2, 5, 7), dtype=np.uint16)
    )
    assert run_export([tmp_path], tmp_path / "input.json") == 0
    previous = select_export(tmp_path).directory
    source.unlink()
    assert run_export([tmp_path], tmp_path / "input.json") == 1
    selected = select_export(tmp_path)
    assert selected.directory == previous
    assert any("NO_INPUT" in reason for reason in selected.warnings)


def test_uncalibrated_tiff_does_not_claim_micrometers(tmp_path):
    path = tmp_path / "unknown.tif"
    save_stack(path, np.ones((1, 5, 7), dtype=np.uint16), Calibration(), {})
    with tifffile.TiffFile(path) as tif:
        assert tif.imagej_metadata["unit"] == "pixel"
        assert "spacing" not in tif.imagej_metadata
    assert (
        json.loads(path.with_suffix(".tif.json").read_text())["calibration"][
            "pixel_width_um"
        ]
        is None
    )
