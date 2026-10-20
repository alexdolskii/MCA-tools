"""Read recorded physical sizes without accepting an ImageJ default scale."""

from xml.etree import ElementTree

from .calibration import Calibration, positive, unit_factor


def tiff_layout(path):
    """Reject ambiguous channels/time/series and lossy ImageJ input types."""
    import tifffile

    with tifffile.TiffFile(path) as tif:
        if len(tif.series) != 1 or len(tif.series[0].levels) != 1:
            raise ValueError(
                "Export one image series at one resolution per TIFF"
            )
        series = tif.series[0]
        if series.dtype.name not in {"uint8", "uint16", "float32"}:
            raise ValueError("TIFF pixels must be uint8, uint16 or float32")
        for page in series.pages:
            if page.samplesperpixel != 1 or int(page.photometric) not in {
                0,
                1,
            }:
                raise ValueError(
                    "TIFF must be grayscale, not RGB or palette color"
                )
        axes = list(zip(series.axes, series.shape))
        for axis, size in axes:
            if axis in "CTS" and size != 1:
                raise ValueError(
                    "TIFF must contain one channel and one timepoint; "
                    "export the selected SHG channel/timepoint separately"
                )
        axes = [(axis, size) for axis, size in axes if axis not in "CTS"]
        names = "".join(axis for axis, _ in axes)
        if names not in {"YX", "ZYX", "QYX", "IYX"}:
            raise ValueError(
                f"Unsupported TIFF axes {series.axes!r}; use YX or ZYX"
            )
        z = axes[0][1] if len(axes) == 3 else 1
        return {
            "axes": series.axes,
            "shape_zyx": [z, axes[-2][1], axes[-1][1]],
            "dtype": series.dtype.name,
            "assumed_z_stack": names in {"QYX", "IYX"},
        }


def tiff_calibration(path):
    import tifffile

    with tifffile.TiffFile(path) as tif:
        if tif.ome_metadata:
            root = ElementTree.fromstring(tif.ome_metadata)
            pixels = root.find(".//{*}Image/{*}Pixels")
            if pixels is None:
                raise ValueError("OME metadata has no Pixels element")
            sizes = []
            for axis in "XYZ":
                value = positive(pixels.get(f"PhysicalSize{axis}"))
                # The OME schema defines um as the default physical-size unit.
                factor = unit_factor(
                    pixels.get(f"PhysicalSize{axis}Unit", "um")
                )
                sizes.append(value * factor if value and factor else None)
            return Calibration(*sizes, source="OME-TIFF"), {
                "ome_xml": tif.ome_metadata
            }
        metadata = tif.imagej_metadata or {}
        tags = tif.pages[0].tags
        unit = metadata.get("unit")
        factor = unit_factor(unit)
        if factor is None:
            resolution_unit = tags.get("ResolutionUnit")
            code = int(resolution_unit.value) if resolution_unit else 1
            factor = {2: 25400.0, 3: 10000.0}.get(code)
        sizes = []
        for axis in "XY":
            tag = tags.get(f"{axis}Resolution")
            value = (
                positive(tag.value[0] / tag.value[1])
                if tag and tag.value[1]
                else None
            )
            sizes.append(factor / value if factor and value else None)
        depth = positive(metadata.get("spacing"))
        z_factor = unit_factor(metadata.get("zunit", unit))
        sizes.append(depth * z_factor if depth and z_factor else None)
        return Calibration(*sizes, source="TIFF header"), {
            "imagej_metadata": metadata
        }


def nd2_calibration(path):
    import scyjava as sj

    service = sj.jimport("loci.common.services.ServiceFactory")().getInstance(
        sj.jimport("loci.formats.services.OMEXMLService").class_
    )
    metadata = service.createOMEXMLMetadata()
    reader = sj.jimport("loci.formats.ImageReader")()
    try:
        reader.setMetadataStore(metadata)
        reader.setId(str(path))
        sizes = []
        micrometer = sj.jimport("ome.units.UNITS").MICROMETER
        for axis in "XYZ":
            length = getattr(metadata, f"getPixelsPhysicalSize{axis}")(0)
            value = length.value(micrometer) if length is not None else None
            sizes.append(
                positive(value.doubleValue()) if value is not None else None
            )
        return Calibration(*sizes, source="ND2/Bio-Formats OME"), {
            "ome_xml": str(service.getOMEXML(metadata))
        }
    finally:
        reader.close()
