# SHG analysis: installation and user guide

[Back to MCA-tools](../README.md)

This guide covers setup on a computer with no analysis software, input
preparation, execution and interpretation of SHG area and intensity results.
Use the Leica route for `.lif` data or the independent TIFF route for compatible
single-channel images from other microscope systems.

- [Install the software](#1-install-on-a-computer-with-no-analysis-software)
- [Set up Visual Studio Code](#2-set-up-visual-studio-code)
- [Prepare LIF or TIFF inputs](#3-prepare-input-folders)
- [Export Leica data](#4-export-original-lif-images)
- [Run SHG analysis](#5-run-the-shg-analysis)
- [Inspect results](#6-find-and-inspect-the-results)
- [Measurement definitions](#table-definitions)
- [Troubleshooting](#troubleshooting)

## 1. Install on a computer with no analysis software

### What you will install

| Component | Purpose |
|---|---|
| Miniforge / Conda | Creates an isolated `mca_tools` software environment |
| Git | Downloads MCA-tools and retrieves later updates |
| Visual Studio Code (VS Code) with Microsoft's Python extension | Edits the input JSON and provides a terminal |
| MCA-tools | Installs the two analysis commands and their Python dependencies |
| Fiji desktop application, optional | Opens TIFF stacks, projections and masks for visual quality control |

This guide uses **Visual Studio Code**, Microsoft's code editor. Conda installs Python 3.10, OpenJDK 11,
Maven 3.9.9 and shared numerical libraries from
[environment.yaml](../environment.yaml); the subsequent pip command installs
MCA and the remaining dependencies declared in [pyproject.toml](../pyproject.toml).

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
instructions below.

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

### Install Miniforge and Git

For Miniforge installation check a [link](https://www.anaconda.com/docs/getting-started/installation). Specifically Miniconda, Command-line installer 
For Git installation check a [link](https://git-scm.com/install/)

Experienced users can manage the project entirely in a terminal using `cd`,
`ls`, `mkdir` and a text editor. We recommend Visual Studio Code for organizing
project folders, editing JSON and running commands in its integrated terminal.

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
`base`. MCA requires Python 3.10 from its own environment. For SSL errors, see
[certificate troubleshooting](#conda-certificate-and-channel-errors).

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
or the installed package version. These checks do not start Fiji. The SHG
backend is pinned to `sc.fiji:fiji:2.14.0` in
[fiji_config.py](../code/mca_tools/fiji_config.py) and uses the environment's
Java. A separate desktop Fiji installation is only a viewer and does not
replace this backend.

MCA uses its own environment and does not require FIA-tools or UMA-tools.
The complete dependency declarations are in [environment.yaml](../environment.yaml)
and [pyproject.toml](../pyproject.toml).

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

Choose the Leica export route below, or skip stage 1 and use independent TIFF
inputs as described at the end of this section.

Keep original LIF files in writable experiment folders outside the code
checkout. For the first trial, use a separate folder containing copies of a
few representative LIFs. Export scans only the files directly inside each
listed folder; it does not recurse into subfolders.

In VS Code, create **`input_paths.json`** in the MCA-tools project root,
using [input_paths.json](../input_paths.json) as a template. Replace every example
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

### Independent TIFF input: skip the LIF export stage

Use [tiff_input_paths.json](../tiff_input_paths.json) as a template and replace
the example path. Entries may be individual `.tif`/`.tiff` files
or folders containing them, for example:

```json
{
  "paths_to_files": [
    "/Volumes/ExampleDrive/Condition_A/SHG_sample_1.tif",
    "/Volumes/ExampleDrive/Condition_B/SHG_TIFFs"
  ]
}
```

Folder scans are nonrecursive. Do not list the same TIFF explicitly and via
its containing folder; overlapping entries are rejected. Files in the same
parent folder share a result run, even when listed separately. Hidden files
are excluded from folder inventories and counts; explicitly listed hidden
paths are rejected. Output subfolders are not scanned on later runs.

Use original single-channel grayscale intensity images, stored as uint8,
uint16 or float32. Each TIFF must contain one image series, one resolution,
one channel and one timepoint, with axes YX or ZYX. RGB/palette images,
multichannel/time-series TIFFs and unsupported pixel types are rejected
instead of silently selecting or converting data. Unlabelled multipage
TIFFs are treated as Z-stacks and logged as `ASSUMED_Z_STACK`; confirm this
interpretation against acquisition records. ImageJ must decode the same
dimensions and pixel type as the TIFF header. TIFF compatibility is not
guaranteed for every vendor layout.

Spatial calibration is read from supported OME, ImageJ or TIFF resolution
metadata. No LIF or MCA export audit is required. If an MCA sidecar is present,
its integrity checks still apply. Missing XY calibration leaves physical
fields blank; do not infer micrometers from image dimensions alone.

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
Export creates numbered folders for all channels; it does not identify SHG
or transmitted-light channels automatically. Select SHG from acquisition records.
Keep its adjacent `.tif.json`, the `Metadata` directory and `run_status.json`
together with the TIFFs. Renaming or editing audited export files can make
the next stage reject them. Only timepoint 0 is exported.

## 5. Run the SHG analysis

Use the MCA installation created above and activate `mca_tools`.

Confirm which exported channel contains the SHG signal; channel 1 is only
the software default. For channel 1, start the interactive workflow:

```bash
shg2_intden_assay -i input_paths.json
```

First choose the input source. For `export`, the same JSON still points to the
**original LIF folders**, and MCA selects a verified export inside each folder.
The default exported channel is 1; use `--channel N` to select another folder.
For `tiff`, supply the TIFF JSON described above instead. The questions are:

| Prompt | What to enter | Effect |
|---|---|---|
| `Input source: 1/export ... or 2/tiff ...` | `export` / `1`, or `tiff` / `2` | Continue a verified LIF export, or analyze independent TIFF inputs |
| `Projection: 1/max or 2/sum` | `max` (or `1`), or `sum` (or `2`) | MAX keeps the largest intensity at each XY position; SUM adds intensities across Z |
| `Threshold: auto or manual` | `auto` or `manual` | Auto uses ImageJ `Moments dark` for bright signal on a dark background; manual uses your bounds |
| `Lower threshold` / `Upper threshold` | Numbers, if manual | Bounds are in the projected image's intensity units; Enter defaults to 0 / `inf` |
| `Start processing? yes/no` | `yes` | Starts the analysis |

Use a documented projection/threshold policy for a comparison set. SUM
depends on the number of Z slices; its values and appropriate thresholds can
differ greatly from MAX. Check masks on representative images before accepting
a setting. Automatic thresholds can differ between images. There is no
universal manual threshold for all microscopes or acquisition settings.

Invalid answers repeat the question. Enter `q` at a prompt or press Ctrl+C
to cancel. Fiji runs **headlessly**: no analysis GUI should appear. **Its first
initialization downloads Maven components and can take longer than later
runs**. A completed run returns the terminal prompt and records a final status.

For repeatable, noninteractive use, specify all choices and `--yes`:

```bash
shg2_intden_assay -i input_paths.json --input-source export --channel 1 --projection max --threshold-mode auto --yes
```

Manual syntax examples, with an unlimited or finite upper bound:

```bash
shg2_intden_assay -i input_paths.json --input-source export --channel 1 --projection sum --threshold 2000 --yes
shg2_intden_assay -i input_paths.json --input-source export --channel 1 --projection sum --threshold 2000 50000 --yes
```

The numbers above illustrate syntax, **not validated biological cutoffs**.
`--threshold LOWER [UPPER]` selects manual mode; omitted UPPER is infinity.
To analyze another channel, replace `--channel 1` with its number.

For independent TIFFs, start with prompts or supply every setting:

```bash
shg2_intden_assay -i tiff_input_paths.json
shg2_intden_assay -i tiff_input_paths.json --input-source tiff --projection max --threshold-mode auto --yes
```

Choose `tiff` at the first prompt in the first command. `--input-source` is
required in noninteractive runs. `--channel`, `--allow-partial-export` and
`--allow-legacy-export` apply only to `export`; independent TIFFs must already
contain the selected SHG channel. Both input modes use identical analysis.

The original Python file launchers also work after installation:

```bash
python code/shg1_lif_to_tif.py -i input_paths.json
python code/shg2_intden_assay.py -i input_paths.json
```

## 6. Find and inspect the results

Results are written **beside the source data**, not into the code folder.
Each input folder has its own export and analysis results; there is no single
automatically combined CSV across all listed folders. `<timestamp>` is UTC
and `<id>` is a unique suffix in the examples below.

| Stage | Output directory |
|---|---|
| LIF export | `<input>/output_<folder>_<timestamp>_<id>/` |
| SHG analysis, export mode | `<selected export>/channel_<N>/Mask_Intensity_Area_Results_<timestamp>_<id>/` |
| SHG analysis, independent TIFF mode | `<TIFF parent folder>/Mask_Intensity_Area_Results_<timestamp>_<id>/` |

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
| `Tables/Area_measurements_individual.csv` | Successfully analyzed images whose filename does not contain `merged` |
| `Tables/Area_measurements_merged.csv` | Successfully analyzed images whose filename contains `merged`, case-insensitively |
| `Metadata/<image>.json` | Source provenance, calibration and the corresponding measurements |
| `run_status.json`, `run.log` | Selected export, parameters, per-image outcomes and errors |

The two tables have identical columns. Each successful image appears in
exactly one table; an empty group has a header-only CSV. If no image succeeds,
no measurement tables are written. `run_status.json` records both table
checksums and row counts under `summaries`.
The `merged` name changes only table grouping, not projection, resizing,
thresholds or metrics. It does not establish whether an image is a stitched
mosaic or a color-channel composite; RGB composites remain invalid SHG inputs.

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

1. Confirm `SUCCESS` in the analysis record and, in export mode, the export record.
   Review counts and errors; a CSV alone does not prove a complete run.
2. Check `input_source` and the input inventory; in export mode also check `export_run`.
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

Do not mix software versions within a comparison set
without reprocessing or assessing the effect. Record the version and exact
Git commit with `shg2_intden_assay --version` and
`conda run -n base git rev-parse HEAD`. Archive the command, input JSON and run
metadata with the experiment.

## Native pixels and metadata

All images retain their original XY dimensions. Filenames containing `merged`
affect table grouping only.
Export/projection perform no resampling or intensity normalization.
LIF 8/16-bit storage is retained; source detector bit depth is recorded.
MAX preserves the pixel type; SUM is float32 even for a one-slice input.

Export includes all scenes, channels, mosaic tiles and Z slices from
**timepoint 0**. Additional timepoints are recorded and warned
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

The masked preview receives two smoothing operations and
contrast enhancement. Measurements use the unsmoothed masked pixels.

## Selecting an export

This section applies to `--input-source export`. Independent TIFF mode reads
the supplied images directly and records their source hashes and metadata.

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

The tables are `Tables/Area_measurements_individual.csv` and
`Tables/Area_measurements_merged.csv`, with the same definitions below.

| Columns | Meaning |
|---|---|
| `Input_Source`, `Image_Group` | `export` or `tiff`; `individual` or `merged` |
| `Original_Width_px`, `Original_Height_px` | Native XY dimensions |
| `Pixel_Width_um`, `Pixel_Height_um`, `Pixel_Depth_um` | Recorded sampling |
| `Particle_Count` | Connected measured regions, not a count of individual collagen fibers |
| `Total_Area_px2`, `Total_Area_um2` | Sum of particle areas, in pixels and µm² |
| `Average_Particle_Area_px2`, `Average_Particle_Area_um2` | Total area/count; zero when count is zero |
| `Image_Area_px2`, `Image_Area_um2` | Entire image area |
| `Area_Fraction_percent` | Measured area / entire image area × 100 |
| `Mean_Intensity` | Raw integrated signal / measured pixel area; blank for zero area |
| `Integrated_Density_raw` | Sum of retained raw pixel intensities |
| `Integrated_Density_um2` | Raw integrated signal × physical pixel area, in signal·µm² |
| `Calibration_Status`, `Calibration_Source` | Availability and source of physical XY sampling |
| `Threshold_Lower`, `Threshold_Upper` | Actual ImageJ thresholds, including automatic runs |
| `Threshold_Method` | `Moments dark` for automatic bright-signal detection, or `manual` |

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

Record the processing settings and analyze comparison sets consistently.

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

See [the developer guide](../code/README.md) for code structure and tests, and
[GitHub Actions](https://github.com/alexdolskii/MCA-tools/actions/workflows/python.yml)
for automated checks. Python and full-Fiji integration tests cover Linux and
macOS, both input routes, native pixels, calibration and result grouping.
Representative experimental images still require mask and calibration review.
Windows/WSL and real ND2 inputs require separate integration validation.

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
| Environment `mca_tools` already exists | Check that it contains Python 3.10 and the declared dependencies, then activate it. Do not repeat environment creation for every run. |
| `EnvironmentNameNotFound` or package requires another Python | Environment creation failed, or the wrong interpreter is active. Resolve the Conda error first, then create the Python 3.10 environment and install with `conda run -n mca_tools python -m pip install .`. Do not install MCA into `base`. |
| `shg1_lif_to_tif` or `shg2_intden_assay` not found | Run `conda activate mca_tools`, then `python -m pip install .` from the project root. Verify `sys.executable`. |
| Python imports fail or VS Code uses another interpreter | Select `mca_tools` in VS Code and explicitly activate it in the terminal; run `python -m pip check`. |
| Input JSON / folder error | Save valid JSON; replace example paths with existing folders. In WSL use Linux paths such as `/mnt/d/...`, not `D:\...`. |
| `NO_INPUT` | Put original `.lif` files directly in the listed folder. Export is not recursive. Files beginning with a dot are intentionally excluded. |
| No verified `channel_N` export | Check stage 1 status, the channel number and file integrity. Re-export from original LIF if necessary. See the explicit legacy/partial options above. |
| Independent TIFFs reported as missing exports | Select `--input-source tiff`; point JSON to TIFF files or their containing folders. |
| TIFF rejected for channels, timepoints, type or dimensions | Export one grayscale SHG channel and one timepoint as an ImageJ-compatible YX/ZYX uint8, uint16 or float32 TIFF, retaining intensities and calibration. |
| LIF cannot be read | Inspect the byte-position diagnostics in `run.log` and check the original file in Leica LAS X or Fiji Bio-Formats. Keep the original unchanged and obtain a complete export from the acquisition system if needed. |
| Other Java / Maven errors, including missing `JWlz` or a malformed JAR path | Check Java 11 and Maven 3.9.9 in the active environment; apply the Conda environment update above if Maven is 3.10. Then inspect `imagej.log` for the exact error. The first backend download needs network access to Maven repositories; institutional proxy/firewall settings may require local IT support. |
| `MISSING_XY_CALIBRATION` or blank µm² fields | Check source metadata and re-export original LIF with the current exporter. Do not replace missing scale with an assumed value; pixel measurements remain available. |
| `PARTIAL`, `FAILED` or interrupted run | Read `run.log` and per-input records in `run_status.json`. Check damaged inputs, available memory and writable disk space. Fix the cause before accepting the table. |
| Projection looks black / mask looks unexpected | Inspect the raw projection in Fiji, its display range, selected channel and actual threshold bounds. Use the smoothed image only as a preview. |

For a reproducible error report, include the command, MCA version, Git commit,
OS, `run_status.json` and the relevant log excerpt. Review local paths and
sample identifiers before posting them publicly.

## Software references

Record the MCA-tools version, repository commit and analysis settings in your
methods. Cite the software used for the image operations:

- Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ: 25 years of image
  analysis. *Nature Methods*. 2012;9:671–675.
  [doi:10.1038/nmeth.2089](https://doi.org/10.1038/nmeth.2089).
- Schindelin J, et al. Fiji: an open-source platform for biological-image
  analysis. *Nature Methods*. 2012;9:676–682.
  [doi:10.1038/nmeth.2019](https://doi.org/10.1038/nmeth.2019).

Dependency versions and software names are recorded in the run metadata;
the package requirements are listed in [pyproject.toml](../pyproject.toml).
