# Citation and software credits

[Return to the main README](../README.md).

Cite MCA-tools as the analysis software and credit the underlying methods and
software actually used. This guide separates the Herovici methodological basis,
analysis platforms, scientific libraries and runtime dependencies. A citation
to MCA-tools does not replace citations to these projects.

## Citing MCA-tools

Use the repository URL, the version used for the analysis and its commit SHA.
For example, replace the bracketed fields in this software reference:

> Dolskii A. MCA-tools: Multimodal Collagen Analysis Toolkit. Version [version],
> commit [full SHA]. https://github.com/alexdolskii/MCA-tools. Accessed [date].

Use a commit permalink (`https://github.com/alexdolskii/MCA-tools/tree/<SHA>`)
to identify the exact source. The QuPath script is distributed separately from
the Python package: record the commit containing the Groovy script even when
the Python package is not installed.

## References by workflow

| Workflow or component used | References to include |
|---|---|
| Herovici ROI analysis | Samyukta et al. [1] for the adapted analysis approach; QuPath [2]; ImageJ [3]; Colour Deconvolution2 [4]; Ruifrok and Johnston [5] for the original unmixing method. |
| SHG area and intensity analysis | ImageJ [3], Fiji [6], PyImageJ [7] and ImageJ2 [8] for the processing/integration stack; NumPy [9], pandas [10–11] and tifffile [12] for array, table and TIFF handling. |
| Leica LIF export | readlif [13], NumPy [9], tifffile [12] and Pillow (software credit below). The exporter uses readlif; it does not use Bio-Formats to read LIF files. |
| Automatic SHG thresholding (`Moments dark`) | Tsai [14], in addition to ImageJ [3]. This method citation applies when automatic thresholding was used; report the numerical bounds for manual thresholding. |
| Bio-Formats image import | Linkert et al. [15] when Bio-Formats was used, for example through the SHG ND2 import path or a QuPath Bio-Formats image server. |
| Fiji used with the QuPath workflow | Add Fiji [6] if Fiji was used, for example to supply plugins. The Groovy script otherwise runs in QuPath's embedded ImageJ environment and does not require PyImageJ. |

The Herovici workflow adapts the image-analysis approach in [1]; it does not
reproduce that study's biological validation in a new tissue or experiment.
Report threshold-positive Red and Blue component areas and the `RGB` vector
preset. These are deconvolution components, not a simple split of the original
RGB channels or direct measurements of collagen type or biochemical maturity.
See the [QuPath guide](../qupath_code/README.md) for interpretation and limitations.

