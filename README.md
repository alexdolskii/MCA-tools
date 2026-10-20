# MCA-tools

**Multimodal Collagen Analysis Toolkit** — two workflows for quantitative
collagen-associated image analysis.

| Tool | Input and purpose |
|---|---|
| **SHG area and intensity** | Leica `.lif` data or compatible single-channel TIFFs from other microscopes; measures second-harmonic generation signal area and intensity at native XY resolution. |
| **Herovici histology in QuPath** | Herovici-stained brightfield RGB images; combines manual ROI annotation with ImageJ colour deconvolution and red/blue component area measurements. |

## Quick start

### SHG analysis

Requires Conda and Git. The environment installs Python 3.10, OpenJDK 11 and
Maven; package installation adds the image-analysis dependencies. macOS and
Linux are tested; Windows setup through WSL is covered in the
[complete SHG guide](docs/shg_guide.md).

```bash
conda run -n base git clone --branch main --single-branch https://github.com/alexdolskii/MCA-tools.git
cd MCA-tools
conda env create -f environment.yaml
conda run -n mca_tools python -m pip install .
conda activate mca_tools
```

**Leica LIF:** put folders containing LIF files in [input_paths.json](input_paths.json)
under `paths_to_files`, then run:

```bash
shg1_lif_to_tif -i input_paths.json
shg2_intden_assay -i input_paths.json --input-source export --channel 1
```

Choose the exported channel containing SHG; `1` is an example, not automatic
channel identification. Follow the projection and threshold prompts.

**Independent TIFFs:** put TIFF files or folders in
[tiff_input_paths.json](tiff_input_paths.json), then run:

```bash
shg2_intden_assay -i tiff_input_paths.json --input-source tiff
```

Use single-channel grayscale images or Z-stacks. Results include projections,
masks and separate CSVs for individual and `merged` images, with areas in
pixel² and, when calibrated, µm². Inspect masks before using measurements.

### Herovici analysis in QuPath

Requires **QuPath with its ImageJ extension** and **Colour Deconvolution2**.

1. Follow the [QuPath setup guide](qupath_code/README.md#install-and-prepare)
   to install and connect the software.
2. Download [qupath_herovici_analysis.groovy](qupath_code/qupath_herovici_analysis.groovy)
   using **Download raw file**, open your brightfield image/project in QuPath,
   and annotate the tissue ROIs.
3. Open the script through **Automate → Show script editor → File → Open**,
   choose **Run → Run**, and select the scope, thresholds and a new output folder.

Outputs include ROI crops, colour components, masks and an annotation-level
CSV. The workflow adapts [Samyukta et al. (2022)](https://pubmed.ncbi.nlm.nih.gov/36037140/);
red/blue component areas require validation for the staining being analyzed.

## Documentation

- [SHG: complete installation from a new computer, inputs, analysis and results](docs/shg_guide.md)
- [QuPath: installation, plugin setup, script download, analysis and results](qupath_code/README.md)
- [Developer guide and tests](code/README.md)

**Temporary protocols.io drafts:** [SHG](docs/protocols_io.md) and
[QuPath/Herovici](docs/protocols_io_qupath_herovici.md). These separate drafts
are retained for review and will be removed after agreement and transfer to
protocols.io; the user guides above are the permanent documentation.

## Support and contributing

Maintained by [Aleksandr Dolskii](https://github.com/alexdolskii).
Use [GitHub Issues](https://github.com/alexdolskii/MCA-tools/issues) for questions
and reproducible bug reports. Include the command, software version and relevant
log excerpt. Contributions are welcome through pull requests; see the
[developer guide](code/README.md) for checks.

## Citation and license

When reporting results, identify the MCA-tools version and commit, and cite
the underlying methods/software listed in the relevant guide.

MCA-tools is distributed under the [MIT License](LICENSE). External software
retains its own licenses and attribution requirements.
