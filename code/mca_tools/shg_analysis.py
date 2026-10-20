"""Native-size SHG analysis with explicit pixel and physical measurements."""

import json
import logging
import math
import os
import sys
from contextlib import ExitStack
from pathlib import Path

import pandas as pd
import scyjava as sj

from .calibration import Calibration, measurement_columns
from .discovery import select_export, select_tiff_inputs
from .fiji_config import FIJI_ENDPOINT
from .files import output_record, sha256_file, write_json
from .imagej import session
from .metadata import nd2_calibration, tiff_calibration, tiff_layout
from .run import Run
from .shg_imagej import (
    ImageProcessingError,
    close_images,
    create_binary_mask,
    create_masked_intensity_image,
    create_projection,
    save_tiff,
)


def open_image(path):
    """Use Bio-Formats for ND2; preserve the original calibration."""
    if path.suffix.lower() == ".nd2":
        options = sj.jimport("loci.plugins.in.ImporterOptions")()
        options.setId(str(path))
        options.setQuiet(True)
        options.setWindowless(True)
        images = sj.jimport("loci.plugins.BF").openImagePlus(options)
        if images is None or len(images) != 1:
            if images is not None:
                close_images(*images)
            raise ImageProcessingError("Expected one ND2 image series")
        return images[0]
    image = sj.jimport("ij.IJ").openImage(str(path))
    if image is None:
        raise ImageProcessingError(f"Cannot open image: {path}")
    return image


def input_calibration(path, image):
    sidecar = path.with_suffix(path.suffix + ".json")
    if sidecar.is_file():
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if data.get("producer") == "mca-tools":
            if data.get("schema_version") != 1 or data.get(
                "image_sha256"
            ) != sha256_file(path):
                raise ImageProcessingError(
                    "TIFF differs from its calibration metadata"
                )
            if data["shape_zyx"][-2:] != [image.getHeight(), image.getWidth()]:
                raise ImageProcessingError(
                    "TIFF dimensions differ from metadata"
                )
            return Calibration.from_dict(data["calibration"]), data
    return (
        nd2_calibration(path)
        if path.suffix.lower() == ".nd2"
        else tiff_calibration(path)
    )


def analyze_particles(original, mask, masked_path):
    """Keep the established particle criteria; measure on an unscaled copy."""
    IJ = sj.jimport("ij.IJ")
    ParticleAnalyzer = sj.jimport("ij.plugin.filter.ParticleAnalyzer")
    ResultsTable = sj.jimport("ij.measure.ResultsTable")
    Measurements = sj.jimport("ij.measure.Measurements")
    masked = create_masked_intensity_image(original, mask)
    preview = pixel_image = None
    try:
        # This existing smoothed preview is never used for measurements.
        preview = masked.duplicate()
        IJ.run(preview, "Smooth", "")
        IJ.run(preview, "Smooth", "")
        IJ.run(preview, "Enhance Contrast...", "saturated=0.35")
        save_tiff(preview, masked_path)

        pixel_image = masked.duplicate()
        pixel_cal = pixel_image.getCalibration().copy()
        pixel_cal.pixelWidth = pixel_cal.pixelHeight = pixel_cal.pixelDepth = (
            1.0
        )
        pixel_cal.setUnit("pixel")
        pixel_cal.setYUnit("pixel")
        pixel_cal.setZUnit("pixel")
        pixel_cal.disableDensityCalibration()
        pixel_image.setCalibration(pixel_cal)
        lower = 1e-4 if pixel_image.getBitDepth() == 32 else 1.0
        IJ.setThreshold(pixel_image, lower, float("inf"))
        sj.jimport("ij.Prefs").blackBackground = True
        summary, particles = ResultsTable(), ResultsTable()
        ParticleAnalyzer.setSummaryTable(summary)
        measurements = (
            Measurements.AREA
            | Measurements.MEDIAN
            | Measurements.MEAN
            | Measurements.INTEGRATED_DENSITY
            | Measurements.LIMIT
        )
        analyzer = ParticleAnalyzer(
            ParticleAnalyzer.SHOW_SUMMARY,
            measurements,
            particles,
            0.0,
            1e9,
            0.0,
            1.0,
        )
        if not analyzer.analyze(pixel_image):
            raise ImageProcessingError("ParticleAnalyzer failed")
        count = int(particles.getCounter())
        area = sum(float(particles.getValue("Area", i)) for i in range(count))
        raw = sum(
            float(particles.getValue("RawIntDen", i)) for i in range(count)
        )
        legacy = (
            {
                str(h): float(summary.getValue(h, 0))
                for h in summary.getHeadings()
            }
            if summary.getCounter()
            else {
                "Count": 0,
                "Total Area": 0.0,
                "Average Size": 0.0,
                "%Area": 0.0,
            }
        )
        return legacy, count, area, raw
    finally:
        close_images(pixel_image, preview, masked)


