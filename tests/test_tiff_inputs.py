import json

import numpy as np
import pytest
import tifffile

from mca_tools.cli import analysis_settings, parser_for
from mca_tools.config import ConfigurationError, load_folders
from mca_tools.discovery import select_tiff_inputs
from mca_tools.metadata import tiff_layout


def test_tiff_config_inventory_and_overlapping_entries(tmp_path):
    folder = tmp_path / "images"
    folder.mkdir()
    visible = folder / "signal.TIFF"
    visible.touch()
    (folder / "._signal.tif").touch()
    (folder / ".hidden.tif").touch()
    (folder / "directory.tif").mkdir()
    (folder / "results").mkdir()
    (folder / "results" / "old_mask.tif").touch()
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"paths_to_files": ["images/signal.TIFF"]}))
    assert load_folders(config, allow_tiff_files=True) == [visible]
    with pytest.raises(ConfigurationError, match="folder"):
        load_folders(config)
    selection = select_tiff_inputs([folder])[0]
    assert selection.files == [visible]
    assert selection.directory == folder
    with pytest.raises(ValueError, match="overlapping"):
        select_tiff_inputs([visible, folder])
    config.write_text(json.dumps({"paths_to_files": ["images/._signal.tif"]}))
    with pytest.raises(ConfigurationError, match="Hidden"):
        load_folders(config, allow_tiff_files=True)


def test_input_source_is_first_prompt_and_modes_are_explicit(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompts = []
    answers = iter(["2", "max", "auto", "yes"])

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    parser = parser_for("shg2_intden_assay")
    args = analysis_settings(parser.parse_args(["-i", "input.json"]))
    assert prompts[0].startswith("Input source:")
    assert (args.input_source, args.channel) == ("tiff", None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    fixed = [
        "-i",
        "input.json",
        "--projection",
        "max",
        "--threshold-mode",
        "auto",
        "--yes",
    ]
    with pytest.raises(ConfigurationError, match="--input-source"):
        analysis_settings(parser.parse_args(fixed))
    for flag in (
        ["--channel", "1"],
        ["--allow-legacy-export"],
        ["--allow-partial-export"],
    ):
        with pytest.raises(ConfigurationError, match="apply only"):
            analysis_settings(
                parser.parse_args(fixed + ["--input-source", "tiff"] + flag)
            )
    export = analysis_settings(
        parser.parse_args(fixed + ["--input-source", "export"])
    )
    assert export.channel == 1


@pytest.mark.parametrize(
    "axes,shape", [("CYX", (2, 5, 7)), ("TYX", (2, 5, 7))]
)
def test_tiff_rejects_multiple_channels_or_timepoints(tmp_path, axes, shape):
    path = tmp_path / "multidimensional.tif"
    tifffile.imwrite(
        path,
        np.zeros(shape, dtype=np.uint16),
        imagej=True,
        metadata={"axes": axes},
    )
    with pytest.raises(ValueError, match="one channel and one timepoint"):
        tiff_layout(path)


def test_tiff_rejects_color_lossy_types_and_multiple_series(tmp_path):
    path = tmp_path / "image.tif"
    tifffile.imwrite(
        path, np.zeros((5, 7, 3), dtype=np.uint8), photometric="rgb"
    )
    with pytest.raises(ValueError, match="grayscale"):
        tiff_layout(path)
    tifffile.imwrite(path, np.ones((5, 7), dtype=np.float64))
    with pytest.raises(ValueError, match="uint8, uint16 or float32"):
        tiff_layout(path)
    with tifffile.TiffWriter(path) as writer:
        writer.write(np.ones((5, 7), dtype=np.uint16))
        writer.write(np.ones((6, 8), dtype=np.uint16))
    with pytest.raises(ValueError, match="one image series"):
        tiff_layout(path)


def test_plain_multipage_tiff_records_z_assumption(tmp_path):
    path = tmp_path / "plain.tif"
    tifffile.imwrite(
        path,
        np.zeros((3, 5, 7), dtype=np.uint16),
        metadata=None,
        photometric="minisblack",
    )
    layout = tiff_layout(path)
    assert layout["shape_zyx"] == [3, 5, 7]
    assert layout["assumed_z_stack"]
