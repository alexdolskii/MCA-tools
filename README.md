# MCA-tools

**Multimodal Collagen Analysis Toolkit** — two workflows for quantitative
collagen-associated image analysis.

Developed in the [Edna (Eti) Cukierman laboratory](https://www.foxchase.org/edna-cukierman)
at **Fox Chase Cancer Center**, MCA-tools supports research into the extracellular
matrix (ECM) microenvironment, with a particular focus on collagen biology.

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

## Related projects

- [UMA-tools](https://github.com/alexdolskii/UMA-tools/tree/main) — analysis of
  fibroblast/ECM units, including fibronectin fiber alignment, matrix thickness
  and nuclear organization.
- [FIA-tools](https://github.com/alexdolskii/FIA-tools/tree/main) — quantification
  of nuclear staining, foci and marker colocalization in fibroblast/ECM units.

## Support and contributing

Maintained by [Aleksandr Dolskii](https://github.com/alexdolskii) and [Ekaterina Shitik](https://github.com/EkaterinShitik).
Use [GitHub Issues](https://github.com/alexdolskii/MCA-tools/issues) for questions
and reproducible bug reports. Include the command, software version and relevant
log excerpt. Contributions are welcome through pull requests; see the
[developer guide](code/README.md) for checks.

## Citation

Report the MCA-tools version and commit, and cite the methods and software
used in your workflow:

- **Herovici method:** [Samyukta et al., 2022](https://doi.org/10.31557/APJCP.2022.23.8.2829).
- **QuPath workflow:** [QuPath](https://doi.org/10.1038/s41598-017-17204-5),
  [ImageJ](https://doi.org/10.1038/nmeth.2089),
  [Colour Deconvolution2](https://doi.org/10.1093/bioinformatics/btaa847), and the
  [original colour-deconvolution method](https://pubmed.ncbi.nlm.nih.gov/11531144/).
- **SHG workflow:** [Fiji](https://doi.org/10.1038/nmeth.2019),
  [ImageJ](https://doi.org/10.1038/nmeth.2089), and
  [PyImageJ](https://doi.org/10.1038/s41592-022-01655-4), together with the
  applicable library and thresholding references.

See the [citation guide](docs/citations.md) for full references, NumPy/pandas,
TIFF/LIF reader credits, conditional citations and version-reporting examples.

## License

MCA-tools is distributed under the [MIT License](LICENSE). External software
retains its own licenses and attribution requirements.
