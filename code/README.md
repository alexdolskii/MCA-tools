# MCA Python package

The installed commands are `shg1_lif_to_tif` and `shg2_intden_assay`.
The two same-named files in this directory are compatibility launchers.
Implementations live in `mca_tools`; QuPath is a separate workflow.

| Module | Responsibility |
|---|---|
| `cli.py` | Lightweight arguments, validated prompts and command dispatch |
| `config.py` | Input JSON, folder and explicit TIFF path validation |
| `files.py` | Shared inventories, safe names, hashes and atomic JSON |
| `lif_export.py` | Native LIF pixels, TIFF calibration and metadata export |
| `lif_reader.py` | Bounded read-only LIF parsing, block checks and verified zero-tail handling |
| `calibration.py` | Explicit spatial units and dual-unit result columns |
| `metadata.py` | TIFF dimensions/type checks and TIFF/OME/ND2 physical metadata without guessed scales |
| `discovery.py` | Verified export selection or nonrecursive TIFF grouping with duplicate rejection |
| `shg_analysis.py` | Per-image SHG workflow and result tables |
| `shg_imagej.py` | Projection, masks and TIFF saving |
| `run.py` | Unique result directories, logs and image outcomes |
| `fiji_config.py` | Fiji endpoint, official OME repository and command temporary directory |
| `imagej.py` | Headless Fiji initialization and command-boundary shutdown |
| `runtime.py` | Worker temporary directories, process observation and cleanup |

## Rules to preserve

- Keep the original XY grid and pixel values during export. No resizing,
  interpolation, normalization or intensity scaling is permitted in export
  or projection. SUM uses float32; MAX retains the input storage bit depth.
- Never skip unknown LIF blocks. Accept a zero tail only after checking every
  trailing byte and agreement with XML-declared memory sizes. Preserve the
  complete original source checksum and record the bounded-reader layout.
- Keep scientific changes separate from structural edits. Use `Moments dark`
  to select bright SHG on dark background (explicitly corrected in 0.2.4).
  Preserve manual thresholding, particle limits and the positive-intensity measurement
  floor unless a scientific change has been explicitly agreed and tested.
- Ask for `export` or `tiff` before analysis settings, or require an explicit
  `--input-source` in noninteractive runs. Both routes call the same processing
  function. Reject unsupported TIFF axes/types rather than silently selecting
  the first channel/timepoint. Record unlabelled-page Z assumptions.
- Partition successful rows by case-insensitive `merged` in the filename.
  Write both `Area_measurements_individual.csv` and
  `Area_measurements_merged.csv`, including headers for an empty group;
  record checksums/counts in `summaries`. Do not duplicate rows across tables.
- Store both pixel and micrometer-derived measurements. Missing or invalid
  physical calibration stays missing. Intensity is never labelled as length.
- Use one filtered inventory for counters and processing. Exclude dot files,
  AppleDouble `._*` entries and directories named like images. Reject an
  explicitly supplied `._*.json` configuration.
- Give every run a new directory. Never reuse or overwrite an earlier run.
  Write final status only after required results are saved. A failed image
  must remain in the audit; a blank valid image is not a failed image.
- Reusable functions do not terminate Python. Share ImageJ across folders;
  close workers and the context once at the command boundary.
- Cleanup touches only the command's owned temporary directory after a
  verified process exit. Leave results, caches, failed-run evidence and
  unrelated files intact.
- Use English comments/docstrings, four spaces, `snake_case` functions,
  `UPPER_CASE` constants and Ruff with a 79-character target line length.

## Development

The runtime matches FIA `tech_dev` and UMA `UMA-tools-V2`: Python 3.10,
NumPy 1.26.4, PyImageJ 1.5.0, scyjava 1.10.0 and jgo 1.0.4.
MCA uses UMA's pandas, Pillow and psutil ranges, plus readlif 0.6.5 and
tifffile 2025.5.10 for LIF/TIFF support. The latter is the last tifffile
release supporting Python 3.10; readlif 0.6.6 requires NumPy 2.
Build requirements retain setuptools >=77
for license metadata, with UMA's <81 upper bound.
`fiji_config.py` is the only definition of `FIJI_ENDPOINT`. It registers the
official OME Maven repository declared by Bio-Formats so that fresh installs
can resolve legacy dependencies such as `woolz:JWlz:1.4.0`. It preserves
caller-supplied JVM options and configures the owned temporary directory.
Use the Conda-provided Java 11 and Maven 3.9.9. MCA retains its own Python 3.10
environment; it does not import FIA or UMA.

`environment.yaml` pins Maven 3.9.9 because Maven 3.10 introduced default
prefix filtering and warning output incompatible with jgo 1.0.4. Fresh
integration testing exposed both a missing OME `/woolz` prefix and a jgo
warning-parser failure. Keep this pin until a newer complete bridge stack
passes the full-Fiji command tests. Configuration leaves `MAVEN_OPTS` and
user configuration files unchanged.

```bash
python -m pip install -e '.[dev]'
ruff check code tests
ruff format --check code tests
python -m pytest -q -m 'not imagej'
MCA_RUN_IMAGEJ_TESTS=1 python -m pytest -q tests/test_imagej.py
```

Native tests need Java and the first Fiji dependency download. Lightweight
tests generate small LIF files and use the real readlif parser; they cover
TIFF pixel equality, calibration, failed inputs, hidden files, run selection,
JSON paths, CLI startup and owned temporary storage. Native tests use
rectangular, anisotropic, 8/16-bit and zero-signal images, MAX/SUM, saved
masks/projections, and two-folder partial completion. A full-Fiji test also
executes installed export and MAX/SUM commands in fresh processes, verifies
Bio-Formats availability, independent TIFF input, separate merged tables and
calibrated measurements, and requires normal
worker exit. CI runs these checks with Java 11 on Linux and macOS.

The pytest configuration disables its `faulthandler` plugin, as recommended
by the [JPype user guide](https://jpype.readthedocs.io/en/latest/userguide.html),
so Python does not replace the JVM's fault handlers during interpreter
shutdown. This avoids a test-process crash after otherwise successful
native tests; assertions and command exit checks remain enabled.

For an offline native test only, `MCA_TEST_IMAGEJ_CLASSPATH` may specify
ImageJ, ij1-patcher and Javassist JARs separated by the OS path separator.
This tests the real headless ImageJ1 operations; it is not a substitute for
validating the full pinned Fiji/Bio-Formats environment. CI uses full Fiji.
