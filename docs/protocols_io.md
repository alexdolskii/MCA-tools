# Native-resolution SHG area and intensity analysis from Leica LIF files using MCA-tools

This is a standalone text for a protocols.io draft. It has not been published
to protocols.io. Copy the title, abstract, materials and numbered procedure
into the corresponding protocol fields. Record the software version and
validate masks and calibration for the experimental dataset being analyzed.

For Herovici-stained histological images, use the independent
[QuPath/Colour Deconvolution2 protocol](protocols_io_qupath_herovici.md).
That protocol adapts [Samyukta et al. (2022)](https://pubmed.ncbi.nlm.nih.gov/36037140/),
runs inside QuPath and has its own software requirements,
measurement definitions and validation status.

## Protocol status and version

Documentation date: 20 October 2026. Software: MCA-tools 0.2.3.
This release adds LIF block validation and read-only handling of verified
zero-filled tails, avoiding readlif's misleading closed-file error.
Unknown nonzero tails, truncated blocks and inconsistent memory sizes still
stop export. The `LIF_ZERO_PADDING` log entry and `lif_structure` sidecar
fields record accepted padding; source pixels and XML remain unchanged.

The environment aligns Python 3.10 and NumPy 1.26.4 with FIA `tech_dev` and UMA
`UMA-tools-V2`, retaining a separate MCA environment. tifffile 2025.5.10
is used because subsequent releases dropped Python 3.10 support; readlif
0.6.5 is used because 0.6.6 requires NumPy 2.

Version 0.2.1 replaces the PyImageJ 1.8.0 startup path that failed in 0.2.0
with the same pinned Java bridge used by FIA `tech_dev` and UMA `UMA-tools-V2`.
Fiji settings and Bio-Formats' official OME Maven repository are configured
in `code/mca_tools/fiji_config.py` so that dependencies can be downloaded on
a new computer without an existing cache.
Maven is pinned to 3.9.9 because Maven 3.10 is incompatible with this jgo
dependency-resolution path.
Full-Fiji integration checks cover Linux and macOS, including export followed
by MAX and SUM analysis through the installed commands, measurement checks
and process termination. The test record is available in
[GitHub Actions](https://github.com/alexdolskii/MCA-tools/actions/runs/39441858607).
That earlier run tested MCA 0.2.1 at commit
`823531cdfd49e663d637bb6f66e1560f4f2b9654`: 26 Python tests and 8 full-Fiji
tests passed on each system with normal process exit. For the Python 3.10
release, consult the checks for the installed revision in
[GitHub Actions](https://github.com/alexdolskii/MCA-tools/actions/workflows/python.yml).
Record the exact version actually used when adapting this protocol. Software
integration testing does not substitute for experimental image quality control.

## Abstract

This computational workflow exports Leica LIF microscopy data to TIFF
Z-stacks and measures second-harmonic generation (SHG) signal area and
intensity using MCA-tools. Export retains native XY dimensions, original
pixel values, available spatial calibration and source metadata. A maximum
or sum Z-projection is thresholded to obtain a binary mask. Measurements are
calculated from unsmoothed masked projection pixels and reported in a CSV
table. Areas are provided in pixel² and, when trustworthy XY calibration is
available, µm². Per-image metadata, processing parameters, checksums and run
logs support traceability.

The workflow analyzes timepoint 0 and reports projected two-dimensional
measurements. It does not quantify three-dimensional collagen volume or
automatically perform group statistics. The QuPath workflow is described
in the companion protocol linked above and is not a stage of this SHG procedure.

## Keywords

Second-harmonic generation; SHG; collagen; Leica LIF; ImageJ; Fiji;
image analysis; spatial calibration; Conda; MCA-tools.

## Materials and software

| Item | Requirement / role |
|---|---|
| Computer | macOS or Linux; a Windows installation route using Ubuntu in WSL 2 is described below |
| Memory and storage | Sufficient for the largest native stack, working copies, exported TIFFs and retained result runs; requirements depend on the dataset |
| Internet connection | Required for installation and initial Fiji/Maven component download |
| Miniforge | Provides Conda and an isolated `mca_tools` environment |
| Git | Retrieves the software and identifies its exact commit |
| Visual Studio Code and Microsoft's Python extension | Edits the configuration and provides a terminal |
| MCA-tools | Repository: https://github.com/alexdolskii/MCA-tools |
| Fiji desktop, optional viewer | Opens TIFF stacks, projections and masks for inspection |
| CSV viewer | Excel, LibreOffice Calc or equivalent; VS Code can also show CSV text |
| Input data | Original Leica `.lif` files, with acquisition metadata including pixel dimensions and the identity of the SHG channel |

The environment file specifies Python 3.10, OpenJDK 11 and Maven 3.9.9. The
package pins NumPy 1.26.4, PyImageJ 1.5.0, readlif 0.6.5, scyjava 1.10.0,
jgo 1.0.4 and tifffile 2025.5.10. Shared UMA-compatible ranges are pandas
>=2.1,<3, Pillow >=10.1,<13 and psutil >=5.9,<8.
The Fiji endpoint is `sc.fiji:fiji:2.14.0`. Installation resolves dependencies
from the repository files. MCA has its own environment and does not require
FIA-tools. Native Windows, WSL and real ND2 inputs have not received complete
workflow validation in this release.

## Before starting

Retain original acquisition files and use a small representative test set
before processing the full experiment. Record the intended SHG channel,
acquisition settings, Z sampling, projection method and threshold policy.
Use a consistent, justified policy across comparison groups. Automatic
thresholds are calculated separately per image; a fixed manual threshold
must be justified for the acquisition and projection being analyzed.

Only the first timepoint, indexed as 0, is exported. All scenes, channels,
tiles and Z slices from that timepoint are included. Tiles are analyzed
separately; the workflow does not stitch mosaics or remove overlap between
tiles. Exported images and their metadata files must remain together.

Installation and computation times vary with network speed, image size and
the number of images. No fixed processing time is assumed.

## Procedure

### 1. Prepare the operating system and terminal

On macOS, open **Applications → Utilities → Terminal**. On Linux, open a
terminal. The following commands use a Unix shell.

On Windows, first install Ubuntu under WSL 2 using Microsoft's
[WSL guide](https://learn.microsoft.com/en-us/windows/wsl/install). On a
supported Windows 10/11 installation, open PowerShell as Administrator:

```powershell
wsl --install
```

Restart if requested, launch Ubuntu and create a Linux username/password.
Run all remaining Conda and MCA commands inside Ubuntu. Install VS Code on
Windows with **Add to PATH** enabled and add Microsoft's **WSL** extension.
This installation route does not itself establish MCA validation on WSL.

### 2. Install Miniforge and Git

Download the `.sh` installer matching the operating system and architecture
from [Miniforge releases](https://github.com/conda-forge/miniforge/releases/latest).
Run `uname -m` to identify the architecture.

| Platform | Installer |
|---|---|
| Apple Silicon Mac | `Miniforge3-MacOSX-arm64.sh` |
| Intel Mac | `Miniforge3-MacOSX-x86_64.sh` |
| Intel/AMD Linux or WSL | `Miniforge3-Linux-x86_64.sh` |
| ARM Linux or WSL | `Miniforge3-Linux-aarch64.sh` |

For example, if an Apple Silicon Mac saved the installer in Downloads:

```bash
bash ~/Downloads/Miniforge3-MacOSX-arm64.sh
```

Substitute the actual path and filename for other systems. Inside WSL, use
the Linux installer; a browser download may be under
`/mnt/c/Users/YourWindowsName/Downloads/`. Quote paths containing spaces.
Accept shell initialization during installation, then close and reopen the
terminal. Verify Conda and install Git:

```bash
conda --version
conda install -n base -c conda-forge git
conda run -n base git --version
```

### 3. Download MCA-tools and create its own environment

Execute one line at a time and wait for completion:

```bash
mkdir -p ~/projects
cd ~/projects
conda run -n base git clone --branch main --single-branch https://github.com/alexdolskii/MCA-tools.git
cd MCA-tools
conda env create -f environment.yaml
conda run -n mca_tools python -m pip install .
conda activate mca_tools
```

Accept Conda's confirmation prompts. The final dot installs the project in
the current directory. Create the environment once; activate it again for
later sessions. Separate Python, Java and desktop Fiji installations are
not required for package installation.

Stop if environment creation fails. The explicit `conda run -n mca_tools`
command prevents installation into `base` after a failed activation.
For `CondaSSLError`, follow the README's
[certificate and channel troubleshooting](https://github.com/alexdolskii/MCA-tools#conda-certificate-and-channel-errors).
Conda can use `CONDA_SSL_VERIFY=truststore` when the institution's certificate
is already trusted by the operating system (Conda >=23.9; base Python >=3.10).
Otherwise obtain the institution's CA bundle from IT. Keep certificate
verification enabled; dependency changes do not fix certificate trust.

### 4. Verify software installation and record the version

```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pip check
java -version
mvn -version
shg1_lif_to_tif --help
shg2_intden_assay --version
conda run -n base git rev-parse HEAD
```

Expect Python 3.10.x from `envs/mca_tools`, no broken pip requirements, Java
11, Maven 3.9.9, and the MCA command help/version. Record the
package version and commit hash. Optionally save the resolved installation
for the experiment record:

```bash
conda env export -n mca_tools > mca_environment_record.yaml
python -m pip freeze > mca_python_packages_record.txt
conda run -n base git rev-parse HEAD > mca_commit_record.txt
```

These checks do not start Fiji. Use MCA 0.2.3 with the dependencies declared
by that checkout. When upgrading from the Python 3.12 environment of MCA
0.2.0/0.2.1, create a fresh environment and preserve the old one:

```bash
conda run -n base git pull --ff-only
conda env create -n mca_tools_py310 -f environment.yaml
conda run -n mca_tools_py310 python -m pip install .
conda run -n mca_tools_py310 python -m pip check
conda activate mca_tools_py310
```

Use `mca_tools_py310` in subsequent commands and VS Code after this migration.
If the earlier environment was never created, use the standard `mca_tools`
installation instead. Changing the endpoint alone does not update Python,
Maven or the Python bridge.
Review the full Fiji test record for the
installed revision, then confirm the complete workflow on representative data.

### 5. Configure Visual Studio Code

Install [Visual Studio Code](https://code.visualstudio.com/download) and the
**Python** extension published by Microsoft (`ms-python.python`). This is
VS Code, not the Visual Studio IDE.

Open `~/projects/MCA-tools` using **File → Open Folder** on macOS/Linux. On
WSL, run `code .` inside that directory in Ubuntu and install the Python
extension in the WSL environment when prompted.

Open the Command Palette (**Cmd+Shift+P** on macOS; **Ctrl+Shift+P** on
Windows/Linux), choose **Python: Select Interpreter** and select `mca_tools`.
If it is absent, select the executable path printed in step 4. Open
**Terminal → New Terminal**:

```bash
cd ~/projects/MCA-tools
conda activate mca_tools
python -c "import sys; print(sys.executable)"
```

Confirm that the terminal also uses `mca_tools`. Execute the following
commands in the terminal; the editor's Run button does not supply the
necessary input configuration.

### 6. Organize inputs and save the JSON configuration

Place original LIF files directly in writable experiment folders outside
the software checkout. Processing is not recursive. For an initial trial,
use a separate folder containing copies of a few representative files.

Create `my_input_paths.json` in the MCA-tools project root in VS Code:

```json
{
  "paths_to_files": [
    "/Volumes/ExampleDrive/Experiment_01/Condition_A",
    "/Volumes/ExampleDrive/Experiment_01/Condition_B"
  ]
}
```

Replace the paths with real folders. A Linux path might be
`/home/yourname/data/Condition_A`; a Windows D: drive folder in WSL might be
`/mnt/d/Experiment_01/Condition_A`. Confirm that external drives are mounted
and writable. List folders, not individual LIFs or exported channel folders.
Use double quotes, commas between entries and no trailing comma or comments.
Save with **Cmd+S / Ctrl+S**.

Absolute paths are recommended. Relative entries are resolved against the
JSON's directory. Hidden files, including macOS `._*`, are ignored and not
counted as inputs. Missing, hidden or repeated input folders are rejected.

### 7. Export LIF data to calibrated TIFF stacks

```bash
shg1_lif_to_tif -i my_input_paths.json
```

Wait for the terminal prompt to return. For each listed folder, locate the
printed output directory:

`<input>/output_<folder>_<timestamp>_<id>/`

It contains `channel_1/`, additional channel directories as appropriate,
TIFF/JSON pairs, `Metadata/`, `run.log` and `run_status.json`.
Timestamps use UTC and the suffix distinguishes separate runs.

### 8. Verify export before proceeding

Open `run_status.json` in each export. Require `SUCCESS`, zero failed inputs
and zero unprocessed inputs for the standard complete workflow. Export input
counts refer to LIF files; each LIF may produce several TIFFs.

Inspect representative TIFFs in the optional
[Fiji desktop application](https://imagej.net/software/fiji/) using
**File → Open**. Confirm original width/height, Z slices and the SHG channel.
Check sampling against the acquisition metadata and the adjacent
`<image>.tif.json`. Keep all TIFFs, sidecars, source XML and run records
together and unmodified. Altering audited files can cause selection to fail.

XY dimensions and original values are preserved; there is no resize to
1024 × 1024 or intensity normalization. readlif sampling in pixels/µm is
converted to µm/pixel. Unknown or invalid calibration remains missing.
The complete original LIF XML is retained in `Metadata/`.

### 9. Choose analysis settings and start SHG processing

Confirm the installed software version as described in step 4 and which
exported channel represents SHG; channel 1 is only the
default. For channel 1, run:

```bash
shg2_intden_assay -i my_input_paths.json --channel 1
```

The JSON continues to list the original folders. For each one, MCA selects
the newest verified successful export containing the requested channel.
Check the selected `export_run` in the analysis metadata; if a newer export
is incomplete or altered, an older valid export may be selected instead.

| Question | Response and meaning |
|---|---|
| Projection | Enter `max` / `1` for a maximum Z-projection, or `sum` / `2` for a sum Z-projection |
| Threshold mode | Enter `auto` for ImageJ Moments, or `manual` for explicit intensity bounds |
| Manual bounds | Enter lower and upper thresholds in projection intensity units; Enter defaults to 0 and `inf` |
| Start confirmation | Enter `yes` to proceed |

SUM adds intensities across Z and is saved as float32. MAX retains the
source pixel type. SUM depends on the number of slices; manual thresholds
cannot be transferred blindly between projection methods or acquisition
settings. Use representative images to assess whether the selected policy
captures the intended signal.

For a noninteractive MAX/Moments run:

```bash
shg2_intden_assay -i my_input_paths.json --channel 1 --projection max --threshold-mode auto --yes
```

A manual syntax example is:

```bash
shg2_intden_assay -i my_input_paths.json --channel 1 --projection sum --threshold 2000 50000 --yes
```

**2000 and 50000 are illustrative values, not recommended biological
cutoffs.** A single bound such as `--threshold 2000` leaves the upper bound
unlimited. Replace `--channel 1` if another exported channel contains SHG.
Record the complete command and the actual settings used.

Fiji runs headlessly, without a GUI. Its initial Maven component download
requires network access. Enter `q` at a prompt or press Ctrl+C to cancel.
The normal end of processing returns the terminal prompt and saves a final
status; a returned prompt alone does not indicate success.

### 10. Inspect images and completion records

For each selected export/channel, open:

`<export>/channel_<N>/Mask_Intensity_Area_Results_<timestamp>_<id>/`

| Output | Appearance and interpretation |
|---|---|
| `<image>_processed.tif` | Native-XY grayscale 2D projection |
| `Masks/<image>_mask.tif` | White selected regions on a black background; 8-bit binary mask |
| `Masked_Images/<image>_masked.tif` | Masked preview with two smoothing operations and contrast enhancement |
| `Tables/All_area_measurements.csv` | One row per successfully analyzed TIFF |
| `Metadata/<image>.json` | Calibration, source provenance and measurements |
| `run_status.json` and `run.log` | Parameters, selected export, counts, per-image outcomes and errors |

Require `SUCCESS` and reconcile counts with the expected TIFF inputs. A CSV
can exist for a partial run; its presence does not establish completeness.
Each listed input folder produces a separate result table.

In Fiji, compare projections with their masks and inspect background
selection or missed signal across representative conditions. Use
**Image → Properties** to inspect dimensions/sampling. Adjust the display
range through **Image → Adjust → Brightness/Contrast** if needed, especially
for SUM images, without applying a pixel transformation or overwriting
audited files. Numerical measurements use unsmoothed masked pixels; the
smoothed preview is for inspection.

### 11. Read the measurement table

Import `All_area_measurements.csv` with a comma delimiter and dot decimal
separator into a table viewer. Retain the original CSV as the analysis
record. The main fields are:

| Field | Definition |
|---|---|
| `Image_Filename` | Analyzed input TIFF identifier |
| `Original_Width_px`, `Original_Height_px` | Native image dimensions |
| `Pixel_Width_um`, `Pixel_Height_um`, `Pixel_Depth_um` | Available physical sampling |
| `Particle_Count` | Number of measured positive-signal particles |
| `Total_Area_px2`, `Total_Area_um2` | Sum of measured particle areas |
| `Average_Particle_Area_px2`, `Average_Particle_Area_um2` | Total measured area divided by count; zero when count is zero |
| `Image_Area_px2`, `Image_Area_um2` | Full projected image area |
| `Area_Fraction_percent` | Measured area / full image area × 100 |
| `Mean_Intensity` | Raw integrated signal divided by measured pixel area |
| `Integrated_Density_raw` | Sum of retained raw projection pixel intensities |
| `Integrated_Density_um2` | Raw integrated signal × physical pixel area, in signal·µm² |
| `Calibration_Status`, `Calibration_Source` | Presence and source of trustworthy XY scale |
| `Projection_Method`, `Threshold_Mode`, `Threshold_Lower`, `Threshold_Upper` | Recorded processing choices and actual threshold bounds |

For pixel width `sx` and pixel height `sy`, both in µm/pixel:

`area_um2 = area_px2 × sx × sy`

The calculation supports different X and Y sampling. Intensity is not a
length measurement. These results describe a 2D projection, even when
`Pixel_Depth_um` is available; they are not voxel counts or µm³ volumes.

When XY calibration is missing, physical fields remain blank and the status
is `MISSING_XY_CALIBRATION`. Pixel measurements remain available. A valid
image without measured signal has zero count, area and summed signal;
its mean intensity is blank. Missing calibration is not equivalent to a
zero-area result.

Legacy ImageJ summary columns are also retained. Their areas are in pixel²,
as stated by `Legacy_Area_Unit`; their `Mean` and `IntDen` are particle-summary
statistics. Use the explicitly named fields above for pooled signal
measurements.

### 12. Compare with an illustrative numerical example

This is a calculation example, not an experimental result. Consider a
7 × 5-pixel image with six retained signal pixels, sampling of
0.5 × 0.25 µm/pixel, and intensities 10, 20 and 30 at each signal position
across three Z slices. Assume the threshold retains those six positions.

| Measurement | MAX | SUM |
|---|---:|---:|
| Measured area (pixel²) | 6 | 6 |
| Measured area (µm²) | 0.75 | 0.75 |
| Entire image area (pixel² / µm²) | 35 / 4.375 | 35 / 4.375 |
| Area fraction (%) | 17.1429 | 17.1429 |
| Mean intensity | 30 | 60 |
| Raw integrated density | 180 | 360 |
| Physical integrated density (signal·µm²) | 22.5 | 45 |

For example, measured physical area is `6 × 0.5 × 0.25 = 0.75 µm²`.

### 13. Archive the analysis and repeat consistently

Retain original LIFs, the input JSON, exported TIFFs and sidecars, source
XML, all result directories, exact commands, software version/commit and
environment records. No group statistics or plots are generated automatically.
Document any subsequent table combination, exclusions or statistical analysis
separately. Scene/tile rows are not automatically independent biological
replicates; retain the mapping to specimens.

For another session:

```bash
cd ~/projects/MCA-tools
conda activate mca_tools
```

Reusing a verified export is sufficient when only SHG settings change. Each
analysis creates a new output directory and preserves previous runs. When
finished, `conda deactivate` leaves the MCA environment. Avoid updating
software partway through a comparison set without assessing or reprocessing
the affected data.

## Quality-control criteria and limitations

- Both stages must finish successfully for the standard complete workflow;
  review per-input outcomes and the selected export.
- Confirm channel identity, original XY dimensions and available calibration
  against acquisition records before reporting µm².
- Assess masks against projections. Quantification includes positive masked
  pixels with an intensity floor of 1 for integer pixels and 1e-4 for float32;
  mask-selected zero pixels do not contribute to measured area. The retained
  particle area range is 0–1e9 pixels and circularity range is 0–1.
- Timepoints after 0 are not analyzed. Separate mosaic tiles can overlap;
  their areas must not be summed as a stitched tissue area without accounting
  for that overlap.
- Neither projection nor export resamples XY or normalizes intensities.
  Acquisition settings and Z sampling remain relevant to comparisons.
- Old exports that lost calibration cannot recover it from pixel arrays
  alone. Re-export the original LIF data. Legacy or partial exports require
  explicit CLI options and do not meet the standard complete-run criteria.
- The automated full-Fiji checks use synthetic, calibrated images. Real ND2
  data and Windows/WSL require separate validation. Assess segmentation and
  acquisition calibration on the actual experimental images.

## Troubleshooting

| Problem | Action |
|---|---|
| Conda is not found | Reopen the terminal after installation. If initialization was skipped, use `~/miniforge3/bin/conda init zsh` on macOS or `~/miniforge3/bin/conda init bash` for Bash on Linux/WSL, then reopen; adapt the path/shell if needed. |
| Conda SSL certificate error | Use the OS trust store if the institutional certificate is already trusted, or the CA bundle supplied by IT; see the README certificate troubleshooting. Resolve this before continuing installation. |
| Environment missing or Python 3.14 rejected | Environment creation failed or `base` is still active. Create MCA's Python 3.10 environment successfully, then install using `conda run -n mca_tools python -m pip install .`. |
| MCA command is not found | Activate `mca_tools`; install with `python -m pip install .` in the project root; check the interpreter path. |
| Invalid JSON or missing folder | Save valid JSON and replace example paths. Use paths visible inside the active operating system, including `/mnt/d/...` in WSL. |
| No input images | Place LIFs directly in the listed folder. Hidden `._*` files are intentionally ignored. |
| No verified export/channel | Review export status, channel number and file integrity; re-export original LIF if necessary. |
| Closed-file error inside readlif | Update to MCA 0.2.3 and reinstall. The reader now handles verified zero tails and reports other structural problems with byte positions. If the new run fails, retain its log and check the original LIF in Leica LAS X or Fiji Bio-Formats without overwriting it. |
| PyImageJ error mentioning `major_version` | Update MCA 0.2.0 to 0.2.1 or later, activate `mca_tools`, reinstall with `python -m pip install .` and restart the command. Verify versions with `python -m pip show mca-tools pyimagej scyjava jgo`. |
| Other Java/Maven initialization failure | Verify Java 11 and Maven 3.9.9 in the active environment; update the Conda environment if Maven is 3.10. Inspect `~/.mca-tools/runs/<run_id>/imagej.log`; initial component downloads require network access. |
| Missing µm² measurements | Review original spatial metadata and sidecars; re-export if appropriate. Do not invent a pixel scale. |
| Partial or failed processing | Inspect `run.log` and per-input records for corrupt files, memory problems, unwritable storage or the exact processing error. |

Run statuses include `SUCCESS`, `PARTIAL`, `FAILED`, `NO_INPUT` and
`CANCELLED`. Exit codes are 0 for complete success, 1 for incomplete/failed
processing, 2 for invalid arguments/configuration and 130 for cancellation.
Worker records remain in `~/.mca-tools/runs/`. Temporary data may remain in
`~/.mca-tools/tmp/` after failure or uncertain process shutdown; this does not
mean that analysis completed successfully.

## References and software resources

- [MCA-tools repository and current README](https://github.com/alexdolskii/MCA-tools)
- [Earlier MCA 0.2.1 integration baseline](https://github.com/alexdolskii/MCA-tools/tree/823531cdfd49e663d637bb6f66e1560f4f2b9654)
- [Miniforge installation documentation](https://github.com/conda-forge/miniforge)
- [Visual Studio Code Python environments](https://code.visualstudio.com/docs/python/environments)
- [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Visual Studio Code with WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode)
- [Fiji desktop application](https://imagej.net/software/fiji/)