The selection above follows the official citation guidance for
[QuPath](https://qupath.readthedocs.io/en/stable/docs/intro/citing.html),
[ImageJ/Fiji](https://imagej.net/contribute/citing),
[PyImageJ](https://py.imagej.net/en/latest/Citation.html),
[NumPy](https://numpy.org/citing-numpy/),
[pandas](https://pandas.pydata.org/about/citing.html), and
[Colour Deconvolution2](https://blog.bham.ac.uk/intellimic/g-landini-software/colour-deconvolution-2/).
If reference limits apply, ImageJ's guidance prioritizes publications for the
specific plugins used. Record supporting software and versions in Methods or
supplementary material.

## Bibliography

1. **Herovici analysis approach.** Samyukta S, et al. An Evaluation of the
   Prognosticative Value of Hyalinization in the Biological Behaviour of Oral
   Lesions Using Image Analysis. *Asian Pacific Journal of Cancer Prevention*.
   2022;23(8):2829–2834.
   [doi:10.31557/APJCP.2022.23.8.2829](https://doi.org/10.31557/APJCP.2022.23.8.2829).
   [PubMed](https://pubmed.ncbi.nlm.nih.gov/36037140/).

2. **QuPath.** Bankhead P, et al. QuPath: Open source software for digital
   pathology image analysis. *Scientific Reports*. 2017;7:16878.
   [doi:10.1038/s41598-017-17204-5](https://doi.org/10.1038/s41598-017-17204-5).

3. **ImageJ.** Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ:
   25 years of image analysis. *Nature Methods*. 2012;9:671–675.
   [doi:10.1038/nmeth.2089](https://doi.org/10.1038/nmeth.2089).

4. **Colour Deconvolution2.** Landini G, Martinelli G, Piccinini F. Colour
   deconvolution: stain unmixing in histological imaging. *Bioinformatics*.
   2021;37(10):1485–1487.
   [doi:10.1093/bioinformatics/btaa847](https://doi.org/10.1093/bioinformatics/btaa847).
   [Plugin source and releases](https://github.com/landinig/IJ-Colour_Deconvolution2).
   The journal issue is dated 2021; the paper appeared online in 2020.

5. **Original colour-deconvolution method.** Ruifrok AC, Johnston DA.
   Quantification of histochemical staining by color deconvolution.
   *Analytical and Quantitative Cytology and Histology*. 2001;23(4):291–299.
   [PMID:11531144](https://pubmed.ncbi.nlm.nih.gov/11531144/).

6. **Fiji.** Schindelin J, et al. Fiji: an open-source platform for
   biological-image analysis. *Nature Methods*. 2012;9:676–682.
   [doi:10.1038/nmeth.2019](https://doi.org/10.1038/nmeth.2019).

7. **PyImageJ.** Rueden CT, et al. PyImageJ: A library for integrating ImageJ
   and Python. *Nature Methods*. 2022;19:1326–1327.
   [doi:10.1038/s41592-022-01655-4](https://doi.org/10.1038/s41592-022-01655-4).

8. **ImageJ2.** Rueden CT, et al. ImageJ2: ImageJ for the next generation of
   scientific image data. *BMC Bioinformatics*. 2017;18:529.
   [doi:10.1186/s12859-017-1934-z](https://doi.org/10.1186/s12859-017-1934-z).

9. **NumPy.** Harris CR, et al. Array programming with NumPy. *Nature*.
   2020;585:357–362.
   [doi:10.1038/s41586-020-2649-2](https://doi.org/10.1038/s41586-020-2649-2).

10. **pandas paper.** McKinney W. Data Structures for Statistical Computing
    in Python. In: *Proceedings of the 9th Python in Science Conference*.
    2010:56–61.
    [doi:10.25080/Majora-92bf1922-00a](https://doi.org/10.25080/Majora-92bf1922-00a).

11. **pandas software.** The pandas development team. *pandas-dev/pandas:
    Pandas* [software]. Zenodo.
    [Software archive](https://doi.org/10.5281/zenodo.3509134).
    Select the release actually used and export its version-specific citation;
    the archive link identifies the project across releases. The pandas
    project requests both its software citation and the paper in [10].

12. **tifffile.** Gohlke C. *tifffile* [software].
    [Software archive](https://doi.org/10.5281/zenodo.6795860).
    Cite the installed release, using its version-specific archive record
    when available. MCA-tools pins 2025.5.10 in
    [pyproject.toml](../pyproject.toml);
    [that release's documentation](https://github.com/cgohlke/tifffile/tree/v2025.5.10)
    provides the project DOI above.

13. **readlif.** Negretti N. *readlif* [software]. Version 0.6.5. 2021.
    [Release and author metadata](https://pypi.org/project/readlif/0.6.5/).
    This is the version used by MCA-tools. Cite the software release directly;
    the Bio-Formats paper is not a substitute for crediting readlif.

14. **Moments thresholding.** Tsai WH. Moment-preserving thresholding:
    A new approach. *Computer Vision, Graphics, and Image Processing*.
    1985;29(3):377–393.
    [doi:10.1016/0734-189X(85)90133-1](https://doi.org/10.1016/0734-189X%2885%2990133-1).
    [ImageJ method documentation](https://imagej.net/plugins/auto-threshold#moments).

15. **Bio-Formats, when used.** Linkert M, et al. Metadata matters: access to
    image data in the real world. *Journal of Cell Biology*.
    2010;189(5):777–782.
    [doi:10.1083/jcb.201004104](https://doi.org/10.1083/jcb.201004104).
    [OME citation guidance](https://www.openmicroscopy.org/citing-ome/).

## Supporting libraries and runtime credits

Report these as software dependencies with their installed versions and
project URLs. A separate journal article is not needed for every runtime
dependency. Use an upstream release citation when the project provides one.

| Software | Role in MCA-tools | Project or documentation |
|---|---|---|
| Pillow | Image objects and pixel decoding used by readlif during LIF export. | [Pillow](https://pillow.readthedocs.io/en/stable/about.html) |
| scyjava | Java class access and JVM configuration for SHG processing. | [scyjava](https://github.com/scijava/scyjava) |
| jgo | Resolves the Java dependencies used to launch Fiji. | [jgo](https://github.com/apposed/jgo) |
| JPype | Python–Java bridge underlying the SHG runtime. | [JPype](https://jpype.readthedocs.io/) |
| psutil | Process and resource management. | [psutil](https://psutil.readthedocs.io/) |
| QuPath ImageJ integration | Transfers QuPath image regions and ROIs to embedded ImageJ. | [QuPath source](https://github.com/qupath/qupath); cite QuPath [2] and ImageJ [3]. |
| Apache Groovy | Language used by the independent QuPath script. | [Groovy](https://groovy-lang.org/) |
| Python, OpenJDK and Apache Maven | Interpreter, Java runtime and Java dependency resolution. | [Python](https://www.python.org/), [OpenJDK](https://openjdk.org/), [Maven](https://maven.apache.org/) |

Dependency requirements are maintained in [pyproject.toml](../pyproject.toml)
and [environment.yaml](../environment.yaml). The SHG Fiji endpoint is defined
in [fiji_config.py](../code/mca_tools/fiji_config.py). QuPath manages its own
Java/Groovy/ImageJ dependencies; the SHG Conda environment does not specify
the versions loaded by QuPath.

## Record the versions used

For SHG, retain `run_status.json`, which records the MCA-tools version and
selected Python dependency versions, together with the run parameters and
outputs. From the repository root, also record:

```bash
shg2_intden_assay --version
git rev-parse HEAD
python -m pip freeze > software_versions.txt
conda env export > conda_environment.yml
```

For QuPath, record the QuPath version, the script's repository commit,
embedded ImageJ version, Colour Deconvolution2 version, `RGB` vector preset,
plugin output settings, downsample, red/blue threshold bounds and spatial
calibration. Retain the annotations and masks used to review the measurements.
If the software was modified locally, retain that modified source as well.

External projects retain their own licenses. Bibliographic citation and
software-license obligations are separate; see the upstream projects for
their license texts.
