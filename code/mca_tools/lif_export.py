"""Export native LIF pixels with calibrated TIFFs and original metadata."""

import hashlib
import uuid
import warnings
from pathlib import Path

import numpy as np
import tifffile

from .calibration import Calibration
from .files import (
    image_files,
    output_record,
    safe_label,
    sha256_file,
    write_json,
    write_text,
)
from .lif_reader import load_lif
from .run import Run


def save_stack(path, stack, calibration, provenance):
    """Write ImageJ-compatible ZYX TIFF and validate its stored pixels."""
    metadata = {
        "axes": "ZYX",
        "unit": "um" if calibration.calibrated else "pixel",
    }
    options = {}
    if calibration.calibrated:
        options["resolution"] = (
            1 / calibration.pixel_width_um,
            1 / calibration.pixel_height_um,
        )
        options["resolutionunit"] = "NONE"
    if calibration.pixel_depth_um and calibration.calibrated:
        metadata["spacing"] = calibration.pixel_depth_um
    # A sidecar records missing Z calibration explicitly; no 1 um is assumed.
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tifffile.imwrite(
            temporary,
            stack,
            imagej=True,
            metadata=metadata,
            photometric="minisblack",
            **options,
        )
        stored = tifffile.memmap(temporary)
        if stored.dtype != stack.dtype or not np.array_equal(
            stored.reshape(stack.shape), stack
        ):
            raise ValueError(f"TIFF verification failed: {path}")
        del stored
        if path.exists():
            raise FileExistsError(
                f"Refusing to replace an existing TIFF: {path}"
            )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    sidecar = path.with_suffix(path.suffix + ".json")
    write_json(
        sidecar,
        {
            "schema_version": 1,
            "producer": "mca-tools",
            "image_sha256": sha256_file(path),
            "shape_zyx": list(stack.shape),
            "dtype": str(stack.dtype),
            "calibration": calibration.as_dict(),
            **provenance,
        },
    )
    return [path, sidecar]


def export_lif(path: Path, run: Run):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message="LIF file is likely truncated.*",
            category=UserWarning,
        )
        lif, layout = load_lif(path)
    if layout.data_end < layout.file_size:
        run.logger.info(
            "LIF_ZERO_PADDING | %s | starts_at=%d | verified_bytes=%d",
            path.name,
            layout.data_end,
            layout.file_size - layout.data_end,
        )
    images = list(lif.get_iter_image())
    if not images:
        raise ValueError("No image scenes in LIF")
    source_hash = sha256_file(path)
    # The filename digest distinguishes case/extension variants on all OSes.
    file_id = (
        safe_label(path.stem)
        + "_"
        + hashlib.sha256(path.name.encode()).hexdigest()[:8]
    )
    metadata_folder = run.directory / "Metadata"
    metadata_folder.mkdir(exist_ok=True)
    xml_path = metadata_folder / f"{file_id}.xml"
    write_text(xml_path, lif.xml_header)
    outputs = [xml_path]
    for scene_index, image in enumerate(images, 1):
        if tuple(image.display_dims) != (1, 2):
            raise ValueError("Only XY LIF scenes are supported")
        width, height, nz, nt, nm = image.dims
        if min(width, height, nz, nt, nm, image.channels) < 1:
            raise ValueError("Invalid LIF dimensions")
        calibration = Calibration.from_lif(image)
        if not calibration.calibrated:
            run.logger.warning(
                "MISSING_XY_CALIBRATION | %s | scene=%d",
                path.name,
                scene_index,
            )
        if nt > 1:
            run.logger.warning(
                "FIRST_TIMEPOINT_ONLY | %s | available=%d", path.name, nt
            )
        for channel in range(image.channels):
            destination = run.directory / f"channel_{channel + 1}"
            destination.mkdir(exist_ok=True)
            for tile in range(nm):
                stack = None
                for z in range(nz):
                    plane = np.asarray(
                        image.get_frame(z=z, t=0, c=channel, m=tile)
                    )
                    if plane.shape != (height, width) or plane.dtype not in (
                        np.uint8,
                        np.uint16,
                    ):
                        raise ValueError(
                            "Unexpected LIF plane dimensions or pixel type"
                        )
                    if stack is None:
                        stack = np.empty(
                            (nz, height, width), dtype=plane.dtype
                        )
                    if plane.dtype != stack.dtype:
                        raise ValueError(
                            "Pixel type changes within a LIF Z-stack"
                        )
                    stack[z] = plane
                name = (
                    f"{file_id}_{safe_label(image.name)}_S{scene_index:03d}"
                    f"_tile_{tile + 1}_C{channel + 1}.tif"
                )
                provenance = {
                    "lif_structure": layout.as_dict(),
                    "source_lif": str(path),
                    "source_sha256": source_hash,
                    "source_xml": xml_path.relative_to(
                        run.directory
                    ).as_posix(),
                    "scene_index": scene_index,
                    "scene_name": image.name,
                    "channel": channel + 1,
                    "timepoint": 0,
                    "tile": tile + 1,
                    "source_dimensions_xyztm": list(image.dims),
                    "scene_metadata": image.info,
                }
                outputs.extend(
                    save_stack(
                        destination / name, stack, calibration, provenance
                    )
                )
    return [output_record(p, run.directory) for p in outputs]


def run_export(folders, input_json):
    statuses = []
    for folder in folders:
        files = image_files(folder, {".lif"})
        run = Run(
            folder,
            f"output_{safe_label(folder.name)}",
            "lif_export",
            files,
            {
                "input_json": str(input_json),
                "timepoint": 0,
                "preserve_xy": True,
                "preserve_pixel_values": True,
            },
        )
        with run:
            hidden = sum(
                p.is_file() and p.name.startswith(".")
                for p in folder.iterdir()
            )
            run.logger.info(
                "INPUTS | selected=%d | ignored_hidden=%d", len(files), hidden
            )
            for record, path in zip(run.data["images"], files):
                try:
                    outputs = export_lif(path, run)
                except Exception as error:
                    run.record_failure(record, error)
                else:
                    run.record_success(record, outputs)
        statuses.append(run.data["status"])
    return 0 if statuses and all(s == "SUCCESS" for s in statuses) else 1
