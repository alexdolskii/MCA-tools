# MCA-tools

Multimodal Collagen Analysis Toolkit

The Python workflow exports Leica LIF images as TIFF Z-stacks and measures SHG image area and intensity with ImageJ. The Herovici analysis script for QuPath is available separately in [`qupath_code`](qupath_code).

## Installation

Install [Git](https://git-scm.com/downloads) and [Miniforge](https://github.com/conda-forge/miniforge). Use a terminal in which Conda is available.

### 1. Download MCA-tools

```bash
git clone --branch main --single-branch https://github.com/alexdolskii/MCA-tools.git
cd MCA-tools
```

If you already have a checkout, update it and work from its root folder.

### 2. Create the MCA environment and install the package

Run these commands from the repository root:

```bash
conda env create -f environment.yaml
conda activate mca_tools
python -m pip install .
```

The independent environment is named `mca_tools`. [`environment.yaml`](environment.yaml) installs Python 3.12, OpenJDK 11, Maven, and pip. [`pyproject.toml`](pyproject.toml) defines the Python dependencies and creates the two terminal commands during `python -m pip install .`.

| Python dependency | Version |
|---|---|
| NumPy | 2.2.6 |
| pandas | 2.2.3 |
| PyImageJ | 1.8.0 |
| readlif | 0.6.6 |
| scyjava | 1.12.4 |
| tifffile | 2025.6.11 |

Additional dependencies, including Pillow and the Java bridge packages, are resolved automatically. `readlif 0.6.6` requires NumPy 2 or newer; this environment provides NumPy 2.2.6. The dependency versions here are specific to MCA.

Create the environment once. In each new terminal session, activate it with `conda activate mca_tools`. After updating the repository, activate the environment and run `python -m pip install .` again to install the updated package.

### 3. Check the installation

```bash
python -m pip check
shg1_lif_to_tif --help
shg2_intden_assay --help
python -c "import imagej, numpy, pandas, readlif, scyjava, tifffile; print('MCA imports OK')"
```

These checks verify Python dependencies and command availability. To check Fiji initialization before processing images:

```bash
python -c "import imagej; ij = imagej.init('sc.fiji:fiji', mode='headless'); print(ij.getVersion()); ij.context().dispose()"
```

The scripts resolve Fiji Java components through Maven. The first initialization requires internet access and can take several minutes. The Fiji components are downloaded separately from the Python environment; the scripts retain their existing `sc.fiji:fiji` initialization endpoint.

## Prepare the input paths

Edit [`input_paths.json`](input_paths.json) to list the folders containing the original LIF files:

```json
{
  "paths_to_files": [
    "/Volumes/ExampleDrive/Experiment_01/Condition_A",
    "/Volumes/ExampleDrive/Experiment_01/Condition_B"
  ]
}
```

Each entry is a folder, despite the name `paths_to_files`. Use paths that exist on the computer running the analysis. Under WSL, use WSL paths such as `/mnt/d/Experiment_01/Condition_A`. For native Windows JSON paths, use forward slashes such as `D:/Experiment_01/Condition_A` or escape backslashes.

Both stages use the same JSON file. Run from the repository root when using the relative name `input_paths.json`, or supply an absolute JSON path in quotes.

## Run the Python workflow

Activate the environment and run the stages in order, waiting for the first stage to finish:

```bash
conda activate mca_tools
shg1_lif_to_tif -i input_paths.json
shg2_intden_assay -i input_paths.json
```

| Command | Input and behavior | Output location |
|---|---|---|
| `shg1_lif_to_tif` | Reads `.lif` files directly inside each configured folder. Exports scenes, channels, mosaic tiles, and Z slices from the first time point. | `output_<input_folder_name>_<timestamp>/channel_<number>/` inside each input folder. |
| `shg2_intden_assay` | Finds `channel_1` inside the latest matching `output_...` folder under each configured folder. Prompts for MAX or SUM projection, automatic or manual thresholding, and confirmation to start. | `Mask_Intensity_Area_Results_<timestamp>/` inside the selected `channel_1` folder. |

The second stage writes projections, masks, masked images, and `Tables/All_area_measurements.csv`. Its supported input extensions are `.tif`, `.tiff`, and `.nd2`. Both stages exclude filenames beginning with a dot, including macOS `._*` files.

The existing direct script launches remain available from the repository root:

```bash
python code/shg1_lif_to_tif.py -i input_paths.json
python code/shg2_intden_assay.py -i input_paths.json
```

## Validation and run records

Check one representative LIF file before a larger batch. Verify channel identity, Z-stack dimensions, exported TIFF values, and the resulting masks and measurements. Installation checks alone do not validate image analysis results.

On Linux, this environment was created from `environment.yaml` with Micromamba and the package was installed with pip. Dependency checks, both installed commands, Python imports, and a TIFF/Pillow/NumPy round trip passed. The original analysis scripts are unchanged.

The environment targets macOS and Linux, including WSL. Native Windows and macOS execution must be verified on those platforms. Full Fiji initialization and real LIF image analysis still require validation; the test runner encountered a network wait while retrieving Maven dependencies through its proxy.

Record the repository commit and the installed packages with each experiment:

```bash
git rev-parse HEAD
conda env export -n mca_tools
python -m pip freeze
```

The programs print progress and errors to the terminal. Preserve that output with the experiment records; the existing analysis scripts do not write a dedicated persistent run log.

## QuPath script

[`qupath_code/qupath_herovici_analysis.groovy`](qupath_code/qupath_herovici_analysis.groovy) runs inside QuPath. The Conda environment and Python terminal commands apply to the SHG workflow in `code`.
