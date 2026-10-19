# MCA-tools

Multimodal Collagen Analysis Toolkit

MCA exports Leica LIF images as calibrated TIFF Z-stacks and measures SHG area
and intensity. Python uses its own `mca_tools` environment. The separate
[QuPath workflow](qupath_code) is unchanged.

## Install or update

Install Git and [Miniforge](https://github.com/conda-forge/miniforge), then:

```bash
git clone --branch main --single-branch https://github.com/alexdolskii/MCA-tools.git
cd MCA-tools
conda env create -f environment.yaml
conda activate mca_tools
python -m pip install .
python -m pip check
shg1_lif_to_tif --help
shg2_intden_assay --version
```

After updating an existing checkout, activate `mca_tools` and run
`python -m pip install .` again. The environment name is unchanged.
[environment.yaml](environment.yaml) supplies Python 3.12, OpenJDK 11 and Maven;
[pyproject.toml](pyproject.toml) declares Python dependencies. FIA is not required.

LIF export does not start Java. SHG uses the shared pinned endpoint
`sc.fiji:fiji:2.14.0` in `code/mca_tools/imagej.py`, with the Java installed in
the environment rather than a downloaded second JVM. The first Fiji start
requires network access for Maven components. Help/version do not start Fiji.

## Input and commands

[input_paths.json](input_paths.json) lists original LIF folders:

```json
{
  "paths_to_files": [
    "/Volumes/ExampleDrive/Experiment_01/Condition_A",
    "/Volumes/ExampleDrive/Experiment_01/Condition_B"
  ]
}
```

Absolute paths are recommended. Relative entries now resolve against the
JSON directory, independent of the terminal working directory. Missing,
hidden or duplicate folders are rejected. WSL paths use `/mnt/d/...`.
Dot files, including macOS `._*`, and directories named like images are
excluded from processing and input counts. An explicit `._*.json` is rejected.

Interactive workflow:

```bash
conda activate mca_tools
shg1_lif_to_tif -i input_paths.json
shg2_intden_assay -i input_paths.json
```

SHG asks for MAX/SUM, automatic/manual thresholding and start confirmation.
Invalid answers repeat the question. `q`, Ctrl+C and end-of-input cancel.
For automated use, supply all choices and `--yes`:

```bash
shg2_intden_assay -i input_paths.json --projection max --threshold-mode auto --yes
shg2_intden_assay -i input_paths.json --projection sum --threshold 2000 --yes
shg2_intden_assay -i input_paths.json --projection sum --threshold 2000 50000 --yes
```

These numeric thresholds illustrate syntax, not validated biological cutoffs.
`--threshold LOWER [UPPER]` selects manual thresholding; the default upper
bound is infinity. Automatic thresholding retains Moments. `--channel N`
selects the exported `channel_N` folder; the default is 1.

The direct launchers remain available:

```bash
python code/shg1_lif_to_tif.py -i input_paths.json
python code/shg2_intden_assay.py -i input_paths.json
```

## Native pixels and metadata

Version 0.2 removes the 1024 × 1024 resize and the filename-dependent
`merged` exception. All images retain their original XY dimensions.
Export/projection perform no resampling or intensity normalization.
LIF 8/16-bit storage is retained; source detector bit depth is recorded.
MAX preserves the pixel type; SUM is float32 even for a one-slice input.

Export includes all scenes, channels, mosaic tiles and Z slices from
**timepoint 0**, as before. Additional timepoints are recorded and warned
about, not analyzed. Scene indices and source-name digests prevent collisions.

Every exported TIFF has native pixels, calibrated X/Y resolution and Z spacing
when available. A `<image>.tif.json` sidecar preserves spatial sampling,
dimensions, scene metadata, channel/tile/timepoint and checksums. The complete
original LIF XML header is saved under `Metadata/`.

readlif reports pixels/µm; MCA stores its reciprocal, µm/pixel. X/Y are handled
independently, including non-square pixels. Missing/invalid calibration stays
missing. It is never replaced with an assumed 1 µm/pixel.

Projections, masks and masked previews retain XY dimensions and calibration.
Source references are preserved in TIFF Info and per-image JSON. Legacy TIFF,
OME-TIFF and ND2 physical sizes come from recorded metadata, not ImageJ's
default scale. ND2 uses Bio-Formats and its first image series.

The existing masked preview still receives two smoothing operations and
contrast enhancement. Measurements use the unsmoothed masked pixels.

## Outputs and selecting an export

| Stage | Location |
|---|---|
| Export | `<input>/output_<folder>_<timestamp>_<id>/channel_<N>/` |
| SHG | `<selected export>/channel_<N>/Mask_Intensity_Area_Results_<timestamp>_<id>/` |

Every run has a unique UTC timestamp/random suffix; earlier runs are never
reused or overwritten. Each has `run.log` and `run_status.json`.
SHG additionally saves projections, `Tables/`, `Masks/`, `Masked_Images/`
and `Metadata/`.

SHG selects the newest verified **SUCCESS** export with the requested channel.
Inventory and checksums are checked; empty, failed, incomplete or altered
candidates are skipped with a recorded reason.

- `--allow-partial-export` explicitly permits an audited PARTIAL export.
  Only outputs from successfully completed LIF inputs are eligible; files left
  by a failed LIF never enter the next stage.
- `--allow-legacy-export` permits old exports without a completion record,
  labelled `LEGACY_UNVERIFIED`. Their completeness cannot be established.

Re-export original LIF files to obtain reliable calibration and completion
records. Lost physical metadata cannot be reconstructed from old TIFFs alone.

## Table definitions

The table is `Tables/All_area_measurements.csv`.

| Columns | Meaning |
|---|---|
| `Original_Width_px`, `Original_Height_px` | Native XY dimensions |
| `Pixel_Width_um`, `Pixel_Height_um`, `Pixel_Depth_um` | Recorded sampling |
| `Particle_Count` | Measured particle count |
| `Total_Area_px2`, `Total_Area_um2` | Sum of particle areas, in pixels and µm² |
| `Average_Particle_Area_px2`, `Average_Particle_Area_um2` | Total area/count; zero when count is zero |
| `Image_Area_px2`, `Image_Area_um2` | Entire image area |
| `Area_Fraction_percent` | Measured area / entire image area × 100 |
| `Mean_Intensity` | Raw integrated signal / measured pixel area; blank for zero area |
| `Integrated_Density_raw` | Sum of retained raw pixel intensities |
| `Integrated_Density_um2` | Raw integrated signal × physical pixel area, in signal·µm² |
| `Calibration_Status`, `Calibration_Source` | Availability and source of physical XY sampling |
| `Threshold_Lower`, `Threshold_Upper` | Actual ImageJ thresholds, including automatic runs |

Physical area = pixel area × pixel width in µm × pixel height in µm.
Missing scale produces blank physical columns and `MISSING_XY_CALIBRATION`;
pixel measurements remain available. Intensity itself is not a length.

Source hashes, projection method/bit depth, Z/time counts and requested
thresholds are recorded. An unbounded requested upper threshold is `inf`.
Legacy ImageJ summary columns remain; their areas are pixels
(`Legacy_Area_Unit=pixel^2`). Legacy `Mean`/`IntDen` are particle-summary
statistics; new intensity columns describe the pooled measured pixels.

The existing particle range remains 0–1e9 pixels and circularity 0–1.
The positive-intensity inclusion floor remains 1 for integer pixels and
1e-4 for float32. A mask-selected zero-valued pixel therefore does not enter
measured positive area. Valid blank images retain zero count/area/summed
signal; they are not processing failures.

Results can differ from version 0.1 for images formerly resized. Record the
version and analyze comparison sets consistently.

## Status, logs and temporary files

| Status | Meaning |
|---|---|
| `SUCCESS` | All selected inputs and required outputs completed |
| `PARTIAL` | Some inputs completed and others failed |
| `FAILED` | None completed, or a run-level operation failed |
| `NO_INPUT` | No supported source images |
| `CANCELLED` | User interruption |

Damaged inputs retain errors/tracebacks while other images continue.
Run metadata records identities, hashes, parameters, versions and counts.
Exit codes: 0 complete success; 1 incomplete/failed processing; 2 invalid
arguments/configuration; 130 cancellation.

A supervised worker uses `~/.mca-tools/tmp/<run_id>/` for Python/Java temporary
files. Records and `runtime.log` remain in `~/.mca-tools/runs/<run_id>/`;
SHG also writes `imagej.log`. An absolute `MCA_RUNTIME_HOME` overrides this root.

Cleanup requires the matching ownership marker and verified worker/observed
descendant exit. Failure, partial completion or uncertain process inspection
retains temporary files. Results, caches and unrelated files are untouched.
Process inspection is sampled; records describe observed processes.
One ImageJ context is shared across folders and closed with its workers at
the command boundary.

## Development and validation

See [code/README.md](code/README.md) for architecture and checks. Tests cover
real readlif parsing of generated LIFs, native TIFF pixels, anisotropic/missing
calibration, hidden/corrupt files, result selection, CLI and temporary storage.
Native tests cover MAX/SUM, rectangular 8/16-bit images, float32, saved
calibration, zero signal and multiple folders.

Local validation used real headless ImageJ1 1.54p with ij1-patcher and a public
[readlif LIF fixture](https://github.com/Arcadia-Science/readlif/tree/master/tests/artifacts/xyzt-example).
Full initial Fiji/Maven resolution and real ND2 files still require their own
integration validation. GitHub Actions defines Linux/macOS package checks and
full pinned-Fiji checks on Linux; workflow definitions alone do not establish
a successful run.

## QuPath

[qupath_code](qupath_code) remains an independent QuPath workflow.
Its files are unchanged by this Python update.
