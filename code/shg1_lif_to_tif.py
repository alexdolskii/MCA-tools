#!/usr/bin/env python3

"""Export LIF scenes, channels, and mosaic tiles as TIFF Z-stacks."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from readlif.reader import LifFile

# Configure the JVM before importing PyImageJ.
os.environ["_JAVA_OPTIONS"] = (
    "-Xmx16g "
    "-XX:+IgnoreUnrecognizedVMOptions "
    "--illegal-access=warn "
    "--add-opens=java.base/java.lang=ALL-UNNAMED"
)

import imagej  # noqa: E402  # The JVM options must be set before this import.


class LifFileProcessorError(Exception):
    """Raised when the input configuration or a LIF file cannot be processed."""


class ImageJInitializationError(Exception):
    """Raised when ImageJ cannot be initialized."""


def load_folder_paths(json_path: Path) -> list[Path]:
    """Load and validate input folders from the JSON ``paths_to_files`` list."""
    try:
        with json_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise LifFileProcessorError(
            f"Could not read or parse JSON file '{json_path}': {error}"
        ) from error

    if not isinstance(config, dict):
        raise LifFileProcessorError("The JSON root must be an object.")

    folder_values = config.get("paths_to_files")
    if not isinstance(folder_values, list) or not folder_values:
        raise LifFileProcessorError(
            "The JSON file must contain a non-empty 'paths_to_files' list."
        )

    invalid_values = [
        value
        for value in folder_values
        if not isinstance(value, str) or not value.strip()
    ]
    if invalid_values:
        raise LifFileProcessorError(
            "Every item in 'paths_to_files' must be a non-empty string."
        )

    return [Path(value).expanduser() for value in folder_values]


def create_output_folder(
    input_folder: Path,
    timestamp: str,
) -> Path:
    """Create the output folder inside the corresponding input folder."""
    folder_name = input_folder.name
    output_folder = input_folder / f"output_{folder_name}_{timestamp}"

    output_folder.mkdir(parents=True, exist_ok=True)
    return output_folder


def create_channel_folders(
    output_folder: Path,
    channel_count: int,
) -> list[Path]:
    """Create one numbered output subfolder for each channel."""
    channel_folders = [
        output_folder / f"channel_{channel_number}"
        for channel_number in range(1, channel_count + 1)
    ]

    for channel_folder in channel_folders:
        channel_folder.mkdir(parents=True, exist_ok=True)

    return channel_folders


def find_lif_files(folder: Path) -> list[Path]:
    """Return all LIF files located directly inside a folder."""
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() == ".lif"
        ),
        key=lambda path: path.name.lower(),
    )


def get_max_channel_count(lif_paths: list[Path]) -> int:
    """Find the largest channel count among all scenes in all LIF files."""
    max_channel_count = 0

    for lif_path in lif_paths:
        try:
            lif_file = LifFile(str(lif_path))
            for image in lif_file.get_iter_image():
                max_channel_count = max(max_channel_count, image.channels)
        except Exception as error:
            print(f"[WARNING] Could not inspect '{lif_path.name}': {error}")

    return max_channel_count


def process_lif_file(lif_path: Path, channel_folders: list[Path]) -> None:
    """Export every scene, channel, and mosaic tile as a TIFF Z-stack."""
    try:
        lif_file = LifFile(str(lif_path))
        images = list(lif_file.get_iter_image())
    except Exception as error:
        raise LifFileProcessorError(
            f"Could not open LIF file '{lif_path}': {error}"
        ) from error

    if not images:
        raise LifFileProcessorError(f"No scenes found in '{lif_path}'.")

    print(f"\n[Processing LIF] {lif_path} - {len(images)} scene(s) found.")

    for image in images:
        scene_name = str(image.info.get("name", "scene_Unknown"))
        safe_scene_name = scene_name.replace(" ", "_")
        x_size, y_size, z_count, _, mosaic_count = image.dims

        for channel_index in range(image.channels):
            if channel_index >= len(channel_folders):
                print(
                    f"[WARNING] Skipping channel {channel_index + 1}: "
                    "no output folder is available."
                )
                continue

            channel_folder = channel_folders[channel_index]

            for mosaic_index in range(mosaic_count):
                # Allocate the stack without filling it because every plane is replaced.
                stack = np.empty(
                    (z_count, y_size, x_size),
                    dtype=np.uint16,
                )

                for z_index in range(z_count):
                    stack[z_index] = image.get_frame(
                        z=z_index,
                        t=0,
                        c=channel_index,
                        m=mosaic_index,
                    )

                output_name = (
                    f"{lif_path.stem}_{safe_scene_name}_"
                    f"tile_{mosaic_index + 1}_C{channel_index + 1}.tif"
                )
                output_path = channel_folder / output_name

                tifffile.imwrite(
                    output_path,
                    stack,
                    photometric="minisblack",
                )
                print(f"  Saved stack: {output_path}")


def initialize_imagej() -> Any:
    """Initialize ImageJ2 in headless mode."""
    print("\nInitializing ImageJ2 in headless mode...")

    try:
        imagej_instance = imagej.init("sc.fiji:fiji", mode="headless")
    except Exception as error:
        raise ImageJInitializationError(
            f"Could not initialize ImageJ: {error}"
        ) from error

    print("ImageJ2 successfully initialized.")
    return imagej_instance


def process_folder(folder: Path) -> None:
    """Process every LIF file in one configured folder."""
    if not folder.is_dir():
        print(f"[WARNING] Folder '{folder}' does not exist; skipping.")
        return

    print(f"\n=== Processing folder: {folder} ===")

    # The output folder is created inside the path provided in the JSON file.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = create_output_folder(folder, timestamp)

    print(f"  TIFF output folder: {output_folder}")

    lif_paths = find_lif_files(folder)
    print(f"  Found {len(lif_paths)} LIF file(s).")

    if not lif_paths:
        print("  No LIF files found; skipping.")
        return

    max_channel_count = get_max_channel_count(lif_paths)
    if max_channel_count == 0:
        print("  No valid channels found; skipping.")
        return

    channel_folders = create_channel_folders(
        output_folder,
        max_channel_count,
    )

    print(f"  Starting processing of {len(lif_paths)} file(s)...")
    for lif_path in lif_paths:
        try:
            process_lif_file(lif_path, channel_folders)
        except LifFileProcessorError as error:
            print(f"[ERROR] {error}")

    print("\nFolder processing completed.")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export LIF scenes and channels as TIFF Z-stacks."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to a JSON file containing the 'paths_to_files' list.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the command-line application."""
    args = parse_arguments()

    try:
        folder_paths = load_folder_paths(args.input)
    except LifFileProcessorError as error:
        print(f"[ERROR] {error}")
        return 1

    try:
        imagej_instance = initialize_imagej()
    except ImageJInitializationError as error:
        print(f"[ERROR] {error}")
        return 1

    # Keep the ImageJ instance alive until all folders have been processed.
    _ = imagej_instance

    for folder in folder_paths:
        process_folder(folder)

    print("\nAll folders processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())