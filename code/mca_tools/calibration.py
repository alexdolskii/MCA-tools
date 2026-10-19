"""Spatial calibration in micrometers; absent metadata never implies 1 um."""

import math
import re
from dataclasses import asdict, dataclass


def positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def unit_factor(unit):
    """Convert recognized spatial units to micrometers."""
    value = re.sub(r"\\u00b5|\\u03bc", "u", str(unit).strip().lower())
    value = value.replace("µ", "u").replace("μ", "u")
    return {
        "um": 1.0,
        "micron": 1.0,
        "microns": 1.0,
        "micrometer": 1.0,
        "micrometers": 1.0,
        "micrometre": 1.0,
        "micrometres": 1.0,
        "nm": 0.001,
        "mm": 1000.0,
        "cm": 10000.0,
        "m": 1000000.0,
        "inch": 25400.0,
        "inches": 25400.0,
    }.get(value)


@dataclass(frozen=True)
class Calibration:
    pixel_width_um: float | None = None
    pixel_height_um: float | None = None
    pixel_depth_um: float | None = None
    source: str = "missing"

    @property
    def calibrated(self):
        return (
            positive(self.pixel_width_um) is not None
            and positive(self.pixel_height_um) is not None
        )

    @property
    def pixel_area_um2(self):
        if self.calibrated:
            return self.pixel_width_um * self.pixel_height_um
        return None

    def as_dict(self):
        return {
            **asdict(self),
            "status": "CALIBRATED"
            if self.calibrated
            else "MISSING_XY_CALIBRATION",
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            *(
                positive(data.get(key))
                for key in (
                    "pixel_width_um",
                    "pixel_height_um",
                    "pixel_depth_um",
                )
            ),
            source=str(data.get("source", "metadata")),
        )

    @classmethod
    def from_lif(cls, image):
        # readlif 0.6.6 reports pixels/um, NOT um/pixel.
        scales = getattr(image, "scale", (None, None, None))
        sizes = [1.0 / n if (n := positive(s)) else None for s in scales[:3]]
        return cls(*sizes, source="LIF/readlif")

    @classmethod
    def from_imagej(cls, image):
        cal = image.getCalibration()
        values = []
        for size, unit in (
            (cal.pixelWidth, cal.getXUnit()),
            (cal.pixelHeight, cal.getYUnit()),
            (cal.pixelDepth, cal.getZUnit()),
        ):
            factor, number = unit_factor(unit), positive(size)
            values.append(number * factor if number and factor else None)
        return cls(*values, source="ImageJ input metadata")

    def apply(self, image):
        """Apply XY only when both axes have trustworthy physical sizes."""
        cal = image.getCalibration().copy()
        if self.calibrated:
            cal.pixelWidth = self.pixel_width_um
            cal.pixelHeight = self.pixel_height_um
            cal.setUnit("um")
            cal.setYUnit("um")
        else:
            cal.pixelWidth = cal.pixelHeight = 1.0
            cal.setUnit("pixel")
            cal.setYUnit("pixel")
        if self.pixel_depth_um:
            cal.pixelDepth = self.pixel_depth_um
            cal.setZUnit("um")
        else:
            cal.pixelDepth = 1.0
            cal.setZUnit("pixel")
        image.setCalibration(cal)

    def columns(self):
        return {
            "Pixel_Width_um": self.pixel_width_um,
            "Pixel_Height_um": self.pixel_height_um,
            "Pixel_Depth_um": self.pixel_depth_um,
            "Calibration_Status": self.as_dict()["status"],
            "Calibration_Source": self.source,
        }


def measurement_columns(count, area, raw_intden, width, height, calibration):
    """Export pixel and physical areas and raw integrated signal explicitly."""
    factor = calibration.pixel_area_um2

    def physical(value):
        return value * factor if factor is not None else None

    average = area / count if count else 0.0
    return {
        "Particle_Count": count,
        "Total_Area_px2": area,
        "Total_Area_um2": physical(area),
        "Average_Particle_Area_px2": average,
        "Average_Particle_Area_um2": physical(average),
        "Image_Area_px2": width * height,
        "Image_Area_um2": physical(width * height),
        "Area_Fraction_percent": 100.0 * area / (width * height),
        "Mean_Intensity": raw_intden / area if area else None,
        "Integrated_Density_raw": raw_intden,
        "Integrated_Density_um2": physical(raw_intden),
        **calibration.columns(),
    }
