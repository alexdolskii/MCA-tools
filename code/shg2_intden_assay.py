#!/usr/bin/env python3

"""Process channel_1 images from the latest LIF-export output folders."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import imagej
import pandas as pd
import scyjava as sj


ProjectionMethod = Literal["max", "sum"]


class ImageJInitializationError(Exception):
    """Raised when ImageJ cannot be initialized."""


class ImageProcessingError(Exception):
    """Raised when an image cannot be processed correctly."""


def initialize_imagej() -> Any:
    """Initialize ImageJ in headless mode with Fiji plugin support."""
    print("Initializing ImageJ in headless mode...")

    try:
        imagej_instance = imagej.init("sc.fiji:fiji", mode="headless")
    except Exception as error:
        raise ImageJInitializationError(
            f"Failed to initialize ImageJ: {error}"
        ) from error

    print("ImageJ successfully initialized.")
    return imagej_instance


def load_config(json_path: Path) -> list[Path]:
    """Load base folder paths from the shared JSON configuration."""
    if not json_path.is_file():
        raise FileNotFoundError(f"File '{json_path}' does not exist.")

    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"File '{json_path}' does not contain valid JSON: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError("The JSON root must be an object.")

    path_values = data.get("paths_to_files")
    if not isinstance(path_values, list) or not path_values:
        raise ValueError(
            "JSON must contain a non-empty 'paths_to_files' list."
        )

    if any(
        not isinstance(path_value, str) or not path_value.strip()
        for path_value in path_values
    ):
        raise ValueError(
            "Every item in 'paths_to_files' must be a non-empty string."
        )

    return [Path(path_value).expanduser() for path_value in path_values]


def get_latest_channel_folders(base_paths: list[Path]) -> list[Path]:
    """Find channel_1 in the latest TIFF-export folder under each base path."""
    target_folders: list[Path] = []
    print("\nScanning for the latest output directories and channel_1...")

    for base_path in base_paths:
        if not base_path.is_dir():
            print(f"  [WARNING] Base folder '{base_path}' does not exist.")
            continue

        # Ignore folders produced by other processing scripts.
        output_folders = sorted(
            (
                folder
                for folder in base_path.iterdir()
                if folder.is_dir()
                and folder.name.startswith("output_")
                and not folder.name.startswith("output_processed_")
            ),
            key=lambda folder: folder.name,
        )

        if not output_folders:
            print(f"  [WARNING] No output folder found in '{base_path}'.")
            continue

        latest_output = output_folders[-1]
        channel_folder = latest_output / "channel_1"

        if channel_folder.is_dir():
            print(f"  Found target: {channel_folder}")
            target_folders.append(channel_folder)
        else:
            print(
                f"  [WARNING] channel_1 was not found in "
                f"'{latest_output.name}'."
            )

    if not target_folders:
        raise ValueError("No valid channel_1 folders were found.")

    return target_folders


def get_projection_method() -> ProjectionMethod:
    """Ask the user which Z-projection method should be used."""
    print("\nChoose the Z-projection method:")
    print("  1 - Maximum Intensity Projection (preserves source bit depth)")
    print("  2 - Sum Slices (saved as a 32-bit float TIFF)")

    while True:
        choice = input("Projection method [1/2, max/sum]: ").strip().lower()

        if choice in {"1", "max", "maximum"}:
            return "max"
        if choice in {"2", "sum", "sum slices"}:
            return "sum"

        print("Invalid choice. Enter 1/max or 2/sum.")


def get_threshold_choice() -> tuple[str, tuple[float, float] | None]:
    """Ask the user whether automatic or manual thresholding should be used."""
    while True:
        mode = input(
            "\nUse auto or manual thresholding? [auto/manual]: "
        ).strip().lower()

        if mode in {"auto", "a"}:
            return "auto", None
        if mode in {"manual", "m"}:
            break

        print("Invalid choice. Enter auto or manual.")

    while True:
        lower_text = input("Enter the lower threshold [default: 0]: ").strip()
        upper_text = input(
            "Enter the upper threshold [default: no upper limit]: "
        ).strip()

        try:
            lower_value = float(lower_text) if lower_text else 0.0
            upper_value = float(upper_text) if upper_text else float("inf")
        except ValueError:
            print("Thresholds must be numeric values. Please try again.")
            continue

        if lower_value > upper_value:
            print("The lower threshold cannot exceed the upper threshold.")
            continue

        return "manual", (lower_value, upper_value)


def create_results_folders(
    folder_path: Path,
    timestamp: str,
) -> tuple[Path, Path, Path, Path]:
    """Create the result folder structure inside a channel directory."""
    results_folder = folder_path / f"Mask_Intensity_Area_Results_{timestamp}"
    table_folder = results_folder / "Tables"
    mask_folder = results_folder / "Masks"
    masked_folder = results_folder / "Masked_Images"

    for folder in (
        results_folder,
        table_folder,
        mask_folder,
        masked_folder,
    ):
        folder.mkdir(parents=True, exist_ok=True)

    print(f"\nResults folder created: {results_folder}")
    return results_folder, table_folder, mask_folder, masked_folder


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

    IJ.run(mask_image, "Convert to Mask", "")

    if mask_image.getBitDepth() != 8:
        mask_image.close()
        raise ImageProcessingError(
            "Mask conversion did not produce an 8-bit binary image."
        )

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

    if masked_image.getBitDepth() != bit_depth:
        masked_image.close()
        raise ImageProcessingError(
            "Masking unexpectedly changed the image bit depth."
        )

    return masked_image


def analyze_particles_summary(
    original_image: Any,
    mask_image: Any,
    masked_output_path: Path,
    min_size: float = 0.0,
    max_size: float = 1e9,
    min_circularity: float = 0.0,
    max_circularity: float = 1.0,
) -> Any:
    """Apply the mask, save the masked image, and summarize particles."""
    ParticleAnalyzer = sj.jimport("ij.plugin.filter.ParticleAnalyzer")
    ResultsTable = sj.jimport("ij.measure.ResultsTable")
    Measurements = sj.jimport("ij.measure.Measurements")
    IJ = sj.jimport("ij.IJ")
    Prefs = sj.jimport("ij.Prefs")

    measurements = (
        Measurements.AREA
        | Measurements.MEDIAN
        | Measurements.MEAN
        | Measurements.INTEGRATED_DENSITY
        | Measurements.LIMIT
    )
    options = ParticleAnalyzer.SHOW_SUMMARY

    summary_table = ResultsTable()
    ParticleAnalyzer.setSummaryTable(summary_table)

    masked_image = create_masked_intensity_image(original_image, mask_image)

    try:
        masked_image_for_save = masked_image.duplicate()
        try:
            IJ.run(masked_image_for_save, "Smooth", "")
            IJ.run(masked_image_for_save, "Smooth", "")
            IJ.run(
                masked_image_for_save,
                "Enhance Contrast...",
                "saturated=0.35",
            )
            save_tiff(masked_image_for_save, masked_output_path)
        finally:
            masked_image_for_save.close()

        lower_threshold = 1e-4 if masked_image.getBitDepth() == 32 else 1.0
        IJ.setThreshold(masked_image, lower_threshold, float("inf"))
        
        Prefs.blackBackground = True

        particle_table = ResultsTable()
        analyzer = ParticleAnalyzer(
            options,
            measurements,
            particle_table,
            min_size,
            max_size,
            min_circularity,
            max_circularity,
        )

        if not analyzer.analyze(masked_image):
            raise ImageProcessingError(
                "ParticleAnalyzer failed in summary mode."
            )
    finally:
        masked_image.close()

    return summary_table


def extract_summary_row(
    summary_table: Any,
    filename: str,
    original_bit_depth: int,
    projection_bit_depth: int,
    projection_method: ProjectionMethod,
) -> pd.DataFrame | None:
    """Convert the first ImageJ summary row to a pandas DataFrame."""
    if summary_table.getCounter() < 1:
        return None

    row_index = 0
    column_data = {
        str(heading): [summary_table.getValue(heading, row_index)]
        for heading in summary_table.getHeadings()
    }

    summary = pd.DataFrame(column_data)
    summary["Image_Filename"] = filename
    summary["Original_Bit_Depth"] = original_bit_depth
    summary["Projection_Method"] = projection_method.upper()
    summary["Projection_Bit_Depth"] = projection_bit_depth
    return summary


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


def process_image(
    file_path: Path,
    results_folder: Path,
    mask_folder: Path,
    masked_folder: Path,
    projection_method: ProjectionMethod,
    threshold_mode: str,
    manual_threshold_range: tuple[float, float] | None,
    desired_width: int,
    desired_height: int,
) -> pd.DataFrame | None:
    """Process one image and return its particle-summary row."""
    IJ = sj.jimport("ij.IJ")
    Duplicator = sj.jimport("ij.plugin.Duplicator")

    source_image = None
    channel_image = None
    projection = None
    saved_projection = None
    mask_image = None

    try:
        source_image = IJ.openImage(str(file_path))
        if source_image is None:
            raise ImageProcessingError("ImageJ could not open the image.")

        original_bit_depth = source_image.getBitDepth()
        channel_count = source_image.getNChannels()
        slice_count = source_image.getNSlices()
        frame_count = source_image.getNFrames()

        if channel_count < 1 or slice_count < 1 or frame_count < 1:
            raise ImageProcessingError("The image has invalid dimensions.")

        # Extract only channel 1, all Z slices, and the first time point.
        channel_image = Duplicator().run(
            source_image,
            1,
            1,
            1,
            slice_count,
            1,
            1,
        )
        projection = create_projection(channel_image, projection_method)

        if "merged" not in file_path.name.lower():
            resized_projection = projection.resize(
                desired_width,
                desired_height,
                "bilinear",
            )
            projection.close()
            projection = resized_projection

        expected_bit_depth = (
            32 if projection_method == "sum" else original_bit_depth
        )
        if projection.getBitDepth() != expected_bit_depth:
            raise ImageProcessingError(
                "Resizing unexpectedly changed the projection bit depth."
            )

        output_path = results_folder / f"{file_path.stem}_processed.tif"
        save_tiff(projection, output_path)

        # Re-open the saved TIFF so subsequent analysis uses the actual file.
        saved_projection = IJ.openImage(str(output_path))
        if saved_projection is None:
            raise ImageProcessingError(
                f"ImageJ could not reopen saved TIFF '{output_path}'."
            )

        projection_bit_depth = saved_projection.getBitDepth()
        if projection_bit_depth != expected_bit_depth:
            raise ImageProcessingError(
                f"Saved projection has {projection_bit_depth}-bit pixels; "
                f"expected {expected_bit_depth}-bit pixels."
            )

        mask_image = create_binary_mask(
            saved_projection,
            threshold_mode,
            manual_threshold_range,
        )
        mask_path = mask_folder / f"{file_path.stem}_mask.tif"
        save_tiff(mask_image, mask_path)

        masked_output_path = masked_folder / f"{file_path.stem}_masked.tif"
        summary_table = analyze_particles_summary(
            saved_projection,
            mask_image,
            masked_output_path,
        )

        print(
            f"  Processed: {file_path.name} "
            f"[{projection_method.upper()}, {projection_bit_depth}-bit]"
        )
        return extract_summary_row(
            summary_table,
            file_path.name,
            original_bit_depth,
            projection_bit_depth,
            projection_method,
        )
    finally:
        close_images(
            mask_image,
            saved_projection,
            projection,
            channel_image,
            source_image,
        )


def process_images_in_folder(
    folder_path: Path,
    projection_method: ProjectionMethod,
    threshold_mode: str,
    manual_threshold_range: tuple[float, float] | None,
    desired_width: int = 1024,
    desired_height: int = 1024,
) -> None:
    """Process supported image files inside one channel_1 folder."""
    if not folder_path.is_dir():
        print(f"[WARNING] Folder '{folder_path}' does not exist; skipping.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (
        results_folder,
        table_folder,
        mask_folder,
        masked_folder,
    ) = create_results_folders(folder_path, timestamp)

    supported_extensions = {".tif", ".tiff", ".nd2"}
    files_to_process = sorted(
        (
            file_path
            for file_path in folder_path.iterdir()
            if file_path.is_file()
            and not file_path.name.startswith(".")
            and file_path.suffix.lower() in supported_extensions
        ),
        key=lambda file_path: file_path.name.lower(),
    )

    if not files_to_process:
        print(f"  No supported image files found in '{folder_path}'.")
        return

    summaries: list[pd.DataFrame] = []

    for file_path in files_to_process:
        try:
            summary = process_image(
                file_path=file_path,
                results_folder=results_folder,
                mask_folder=mask_folder,
                masked_folder=masked_folder,
                projection_method=projection_method,
                threshold_mode=threshold_mode,
                manual_threshold_range=manual_threshold_range,
                desired_width=desired_width,
                desired_height=desired_height,
            )
        except Exception as error:
            print(f"  [ERROR] Failed to process '{file_path.name}': {error}")
            continue

        if summary is not None:
            summaries.append(summary)

    if summaries:
        combined_summary = pd.concat(summaries, ignore_index=True)
        summary_path = table_folder / "All_area_measurements.csv"
        combined_summary.to_csv(summary_path, index=False)
        print(f"\nSummaries saved to: {summary_path}")
    else:
        print("\nNo particle summaries were generated.")

    print(f"\nFinished processing folder: '{folder_path}'.\n")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Process channel_1 output from the LIF exporter and measure "
            "particle intensity and area."
        )
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to the shared JSON file containing 'paths_to_files'.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the application."""
    args = parse_arguments()

    try:
        imagej_instance = initialize_imagej()
    except ImageJInitializationError as error:
        print(f"[ERROR] {error}")
        return 1

    try:
        try:
            base_paths = load_config(args.input)
            target_folders = get_latest_channel_folders(base_paths)
        except Exception as error:
            print(f"[ERROR] Could not locate input folders: {error}")
            return 1

        projection_method = get_projection_method()
        threshold_mode, manual_threshold_range = get_threshold_choice()

        answer = input("\nStart processing? [yes/no]: ").strip().lower()
        if answer not in {"yes", "y"}:
            print("Processing cancelled.")
            return 0

        for target_folder in target_folders:
            process_images_in_folder(
                folder_path=target_folder,
                projection_method=projection_method,
                threshold_mode=threshold_mode,
                manual_threshold_range=manual_threshold_range,
            )

        print("All folders processed.")
        return 0
    finally:
        imagej_instance.context().dispose()
        print("Script finished.")


if __name__ == "__main__":
    raise SystemExit(main())
