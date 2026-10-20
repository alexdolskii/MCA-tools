# MCA-tools

Multimodal Collagen Analysis Toolkit

MCA supports SHG microscopy and histological image analysis. The Python
workflow exports Leica LIF images as calibrated TIFF Z-stacks and measures
SHG area and intensity in its own `mca_tools` environment. The independent
[QuPath workflow](qupath_code/README.md) automates annotation export and
colour-based area measurements in Herovici-stained brightfield images.

**Version 0.2.3:** LIF export validates block boundaries and supports verified
zero-filled tails in newer LIF files. It avoids readlif's misleading
`I/O operation on closed file` / `seek of closed file` error and reports
unsupported or incomplete blocks with their byte positions. Source files
are read-only; accepted padding is recorded in the log and TIFF sidecars.

MCA uses the same **Python 3.10, NumPy 1.26.4 and Fiji
bridge** baseline as FIA `tech_dev` and UMA `UMA-tools-V2`, in its own
`mca_tools` environment. Shared bridge versions are PyImageJ 1.5.0,
scyjava 1.10.0 and jgo 1.0.4, with Fiji 2.14.0 and Java 11. MCA additionally
requires readlif 0.6.5 and tifffile 2025.5.10 for LIF/TIFF processing:
readlif 0.6.6 requires NumPy 2, and newer tifffile releases dropped Python
3.10 support. Fiji settings remain
centralized in [fiji_config.py](code/mca_tools/fiji_config.py).
The configuration also registers Bio-Formats' official OME repository for
fresh Maven downloads. MCA additionally pins **Maven 3.9.9**, because Maven
3.10's dependency-filtering and warning changes break this older jgo bridge.
See [validation](#development-and-validation) for the actual test coverage.

Start here:

- [QuPath: installation, libraries, operation and results](qupath_code/README.md)
- [QuPath: separate text for protocols.io](docs/protocols_io_qupath_herovici.md)
- [Install on a computer with no analysis software](#1-install-on-a-computer-with-no-analysis-software)
- [Connect Visual Studio Code to MCA](#2-set-up-visual-studio-code)
- [Prepare the data and run the two stages](#3-prepare-input-folders)
- [Find and inspect the results](#6-find-and-inspect-the-results)
- [Interpret pixels, micrometers and intensity](#table-definitions)
- [Separate text for protocols.io](docs/protocols_io.md)

Sections 1-7 below describe the Python SHG workflow. For the Groovy script,
follow the QuPath instructions linked above; no Conda environment is needed.

## 1. Install on a computer with no analysis software

### What you will install

| Component | Purpose |
|---|---|
| Miniforge / Conda | Creates an isolated `mca_tools` software environment |
| Git | Downloads MCA-tools and retrieves later updates |
| Visual Studio Code (VS Code) with Microsoft's Python extension | Edits the input JSON and provides a terminal |
| MCA-tools | Installs the two analysis commands and their Python dependencies |
| Fiji desktop application, optional | Opens TIFF stacks, projections and masks for visual quality control |

This guide uses **Visual Studio Code**, Microsoft's code editor. The larger
Visual Studio IDE is not required. Conda installs Python 3.10, OpenJDK 11,
Maven 3.9.9 and shared numerical libraries from
[environment.yaml](environment.yaml); the subsequent pip command installs
MCA and the remaining dependencies declared in [pyproject.toml](pyproject.toml).
You do not need to install Python or Java separately, or install FIA-tools.

Use a computer with enough memory for the largest native image stack and
several working image copies. Storage requirements depend on the dataset:
exported TIFFs and repeated analysis runs require additional space beside the
original LIF files. Start with a small representative dataset. Network access
is needed for software installation and the first Fiji/Maven download.

The commands below use macOS Terminal, a Linux terminal, or Ubuntu under WSL.
Run each command one line at a time and wait for it to finish. Text such as
`(mca_tools)` is a terminal prompt, not part of a command to copy.

### Windows preparation: use Ubuntu under WSL 2

For Windows, the recommended route is WSL 2 with Ubuntu, followed by the Linux
instructions below. Native Windows and WSL have not been validated for the
complete MCA workflow; this is an installation route, not a platform validation
claim.

1. Follow Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).
   On a supported Windows 10/11 computer, open **PowerShell as Administrator**
   and run:

   ```powershell
   wsl --install
   ```

2. Restart if requested. Open **Ubuntu** from the Start menu and create its
   Linux username and password. All subsequent Conda and MCA commands run in
   Ubuntu, not PowerShell.
3. Install VS Code on Windows and the Microsoft **WSL** extension. Enable
   **Add to PATH** in the VS Code installer. Later, open the cloned project
   from Ubuntu using `code .`. See Microsoft's
   [VS Code with WSL guide](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode).

Keep the code in your Linux home directory, for example
`~/projects/MCA-tools`. A Windows folder `D:\Experiment_01\Condition_A`
normally appears in Ubuntu as `/mnt/d/Experiment_01/Condition_A`. Check that
the drive is mounted and writable before using this path.

### Install Miniforge

Download a matching installer from the official
[Miniforge releases](https://github.com/conda-forge/miniforge/releases/latest).
Follow steps [link](https://continuumio-docs.readthedocs-hosted.com/miniconda/install/#quick-command-line-install)

### Install Git, download MCA and create its environment

Install Git [link](https://git-scm.com/install/mac)

Choose folder for the project:

For advanced users familiar with command-line tools, the entire workflow can be performed directly in a terminal. Standard commands such as `cd` (navigate between directories), `ls` (list files and folders), and `mkdir` (create new directories) can be used to establish and manage the local project structure. JSON configuration files can be created and modified using a command-line text editor, and analysis scripts can be executed directly from the terminal.
However, we recommend using **Visual Studio Code (VS Code)** [link](https://code.visualstudio.com) to simplify project setup and management, particularly for users who are less familiar with command-line operations. VS Code provides a convenient graphical interface for creating and organizing local project directories, viewing and editing JSON configuration files, and identifying potential formatting errors. Its integrated terminal also allows users to execute scripts and manage the analysis workflow without switching between applications. This approach combines the flexibility of command-line execution with the convenience of a graphical development environment.

### Install MCA-tools
```bash
conda run -n base git clone --branch main --single-branch https://github.com/alexdolskii/MCA-tools.git
cd MCA-tools
conda env create -f environment.yaml
conda run -n mca_tools python -m pip install .
conda activate mca_tools
```

Accept Conda's installation confirmation when prompted. The final dot in
`python -m pip install .` means “install this project”; run it in the folder
containing `pyproject.toml`. Create the environment once. On later visits,
activate the existing environment instead of creating it again.

**Stop if environment creation fails.** `EnvironmentNameNotFound` means
there is no usable `mca_tools` environment. The explicit `conda run -n
mca_tools` installation command prevents accidentally installing MCA into
`base`. Python 3.14 in `base` is not the analysis interpreter; MCA requires
Python 3.10. For SSL errors, see [certificate troubleshooting](#conda-certificate-and-channel-errors).

Check the installation:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pip check
java -version
mvn -version
shg1_lif_to_tif --help
shg2_intden_assay --version
```

Expected: Python **3.10.x** from a path containing `envs/mca_tools`, no broken
pip requirements, Java **11**, Maven **3.9.9** and MCA command help
or version **0.2.3**. These checks do not start Fiji. The SHG backend is pinned
to `sc.fiji:fiji:2.14.0` in
[fiji_config.py](code/mca_tools/fiji_config.py) and uses the environment's
Java. A separate desktop Fiji installation is only a viewer and does not
replace this backend.

The Python, NumPy and bridge baseline matches
[FIA's environment](https://github.com/alexdolskii/FIA-tools/blob/tech_dev/environment.yaml)
and [UMA's environment](https://github.com/alexdolskii/UMA-tools/blob/UMA-tools-V2/environment_uma.yaml).
MCA also uses UMA's pandas `>=2.1,<3`, Pillow `>=10.1,<13` and psutil `>=5.9,<8`
ranges. Only libraries used by MCA are included: FIA's neural-network models
and UMA's orientation packages are not required for these two commands.
MCA retains its own environment and does not import FIA or UMA.
When upgrading an older Python 3.12 installation, create a fresh Python 3.10
environment using [the update commands](#7-later-sessions-and-software-updates).
Editing the Fiji endpoint alone does not update these dependencies.

## 2. Set up Visual Studio Code

1. Download [Visual Studio Code](https://code.visualstudio.com/download).
   On macOS, unpack it and move the application to **Applications**; on Linux,
   use the package for your distribution. Windows users install it on Windows
   as described above.
2. Open VS Code. In **Extensions**, install **Python**, published by Microsoft
   (`ms-python.python`). In a WSL window, install Python **in WSL: Ubuntu** when
   offered.
3. On macOS/Linux, choose **File → Open Folder** and select
   `~/projects/MCA-tools`. In WSL, run `code .` from that folder in Ubuntu and
   check that the VS Code window indicates a WSL connection.
4. Open the Command Palette with **Cmd+Shift+P** on macOS or **Ctrl+Shift+P**
   on Windows/Linux. Run **Python: Select Interpreter**, then choose the
   Python 3.10 interpreter named `mca_tools`. If it is missing, use the
   executable path printed during the installation check. Microsoft's
   [environment guide](https://code.visualstudio.com/docs/python/environments)
   describes interpreter discovery.
5. Choose **Terminal → New Terminal** and run:

   ```bash
   cd ~/projects/MCA-tools
   conda activate mca_tools
   python -c "import sys; print(sys.executable)"
   ```

The interpreter selection and the active terminal environment must both refer
to `mca_tools`. Run the commands in this guide in that terminal. The editor's
Run button does not supply the required input JSON or analysis choices.

## 3. Prepare input folders

Keep original LIF files in writable experiment folders outside the code
checkout. For the first trial, use a separate folder containing copies of a
few representative LIFs. Export scans only the files directly inside each
listed folder; it does not recurse into subfolders.

In VS Code, create **`my_input_paths.json`** in the MCA-tools project root,
using [input_paths.json](input_paths.json) as a template. Replace every example
path with a real folder containing original LIF files:

```json
{
  "paths_to_files": [
    "/Volumes/ExampleDrive/Experiment_01/Condition_A",
    "/Volumes/ExampleDrive/Experiment_01/Condition_B"
  ]
}
```

| System | Example folder path to put in JSON |
|---|---|
| macOS external drive | `/Volumes/ExampleDrive/Experiment_01/Condition_A` |
| Linux home directory | `/home/yourname/data/Experiment_01/Condition_A` |
| Windows D: drive from WSL | `/mnt/d/Experiment_01/Condition_A` |

Use double quotes, commas between entries and no comma after the last entry.
JSON does not allow comments. Save the file with **Cmd+S / Ctrl+S**. Each
entry must be a folder, not an individual `.lif` file or an exported
`channel_1` folder. List each condition folder separately if necessary.

Absolute paths are recommended. Relative entries resolve against the JSON
directory. Missing, hidden or duplicate folders are rejected. Dot files,
including macOS `._*`, and directories named like images are excluded from
processing and input counts. An explicit `._*.json` is rejected.

## 4. Export original LIF images

In the activated VS Code terminal, from the project root, run:

```bash
shg1_lif_to_tif -i input_paths.json
```

Wait for the command to finish and the terminal prompt to return. The log
prints the output directory and a final status for each input folder. Check
`run_status.json` in each newly created export: it should say `SUCCESS` with
zero failed or unprocessed inputs. Export counts refer to **LIF files**; one
LIF can produce many TIFFs because it contains scenes, channels and tiles.

Open a TIFF and confirm the original width, height, Z slices and channel.
Keep its adjacent `.tif.json`, the `Metadata` directory and `run_status.json`
together with the TIFFs. Renaming or editing audited export files can make
the next stage reject them. Only timepoint 0 is exported; see
[metadata](#native-pixels-and-metadata) before using time series.

## 5. Run the SHG analysis

Use MCA 0.2.3 with the dependencies installed from this checkout.
If upgrading from 0.2.0 or 0.2.1, follow [the update instructions](#7-later-sessions-and-software-updates)
before starting this stage.

Confirm which exported channel contains the SHG signal; channel 1 is only
the software default. For channel 1, start the interactive workflow:

```bash
shg2_intden_assay -i input_paths.json --channel 1
```

The same JSON still points to the **original folders**. MCA selects an export
inside each folder automatically. It asks these questions in the terminal:

| Prompt | What to enter | Effect |
|---|---|---|
| `Projection: 1/max or 2/sum` | `max` (or `1`), or `sum` (or `2`) | MAX keeps the largest intensity at each XY position; SUM adds intensities across Z |
| `Threshold: auto or manual` | `auto` or `manual` | Auto uses ImageJ Moments for each image; manual uses your bounds |
| `Lower threshold` / `Upper threshold` | Numbers, if manual | Bounds are in the projected image's intensity units; Enter defaults to 0 / `inf` |
| `Start processing? yes/no` | `yes` | Starts the analysis |

Use a documented projection/threshold policy for a comparison set. SUM
depends on the number of Z slices; its values and appropriate thresholds can
differ greatly from MAX. Check masks on representative images before accepting
a setting. Automatic thresholds can differ between images. There is no
universal manual threshold for all microscopes or acquisition settings.

Invalid answers repeat the question. Enter `q` at a prompt or press Ctrl+C
to cancel. Fiji runs **headlessly**: no analysis GUI should appear. Its first
initialization downloads Maven components and can take longer than later
runs. A completed run returns the terminal prompt and records a final status.

For repeatable, noninteractive use, specify all choices and `--yes`:

```bash
shg2_intden_assay -i my_input_paths.json --channel 1 --projection max --threshold-mode auto --yes
```

Manual syntax examples, with an unlimited or finite upper bound:

```bash
shg2_intden_assay -i my_input_paths.json --channel 1 --projection sum --threshold 2000 --yes
shg2_intden_assay -i my_input_paths.json --channel 1 --projection sum --threshold 2000 50000 --yes
```

The numbers above illustrate syntax, **not validated biological cutoffs**.
`--threshold LOWER [UPPER]` selects manual mode; omitted UPPER is infinity.
To analyze another channel, replace `--channel 1` with its number.

The original Python file launchers also work after installation:

```bash
python code/shg1_lif_to_tif.py -i my_input_paths.json
python code/shg2_intden_assay.py -i my_input_paths.json
```

## 6. Find and inspect the results

Results are written **beside the source data**, not into the code folder.
Each input folder has its own export and analysis results; there is no single
automatically combined CSV across all listed folders. `<timestamp>` is UTC
and `<id>` is a unique suffix in the examples below.

| Stage | Output directory |
|---|---|
| LIF export | `<input>/output_<folder>_<timestamp>_<id>/` |
| SHG analysis | `<selected export>/channel_<N>/Mask_Intensity_Area_Results_<timestamp>_<id>/` |

**Inside the export directory:**

| Relative path | Contents |
|---|---|
| `channel_1/<image>.tif` (and other channels) | Native-size grayscale Z-stack; one scene/tile/channel per TIFF |
| `channel_1/<image>.tif.json` | Calibration, dimensions, source metadata and checksums |
| `Metadata/<source>.xml` | Complete original LIF XML header |
| `run_status.json`, `run.log` | Completion audit and processing messages |

**Inside each SHG result directory, after a successful analysis:**

| Relative path | What it looks like / what to use it for |
|---|---|
| `<image>_processed.tif` | One grayscale 2D MAX or SUM projection, retaining the source XY size |
| `Masks/<image>_mask.tif` | An 8-bit binary image: white selected signal on black background |
| `Masked_Images/<image>_masked.tif` | Masked signal preview with two smoothing operations and contrast enhancement; use for visual inspection |
| `Tables/All_area_measurements.csv` | One row per successfully analyzed TIFF, with areas, intensities and processing metadata |
| `Metadata/<image>.json` | Source provenance, calibration and the corresponding measurements |
| `run_status.json`, `run.log` | Selected export, parameters, per-image outcomes and errors |

Install the optional [Fiji desktop viewer](https://imagej.net/software/fiji/)
to inspect scientific TIFFs. Open a TIFF with **File → Open**, use the stack
slider for exported Z-stacks and compare the projection with its mask. Check
dimensions and sampling in **Image → Properties**. A 32-bit SUM image may
look dark with its initial display range; adjust **Image → Adjust →
Brightness/Contrast** for viewing without applying a pixel transformation or
overwriting the audited file.

Open the CSV in Excel, LibreOffice Calc or another table viewer; VS Code can
also display it as text. When importing, use **comma** as the delimiter and
**dot** as the decimal separator. The file contains measurements, not a
formatted report, statistical comparisons or automatically generated plots.

### Example of numerical results

The following is an **illustrative calculation**, not experimental data. A
7 × 5-pixel image has six retained signal pixels and sampling of
0.5 × 0.25 µm/pixel. At each of those six positions, three slices have
intensities 10, 20 and 30, and the selected threshold retains the signal.

| CSV field | MAX example | SUM example |
|---|---:|---:|
| `Original_Width_px` / `Original_Height_px` | 7 / 5 | 7 / 5 |
| `Total_Area_px2` | 6 | 6 |
| `Total_Area_um2` | 0.75 | 0.75 |
| `Image_Area_px2` | 35 | 35 |
| `Image_Area_um2` | 4.375 | 4.375 |
| `Area_Fraction_percent` | 17.1429 | 17.1429 |
| `Mean_Intensity` | 30 | 60 |
| `Integrated_Density_raw` | 180 | 360 |
| `Integrated_Density_um2` | 22.5 | 45 |

For example, 6 × 0.5 × 0.25 = **0.75 µm²**. Areas are reported in pixel² and
µm²; intensity is not converted into a length. Physical measurements remain
blank when trustworthy XY calibration is missing.

### Check before using a result table

1. Confirm `SUCCESS` in both export and analysis `run_status.json` files.
   Review counts and errors; a CSV alone does not prove a complete run.
2. Check that the recorded `export_run` is the export you intended to use.
3. Compare the TIFF dimensions with the original data and confirm the SHG
   channel. A width or height of 1024 is valid if it was the original size.
4. Inspect masks across representative conditions for missed signal or
   background selection. Measurements use unsmoothed masked pixels, not the
   smoothed preview.
5. Before interpreting µm², check `Calibration_Status`, `Pixel_Width_um`
   and `Pixel_Height_um` against the acquisition metadata.
6. Keep acquisition, Z sampling, projection and threshold policies consistent
   across comparisons. These are projected 2D areas, not 3D collagen volume.

## 7. Later sessions and software updates

For each new terminal session:

```bash
cd ~/projects/MCA-tools
conda activate mca_tools
```

Use the existing successful export when trying another SHG setting; rerunning
LIF export is unnecessary unless the source data or export software changed.
Each analysis creates a new result directory. After finishing, you may run
`conda deactivate`.

To update an existing **Python 3.10** MCA environment, close active analyses,
preserve your experiment JSON and results, and run from the project root:

```bash
conda run -n base git pull --ff-only
conda env update -n mca_tools -f environment.yaml
conda run -n mca_tools python -m pip install .
conda run -n mca_tools python -m pip check
conda activate mca_tools
```

**Upgrading from MCA 0.2.0/0.2.1 with Python 3.12:** create a fresh environment
to avoid mixing packages built for different Python versions. These commands
preserve the old environment for reproducibility:

```bash
conda run -n base git pull --ff-only
conda env create -n mca_tools_py310 -f environment.yaml
conda run -n mca_tools_py310 python -m pip install .
conda run -n mca_tools_py310 python -m pip check
conda activate mca_tools_py310
python --version
shg2_intden_assay --version
```

Select `mca_tools_py310` in VS Code and substitute that name for `mca_tools`
in later commands. If the earlier environment was never created because
installation failed, use the standard `mca_tools` creation instructions.
Do not mix software versions within a comparison set
without reprocessing or assessing the effect. Record the version and exact
Git commit with `shg2_intden_assay --version` and
`conda run -n base git rev-parse HEAD`. Archive the command, input JSON and run
metadata with the experiment. A protocol-ready methods text is provided in
[docs/protocols_io.md](docs/protocols_io.md).

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

LIF export checks XML/description boundaries and declared memory-block
lengths before decoding pixels. A zero-filled tail is accepted only after
all of it has been checked and the complete blocks agree with XML-declared
memory sizes. This case is recognized by the
[Bio-Formats LIF reader](https://github.com/ome/bioformats/blob/develop/components/formats-gpl/src/loci/formats/in/LIFReader.java).
MCA gives readlif a bounded read-only view; the original file and pixel
offsets stay unchanged. TIFF sidecars include `lif_structure`, and the log
records `LIF_ZERO_PADDING` when padding was accepted. Unknown nonzero data,
truncated blocks and inconsistent metadata remain failures.

readlif reports pixels/µm; MCA stores its reciprocal, µm/pixel. X/Y are handled
independently, including non-square pixels. Missing/invalid calibration stays
missing. It is never replaced with an assumed 1 µm/pixel.

Projections, masks and masked previews retain XY dimensions and calibration.
Source references are preserved in TIFF Info and per-image JSON. Legacy TIFF,
OME-TIFF and ND2 physical sizes come from recorded metadata, not ImageJ's
default scale. ND2 uses Bio-Formats and its first image series.

The existing masked preview still receives two smoothing operations and
contrast enhancement. Measurements use the unsmoothed masked pixels.

## Selecting an export

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

LIF-reader regression tests reproduce readlif's premature-close failure
using complete images followed by zero padding. They cover short and large
padding, exact pixel/XML/calibration preservation, 32/64-bit block lengths,
unexpected nonzero tails, truncated input and inconsistent memory sizes.
These cases establish the supported behavior; an untested user file may
still contain a different unsupported layout or incomplete data.

Local validation used real headless ImageJ1 1.54p with ij1-patcher and a public
[readlif LIF fixture](https://github.com/Arcadia-Science/readlif/tree/master/tests/artifacts/xyzt-example).
MCA 0.2.0 failed full Fiji startup with PyImageJ 1.8.0
([original failing run](https://github.com/alexdolskii/MCA-tools/actions/runs/39344053874)).
Version 0.2.1 adopts the FIA/UMA bridge pins and removes the incompatible
Java-fetch configuration. It also pins Maven 3.9.9 after full integration
checks exposed Maven 3.10 incompatibilities in dependency resolution and
jgo's warning parser. The new full-Fiji test launches the installed
export and MAX/SUM analysis commands in separate processes, checks
Bio-Formats availability, native pixel area, physical area and integrated
signal, and requires successful command exit. These checks run on both
Linux and macOS in [GitHub Actions](https://github.com/alexdolskii/MCA-tools/actions/runs/39441858607).
On 20 October 2026, implementation commit `823531c` passed 26 Python tests
and all 8 full-Fiji tests on each system, including normal process exit.

Real ND2 data and Windows/WSL still require their own integration validation.
Synthetic integration fixtures establish software behavior; representative
experimental images still require mask and calibration quality control.

## Troubleshooting

### Conda certificate and channel errors

`CondaSSLError` with a self-signed certificate chain is a trust configuration
problem, separate from the Python dependencies. With Conda 23.9 or later
running under Python 3.10 or later in `base`, Conda can use the operating
system's trusted certificate store:

```bash
CONDA_SSL_VERIFY=truststore conda env create -f environment.yaml
```

This keeps certificate verification enabled and works only when the required
certificate is already trusted by the operating system. If it still fails,
ask local IT for the institution's CA bundle and use its actual PEM path:
`CONDA_SSL_VERIFY=/path/to/institution-ca-bundle.pem conda env create -f environment.yaml`.
See [Conda's SSL settings](https://docs.conda.io/projects/conda/en/stable/user-guide/configuration/settings.html#ssl-verify).

`nodefaults` in the YAML is a special exclusion marker, not a downloadable
channel. If a Conda installation requests `/nodefaults/` or unwanted
`repo.anaconda.com/pkgs/r` packages, inspect `conda config --show-sources`.
For an environment that does not yet exist, this explicit bootstrap uses
only conda-forge and then installs MCA's Python requirements from the checkout:

```bash
CONDA_SSL_VERIFY=truststore conda create -n mca_tools --override-channels -c https://conda.anaconda.org/conda-forge python=3.10 pip openjdk=11 maven=3.9.9
conda run -n mca_tools python -m pip install .
conda activate mca_tools
python -m pip check
```

Use the IT-provided CA path instead of `truststore` if required. Run the pip
command only after Conda succeeds. Changing channels does not itself repair
certificate trust.

| Symptom | What to check or do |
|---|---|
| `conda: command not found` | Reopen Terminal and VS Code after Miniforge installation. If shell initialization was skipped and the default location was used, run `~/miniforge3/bin/conda init zsh` on macOS, or `~/miniforge3/bin/conda init bash` for Bash on Linux/WSL, then reopen the terminal. Adapt the path/shell if different. |
| Environment `mca_tools` already exists | Check its Python version. Activate an existing Python 3.10 environment; use the fresh-environment migration above for Python 3.12. Do not repeat creation for every run. |
| `EnvironmentNameNotFound` or package requires another Python | Environment creation failed, or the wrong interpreter is active. Resolve the Conda error first, then create the Python 3.10 environment and install with `conda run -n mca_tools python -m pip install .`. Do not install MCA into `base`. |
| `shg1_lif_to_tif` or `shg2_intden_assay` not found | Run `conda activate mca_tools`, then `python -m pip install .` from the project root. Verify `sys.executable`. |
| Python imports fail or VS Code uses another interpreter | Select `mca_tools` in VS Code and explicitly activate it in the terminal; run `python -m pip check`. |
| Input JSON / folder error | Save valid JSON; replace example paths with existing folders. In WSL use Linux paths such as `/mnt/d/...`, not `D:\...`. |
| `NO_INPUT` | Put original `.lif` files directly in the listed folder. Export is not recursive. Files beginning with a dot are intentionally excluded. |
| No verified `channel_N` export | Check stage 1 status, the channel number and file integrity. Re-export from original LIF if necessary. See the explicit legacy/partial options above. |
| `I/O operation on closed file` or `seek of closed file` inside readlif | Upgrade to MCA 0.2.3 and reinstall the package. readlif closes its handle while reporting an unexpected block marker; the message alone does not establish file corruption. MCA now accepts verified zero padding and reports other structural problems with byte positions. If it still fails, retain the new log and check the original LIF in Leica LAS X or Fiji Bio-Formats; do not trim or overwrite it. |
| `UnboundLocalError` mentioning `major_version` at Fiji startup | Update from MCA 0.2.0, activate `mca_tools` and reinstall with `python -m pip install .`. Version 0.2.1 pins PyImageJ 1.5.0, scyjava 1.10.0 and jgo 1.0.4. Check `python -m pip show mca-tools pyimagej scyjava jgo` and restart the command in a fresh process. |
| Other Java / Maven errors, including missing `JWlz` or a malformed JAR path | Check Java 11 and Maven 3.9.9 in the active environment; apply the Conda environment update above if Maven is 3.10. Then inspect `imagej.log` for the exact error. The first backend download needs network access to Maven repositories; institutional proxy/firewall settings may require local IT support. |
| `MISSING_XY_CALIBRATION` or blank µm² fields | Check source metadata and re-export original LIF with the current exporter. Do not replace missing scale with an assumed value; pixel measurements remain available. |
| `PARTIAL`, `FAILED` or interrupted run | Read `run.log` and per-input records in `run_status.json`. Check damaged inputs, available memory and writable disk space. Fix the cause before accepting the table. |
| Projection looks black / mask looks unexpected | Inspect the raw projection in Fiji, its display range, selected channel and actual threshold bounds. Use the smoothed image only as a preview. |

For a reproducible error report, include the command, MCA version, Git commit,
OS, `run_status.json` and the relevant log excerpt. Review local paths and
sample identifiers before posting them publicly.

## QuPath

The independent [Herovici Groovy script](qupath_code/qupath_herovici_analysis.groovy)
runs inside **QuPath's Script Editor**. It processes the current image or
the images in a QuPath project, exports annotation bounding boxes at
downsample 1.0, whites out pixels outside each ROI, and calls
**Colour Deconvolution2** with `vectors=RGB`. It saves three component images,
red/blue masks and `Summary_Mask_Analysis.csv` with one row per processed
annotation. Default thresholds are Red 0-100 and Blue 0-103 (8-bit values).

### Download and load the QuPath script

1. Open the [Groovy file on GitHub](https://github.com/alexdolskii/MCA-tools/blob/main/qupath_code/qupath_herovici_analysis.groovy)
   and click **Download raw file** above the code. Save it as
   `qupath_herovici_analysis.groovy`, keeping that exact file extension.
2. In QuPath, choose **Automate > Show script editor**. In the editor, choose
   **File > Open...** and select the downloaded file; confirm **Groovy** as
   the script language.
3. After completing the ImageJ/plugin setup and preparing annotations, choose
   **Run > Run** once in the editor. The processing-scope dialog should open.

See the [detailed download and loading instructions](qupath_code/README.md#download-the-script-and-open-it-in-qupath)
for the direct raw link, ZIP alternative and filename checks. The `.groovy`
file runs through the Script Editor; Colour Deconvolution2 is installed
separately as described in the [QuPath setup guide](qupath_code/README.md#install-and-prepare).

### Methodological basis

This workflow is **based on and adapted from the Herovici image-analysis
approach of [Samyukta et al. (2022), PMID 36037140](https://pubmed.ncbi.nlm.nih.gov/36037140/)**
([doi:10.31557/APJCP.2022.23.8.2829](https://doi.org/10.31557/APJCP.2022.23.8.2829)).
It helps automate the analysis through QuPath annotation export, ImageJ
colour separation, thresholding and area measurement. It is an adaptation
for automated processing, not a new stain-analysis method or an exact
reproduction of every acquisition and threshold-selection step in the paper.
The underlying plugin and algorithm are credited separately to
[Landini et al. (2021)](https://doi.org/10.1093/bioinformatics/btaa847)
and [Ruifrok and Johnston (2001)](https://pubmed.ncbi.nlm.nih.gov/11531144/).

### QuPath libraries and software

| Component | Use in this script | Installation |
|---|---|---|
| QuPath core and GUI (`QPEx`, `GeneralTools`, `RegionRequest`, `ROI`, `qupath.fx.dialogs.Dialogs`) | Project/image access, annotations, region requests and scope dialog | QuPath desktop application |
| QuPath ImageJ extension (`IJExtension`, `IJTools`) | Embedded ImageJ and calibrated region conversion | Included with the standard QuPath distribution |
| ImageJ1 (`ij.*`) | Images, thresholds, masks, area measurements, TIFF/CSV export and window cleanup | Supplied by QuPath's ImageJ integration |
| Colour Deconvolution2, by Gabriel Landini | External ImageJ command for colour separation | Install the plugin separately and make its directory available to QuPath |
| Groovy (`CompileStatic`, script language and collections) | Script execution and the ROI masking loop | Bundled with QuPath |
| Java standard library (`java.io`, collections and exceptions); desktop runtime | Files, directories and GUI/runtime support | Use QuPath's packaged runtime |
| Fiji desktop, optional | Convenient ImageJ distribution for installing the external plugin | Separate from the Python Fiji backend |

See the [QuPath README](qupath_code/README.md) for exact imported classes,
installation links, function structure, citations and a first-run procedure.
The script uses QuPath's embedded ImageJ; the Python Fiji 2.14.0 endpoint and
Conda pins above do not configure it.

The CSV's `Red Area` and `Blue Area` use the active ImageJ spatial calibration.
It does not currently export separate pixel/physical-unit columns or record
the area unit in the CSV: verify and record that unit from the saved TIFFs.
Use a new output folder for each run, and save unrelated ImageJ work before
starting because this script closes embedded ImageJ windows and tables.
The Python CI results above do not validate this interactive QuPath workflow.
