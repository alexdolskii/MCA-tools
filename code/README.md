# MCA Python package

The installed commands are `shg1_lif_to_tif` and `shg2_intden_assay`.
The two same-named files in this directory are compatibility launchers.
Implementations live in `mca_tools`; QuPath is a separate workflow.

| Module | Responsibility |
|---|---|
| `cli.py` | Lightweight arguments, validated prompts and command dispatch |
| `config.py` | Input JSON and folder validation |
| `files.py` | Shared inventories, safe names, hashes and atomic JSON |
| `lif_export.py` | Native LIF pixels, TIFF calibration and metadata export |
| `calibration.py` | Explicit spatial units and dual-unit result columns |
| `metadata.py` | TIFF/OME/ND2 physical metadata without guessed scales |
| `discovery.py` | Latest verified complete or explicitly allowed partial export |
| `shg_analysis.py` | Per-image SHG workflow and result tables |
| `shg_imagej.py` | Projection, masks and TIFF saving |
| `run.py` | Unique result directories, logs and image outcomes |
| `imagej.py` | Shared Fiji endpoint and command-boundary shutdown |
| `runtime.py` | Worker temporary directories, process observation and cleanup |

## Rules to preserve

- Keep the original XY grid and pixel values during export. No resizing,
  interpolation, normalization or intensity scaling is permitted in export
  or projection. SUM uses float32; MAX retains the input storage bit depth.
- Keep scientific changes separate from structural edits. Preserve Moments,
  manual thresholding, particle limits and the positive-intensity measurement
  floor unless a scientific change has been explicitly agreed and tested.
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
masks/projections, and two-folder partial completion.

For an offline native test only, `MCA_TEST_IMAGEJ_CLASSPATH` may specify
ImageJ, ij1-patcher and Javassist JARs separated by the OS path separator.
This tests the real headless ImageJ1 operations; it is not a substitute for
validating the full pinned Fiji/Bio-Formats environment. CI uses full Fiji.
