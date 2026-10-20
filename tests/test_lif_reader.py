import json
import struct

import numpy as np
import pytest
import tifffile
from readlif.reader import LifFile

from mca_tools.discovery import select_export
from mca_tools.lif_export import run_export
from mca_tools.lif_reader import LifFormatError, load_lif


@pytest.mark.parametrize("padding", [1, 4, 99, 100, 1024 * 1024 + 7])
def test_zero_padding_preserves_pixels_metadata_and_source(
    tmp_path, lif_factory, padding
):
    pixels = np.arange(3 * 5 * 7, dtype=np.uint16).reshape(3, 5, 7)
    source = lif_factory(tmp_path / "image.lif", pixels)
    unpadded = source.read_bytes()
    source.write_bytes(unpadded + bytes(padding))
    # This is the actual upstream failure, not a mocked parser exception.
    with pytest.raises(ValueError, match="closed file"):
        LifFile(str(source))

    assert run_export([tmp_path], tmp_path / "input.json") == 0
    selection = select_export(tmp_path)
    tif = selection.files[0]
    np.testing.assert_array_equal(tifffile.imread(tif), pixels)
    metadata = json.loads(tif.with_suffix(".tif.json").read_text())
    assert metadata["lif_structure"] == {
        "file_size_bytes": len(unpadded) + padding,
        "data_end_byte": len(unpadded),
        "memory_block_count": 1,
        "verified_zero_padding_bytes": padding,
    }
    assert metadata["calibration"]["pixel_width_um"] == 0.5
    assert metadata["calibration"]["pixel_height_um"] == 0.25
    xml_chars = struct.unpack_from("<I", unpadded, 9)[0]
    expected_xml = unpadded[13 : 13 + xml_chars * 2].decode("utf-16-le")
    assert (
        selection.directory / metadata["source_xml"]
    ).read_text() == expected_xml
    assert source.read_bytes() == unpadded + bytes(padding)
    assert "LIF_ZERO_PADDING" in (selection.directory / "run.log").read_text()


def test_unexpected_block_has_original_byte_position(tmp_path, lif_factory):
    source = lif_factory(
        tmp_path / "bad.lif", np.ones((2, 5, 7), dtype=np.uint8)
    )
    original = source.read_bytes()
    source.write_bytes(original + b"BAD!")
    with pytest.raises(
        LifFormatError,
        match=f"memory-block signature at byte {len(original)}.*42 41 44 21",
    ):
        load_lif(source)


@pytest.mark.parametrize("padding", [4, 1024 * 1024 + 19])
def test_nonzero_data_after_zero_marker_is_never_skipped(
    tmp_path, lif_factory, padding
):
    source = lif_factory(
        tmp_path / "bad.lif", np.ones((2, 5, 7), dtype=np.uint16)
    )
    original = source.read_bytes()
    source.write_bytes(original + bytes(padding) + b"x")
    with pytest.raises(
        LifFormatError, match=f"nonzero data.*byte {len(original) + padding}"
    ):
        load_lif(source)
    assert run_export([tmp_path], tmp_path / "input.json") == 1
    export = next(tmp_path.glob("output_*"))
    assert not list(export.rglob("*.tif"))
    assert json.loads((export / "run_status.json").read_text())["status"] == (
        "FAILED"
    )


@pytest.mark.parametrize("cut", [0, 3, 12, -1])
def test_incomplete_header_or_payload_is_rejected(tmp_path, lif_factory, cut):
    source = lif_factory(
        tmp_path / "short.lif", np.ones((2, 5, 7), dtype=np.uint16)
    )
    source.write_bytes(source.read_bytes()[:cut])
    with pytest.raises(LifFormatError, match="Incomplete LIF.*byte"):
        load_lif(source)


def test_padding_cannot_hide_xml_memory_size_disagreement(
    tmp_path, lif_factory
):
    pixels = np.ones((2, 5, 7), dtype=np.uint16)
    source = lif_factory(tmp_path / "bad.lif", pixels)
    original = source.read_bytes()
    old = f'<Memory Size="{pixels.nbytes}"/>'.encode("utf-16-le")
    new = f'<Memory Size="{pixels.nbytes + 1}"/>'.encode("utf-16-le")
    assert len(old) == len(new) and old in original
    source.write_bytes(original.replace(old, new) + bytes(512))
    with pytest.raises(LifFormatError, match="XML-declared sizes"):
        load_lif(source)


def test_zero_tail_cannot_replace_a_missing_image_block(tmp_path, lif_factory):
    source = lif_factory(
        tmp_path / "bad.lif", np.ones((2, 5, 7), dtype=np.uint16)
    )
    original = source.read_bytes()
    header_end = 13 + 2 * struct.unpack_from("<I", original, 9)[0]
    source.write_bytes(original[:header_end] + bytes(512))
    with pytest.raises(LifFormatError, match="memory-block signature"):
        load_lif(source)


@pytest.mark.parametrize("padding", [0, 512])
def test_64bit_memory_length_and_later_image_reads(
    tmp_path, lif_factory, padding
):
    pixels = np.arange(3 * 5 * 7, dtype=np.uint16).reshape(3, 5, 7)
    source = lif_factory(tmp_path / "64bit.lif", pixels)
    original = source.read_bytes()
    header_end = 13 + 2 * struct.unpack_from("<I", original, 9)[0]
    length_offset = header_end + 9
    source.write_bytes(
        original[:length_offset]
        + struct.pack("<Q", pixels.nbytes)
        + original[length_offset + 4 :]
        + bytes(padding)
    )
    lif, layout = load_lif(source)
    assert layout.file_size - layout.data_end == padding
    image = lif.get_image(0)
    # The metadata parsing stream is already closed. Pixel reads must reopen
    # the original source at the unchanged absolute offsets.
    for z in range(3):
        np.testing.assert_array_equal(
            np.asarray(image.get_frame(z=z)), pixels[z]
        )