def process_image(
    path,
    run,
    projection_method,
    threshold_mode,
    threshold_range,
    input_source="export",
):
    IJ = sj.jimport("ij.IJ")
    source = channel = projection = saved = mask = None
    try:
        layout = (
            tiff_layout(path)
            if path.suffix.lower() in {".tif", ".tiff"}
            else None
        )
        source = open_image(path)
        width, height = int(source.getWidth()), int(source.getHeight())
        original_depth = int(source.getBitDepth())
        nz, nt = int(source.getNSlices()), int(source.getNFrames())
        if layout:
            if (
                [nz, height, width] != layout["shape_zyx"]
                or source.getNChannels() != 1
                or nt != 1
                or original_depth
                != {"uint8": 8, "uint16": 16, "float32": 32}[layout["dtype"]]
            ):
                raise ImageProcessingError(
                    "ImageJ TIFF interpretation differs from its dimensions/type; "
                    "export an ImageJ-compatible single-channel YX/ZYX TIFF"
                )
            if layout["assumed_z_stack"]:
                run.logger.warning(
                    "ASSUMED_Z_STACK | %s | unlabelled pages treated as Z slices",
                    path.name,
                )
        calibration, source_metadata = input_calibration(path, source)
        calibration.apply(source)
        if not calibration.calibrated:
            run.logger.warning(
                "MISSING_XY_CALIBRATION | %s | physical fields are blank",
                path.name,
            )
        channel = sj.jimport("ij.plugin.Duplicator")().run(
            source, 1, 1, 1, nz, 1, 1
        )
        calibration.apply(channel)
        projection = create_projection(channel, projection_method)
        calibration.apply(projection)
        provenance = {
            "input": str(path),
            "input_sha256": sha256_file(path),
            "calibration": calibration.as_dict(),
            "source_z_slices": nz,
            "source_timepoints": nt,
            "selected_timepoint": 0,
            "source_metadata": source_metadata,
            "input_source": input_source,
            "tiff_layout": layout,
        }
        projection.setProperty("Info", json.dumps(provenance))
        output = run.directory / f"{path.stem}_processed.tif"
        save_tiff(projection, output)
        saved = IJ.openImage(str(output))
        if saved is None or (saved.getWidth(), saved.getHeight()) != (
            width,
            height,
        ):
            raise ImageProcessingError("Saved TIFF lost the native dimensions")
        expected_depth = 32 if projection_method == "sum" else original_depth
        if saved.getBitDepth() != expected_depth:
            raise ImageProcessingError("Saved projection changed pixel type")
        # Verify the stored XY scale before reapplying explicit missing-Z state.
        stored_cal = Calibration.from_imagej(saved)
        if calibration.calibrated:
            if (
                not stored_cal.calibrated
                or not math.isclose(
                    calibration.pixel_width_um,
                    stored_cal.pixel_width_um,
                    rel_tol=1e-6,
                )
                or not math.isclose(
                    calibration.pixel_height_um,
                    stored_cal.pixel_height_um,
                    rel_tol=1e-6,
                )
            ):
                raise ImageProcessingError(
                    "Saved TIFF lost its spatial calibration"
                )
        calibration.apply(saved)
        mask = create_binary_mask(saved, threshold_mode, threshold_range)
        calibration.apply(mask)
        mask.setProperty("Info", json.dumps(provenance))
        mask_path = run.directory / "Masks" / f"{path.stem}_mask.tif"
        save_tiff(mask, mask_path)
        masked_path = (
            run.directory / "Masked_Images" / f"{path.stem}_masked.tif"
        )
        legacy, count, area, raw = analyze_particles(saved, mask, masked_path)
        row = {
            **legacy,
            **measurement_columns(
                count, area, raw, width, height, calibration
            ),
            "Image_Filename": path.name,
            "Input_Source": input_source,
            "Image_Group": "merged"
            if "merged" in path.name.casefold()
            else "individual",
            "Original_Bit_Depth": original_depth,
            "Original_Width_px": width,
            "Original_Height_px": height,
            "Projection_Method": projection_method.upper(),
            "Projection_Bit_Depth": expected_depth,
            "Source_Z_Slices": nz,
            "Source_Timepoints": nt,
            "Selected_Timepoint": 0,
            "Threshold_Mode": threshold_mode,
            "Threshold_Method": "Moments dark"
            if threshold_mode == "auto"
            else "manual",
            "Threshold_Lower": float(
                str(mask.getProperty("mca.threshold.lower"))
            ),
            "Threshold_Upper": float(
                str(mask.getProperty("mca.threshold.upper"))
            ),
            "Requested_Threshold_Lower": threshold_range[0]
            if threshold_range
            else None,
            "Requested_Threshold_Upper": (
                threshold_range[1]
                if math.isfinite(threshold_range[1])
                else "inf"
            )
            if threshold_range
            else None,
            "Legacy_Area_Unit": "pixel^2",
            "Input_SHA256": provenance["input_sha256"],
        }
        metadata_path = run.directory / "Metadata" / f"{path.stem}.json"
        write_json(metadata_path, {**provenance, "measurement": row})
        outputs = [
            output_record(p, run.directory)
            for p in (output, mask_path, masked_path, metadata_path)
        ]
        return row, outputs
    finally:
        close_images(mask, saved, projection, channel, source)


