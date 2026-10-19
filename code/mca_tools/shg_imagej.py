"""ImageJ operations preserving native XY pixels and intensity semantics."""

from pathlib import Path
from typing import Any, Literal

import scyjava as sj

ProjectionMethod = Literal["max", "sum"]


class ImageProcessingError(Exception):
    """An image could not be processed correctly."""


def save_tiff(image: Any, output_path: Path) -> None:
    """Save an ImagePlus as TIFF without changing its pixel type."""
    FileSaver = sj.jimport("ij.io.FileSaver")

    if not FileSaver(image).saveAsTiff(str(output_path)):
        raise ImageProcessingError(f"Failed to save TIFF '{output_path}'.")


def create_projection(
    source_image: Any,
    projection_method: ProjectionMethod,
) -> Any:
    """Create a MAX or SUM projection with the required output bit depth."""
    ZProjector = sj.jimport("ij.plugin.ZProjector")
    ImageConverter = sj.jimport("ij.process.ImageConverter")

    slice_count = source_image.getNSlices()

    if slice_count > 1:
        projector = ZProjector(source_image)
        method = (
            ZProjector.MAX_METHOD
            if projection_method == "max"
            else ZProjector.SUM_METHOD
        )
        projector.setMethod(method)
        projector.doProjection()
        projection = projector.getProjection()
    else:
        projection = source_image.duplicate()

    if projection is None:
        raise ImageProcessingError("Z-projection did not produce an image.")

    # SUM output must remain floating point even for a one-slice input image.
    if projection_method == "sum" and projection.getBitDepth() != 32:
        ImageConverter(projection).convertToGray32()

    expected_bit_depth = (
        32 if projection_method == "sum" else source_image.getBitDepth()
    )
    if projection.getBitDepth() != expected_bit_depth:
        raise ImageProcessingError(
            f"Unexpected projection bit depth: expected {expected_bit_depth}-bit, "
            f"received {projection.getBitDepth()}-bit."
        )

    projection.setCalibration(source_image.getCalibration().copy())
    if (projection.getWidth(), projection.getHeight()) != (
        source_image.getWidth(),
        source_image.getHeight(),
    ):
        projection.close()
        raise ImageProcessingError(
            "Projection changed the native XY dimensions"
        )
    return projection


def create_binary_mask(
    source_image: Any,
    threshold_mode: str,
    manual_threshold_range: tuple[float, float] | None,
) -> Any:
    """Create an 8-bit binary mask from a 16-bit or 32-bit source image."""
    IJ = sj.jimport("ij.IJ")
    Prefs = sj.jimport("ij.Prefs")

    mask_image = source_image.duplicate()
    Prefs.blackBackground = True

    if threshold_mode == "manual" and manual_threshold_range is not None:
        lower_value, upper_value = manual_threshold_range
        IJ.setThreshold(mask_image, lower_value, upper_value)
    else:
        IJ.setAutoThreshold(mask_image, "Moments")

    lower = mask_image.getProcessor().getMinThreshold()
    upper = mask_image.getProcessor().getMaxThreshold()
    IJ.run(mask_image, "Convert to Mask", "")

    if mask_image.getBitDepth() != 8:
        mask_image.close()
        raise ImageProcessingError(
            "Mask conversion did not produce an 8-bit binary image."
        )

    mask_image.setCalibration(source_image.getCalibration().copy())
    mask_image.setProperty("mca.threshold.lower", str(lower))
    mask_image.setProperty("mca.threshold.upper", str(upper))
    return mask_image


def create_masked_intensity_image(
    original_image: Any,
    mask_image: Any,
) -> Any:
    """Apply an 8-bit binary mask while preserving intensity and bit depth."""
    ImagePlus = sj.jimport("ij.ImagePlus")
    Blitter = sj.jimport("ij.process.Blitter")

    if (
        original_image.getWidth() != mask_image.getWidth()
        or original_image.getHeight() != mask_image.getHeight()
    ):
        raise ImageProcessingError(
            "The original image and mask have different dimensions."
        )

    bit_depth = original_image.getBitDepth()
    original_processor = original_image.getProcessor().duplicate()
    mask_processor = mask_image.getProcessor().duplicate()

    if bit_depth == 8:
        original_processor.copyBits(mask_processor, 0, 0, Blitter.AND)
    elif bit_depth == 16:
        # Convert mask values from 0/255 to 0/65535 for a lossless bitwise AND.
        mask_processor = mask_processor.convertToShort(False)
        mask_processor.multiply(257.0)
        original_processor.copyBits(mask_processor, 0, 0, Blitter.AND)
    elif bit_depth == 32:
        # Convert mask values from 0/255 to 0/1 before float multiplication.
        mask_processor = mask_processor.convertToFloatProcessor()
        mask_processor.multiply(1.0 / 255.0)
        original_processor.copyBits(mask_processor, 0, 0, Blitter.MULTIPLY)
    else:
        raise ImageProcessingError(
            f"Unsupported source bit depth for masking: {bit_depth}-bit."
        )

    masked_image = ImagePlus("Masked Image", original_processor)
    masked_image.setCalibration(original_image.getCalibration().copy())
    if original_image.getProperty("Info") is not None:
        masked_image.setProperty("Info", original_image.getProperty("Info"))

    if masked_image.getBitDepth() != bit_depth:
        masked_image.close()
        raise ImageProcessingError(
            "Masking unexpectedly changed the image bit depth."
        )

    return masked_image


def close_images(*images: Any) -> None:
    """Close every non-null ImagePlus object without prompting for changes."""
    closed_ids: set[int] = set()

    for image in images:
        if image is None:
            continue

        image_id = id(image)
        if image_id in closed_ids:
            continue

        image.changes = False
        image.close()
        closed_ids.add(image_id)
