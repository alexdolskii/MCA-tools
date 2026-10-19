import numpy as np
import pytest
import tifffile

from mca_tools.calibration import Calibration, measurement_columns, unit_factor
from mca_tools.metadata import tiff_calibration


def test_ome_units_are_converted_and_missing_z_is_not_invented(tmp_path):
    path = tmp_path / "image.ome.tif"
    tifffile.imwrite(
        path,
        np.ones((5, 7), dtype=np.uint16),
        ome=True,
        metadata={
            "axes": "YX",
            "PhysicalSizeX": 500,
            "PhysicalSizeXUnit": "nm",
            "PhysicalSizeY": 0.25,
            "PhysicalSizeYUnit": "µm",
        },
    )
    calibration, metadata = tiff_calibration(path)
    assert calibration.pixel_width_um == pytest.approx(0.5)
    assert calibration.pixel_height_um == pytest.approx(0.25)
    assert calibration.pixel_depth_um is None
    assert metadata["ome_xml"]


def test_resolution_without_unit_cannot_be_interpreted_as_microns(tmp_path):
    path = tmp_path / "image.tif"
    tifffile.imwrite(
        path,
        np.ones((5, 7), dtype=np.uint16),
        resolution=(2, 4),
        resolutionunit="NONE",
    )
    calibration, _ = tiff_calibration(path)
    assert not calibration.calibrated
    assert calibration.pixel_depth_um is None


def test_physical_fields_stay_missing_for_invalid_or_one_axis_calibration():
    for calibration in (
        Calibration(),
        Calibration(0.5, None),
        Calibration(float("nan"), 0.25),
    ):
        row = measurement_columns(1, 6, 360, 7, 5, calibration)
        assert row["Total_Area_px2"] == 6
        assert row["Total_Area_um2"] is None
        assert row["Integrated_Density_raw"] == 360
        assert row["Integrated_Density_um2"] is None


@pytest.mark.parametrize("unit", ["µm", "μm", "um", r"\u00B5m", "microns"])
def test_micrometer_spellings(unit):
    assert unit_factor(unit) == 1