def run_analysis(folders, args):
    """Share one Fiji context across folders and close it once per command."""
    logger = logging.Logger("mca.imagej", logging.INFO)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    if os.environ.get("MCA_RUN_DIR"):
        logger.addHandler(
            logging.FileHandler(
                Path(os.environ["MCA_RUN_DIR"]) / "imagej.log",
                encoding="utf-8",
            )
        )
    try:
        with ExitStack() as contexts:
            return _run_analysis(folders, args, contexts, logger)
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def _run_analysis(folders, args, contexts, logger):
    statuses = []
    initialized = False
    startup_error = None
    external = args.input_source == "tiff"
    selections = select_tiff_inputs(folders) if external else folders
    for item in selections:
        folder = item.directory if external else item
        # Selection failures also get a persistent run journal.
        selection = selection_error = None
        try:
            selection = (
                item
                if external
                else select_export(
                    folder,
                    args.channel,
                    args.allow_partial_export,
                    args.allow_legacy_export,
                )
            )
        except (OSError, ValueError) as error:
            selection_error = error
        files = selection.files if selection else []
        parent = (
            selection.directory / f"channel_{args.channel}"
            if selection and not external
            else folder
        )
        parameters = {
            "input_json": str(args.input),
            "input_source": args.input_source,
            "projection": args.projection,
            "threshold_mode": args.threshold_mode,
            "threshold_method": "Moments dark"
            if args.threshold_mode == "auto"
            else "manual",
            "threshold_range": [
                value if math.isfinite(value) else "inf"
                for value in args.threshold
            ]
            if args.threshold
            else None,
            "channel": args.channel,
            "fiji_endpoint": FIJI_ENDPOINT,
            "export_run": str(selection.directory)
            if selection and not external
            else None,
            "export_status": selection.status
            if selection and not external
            else None,
            "preserve_xy": True,
        }
        run = Run(
            parent,
            "Mask_Intensity_Area_Results",
            "shg_analysis",
            files,
            parameters,
        )
        try:
            with run:
                if selection_error:
                    raise selection_error
                if not files:
                    raise ValueError(
                        f"No TIFF inputs directly inside {folder}"
                    )
                for warning in selection.warnings:
                    run.logger.warning(warning)
                for name in ("Tables", "Masks", "Masked_Images", "Metadata"):
                    (run.directory / name).mkdir()
                stems = [p.stem.casefold() for p in files]
                if len(stems) != len(set(stems)):
                    raise ValueError(
                        "Several inputs have the same output filename stem"
                    )
                rows = []
                if startup_error is not None:
                    raise RuntimeError(
                        "ImageJ initialization previously failed"
                    ) from startup_error
                if not initialized:
                    try:
                        contexts.enter_context(session(logger))
                    except Exception as error:
                        startup_error = error
                        raise
                    initialized = True
                run.data["software"]["imagej1"] = str(
                    sj.jimport("ij.IJ").getVersion()
                )
                run.data["software"]["java"] = str(
                    sj.jimport("java.lang.System").getProperty("java.version")
                )
                if initialized:
                    for record, path in zip(run.data["images"], files):
                        try:
                            row, outputs = process_image(
                                path,
                                run,
                                args.projection,
                                args.threshold_mode,
                                args.threshold,
                                args.input_source,
                            )
                        except Exception as error:
                            run.record_failure(record, error)
                        else:
                            rows.append(row)
                            run.record_success(record, outputs)
                            run.logger.info(
                                "PROGRESS | saved=%d/%d", len(rows), len(files)
                            )
                    if rows:
                        table = pd.DataFrame(rows)
                        run.data["summaries"] = {}
                        for group in ("individual", "merged"):
                            summary = (
                                run.directory
                                / "Tables"
                                / f"Area_measurements_{group}.csv"
                            )
                            selected = table[table["Image_Group"] == group]
                            temporary = summary.with_suffix(".csv.tmp")
                            selected.to_csv(temporary, index=False)
                            temporary.replace(summary)
                            run.data["summaries"][group] = {
                                **output_record(summary, run.directory),
                                "rows": len(selected),
                            }
        except Exception as error:
            # The Run context has saved the traceback and FAILED state.
            print(f"FAILED: {folder}: {error}", file=sys.stderr)
            statuses.append("FAILED")
            continue
        statuses.append(run.data["status"])
    return 0 if statuses and all(s == "SUCCESS" for s in statuses) else 1
