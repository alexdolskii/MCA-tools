# Herovici image analysis in QuPath

[qupath_herovici_analysis.groovy](qupath_herovici_analysis.groovy) automates
the export and colour-based area analysis of annotated, Herovici-stained
brightfield histological images. Run it in **QuPath**, independently of the
Python SHG workflow. It can process the current image or an entire project.

The workflow is **based on and adapted from the Herovici image-analysis
approach of [Samyukta et al. (2022), PMID 36037140](https://pubmed.ncbi.nlm.nih.gov/36037140/)**.
MCA automates the analysis using QuPath annotation export, background
masking, colour separation, thresholding, area measurement and organized
outputs. The software implementation uses Colour Deconvolution2, described
by **Landini, Martinelli and Piccinini (2021)** and based on the algorithm
of **Ruifrok and Johnston (2001)**. These software references supplement
the primary Herovici-method reference; MCA does not introduce a new
stain-unmixing algorithm.

The article describes ImageJ scale setting, colour deconvolution and manual
threshold selection for red/blue area measurement. MCA adapts these steps
to QuPath ROIs and project iteration. It retains native crop dimensions and
uses one user-selected threshold pair per channel throughout a run. The
paper's 640 × 480 image acquisition is not a resizing requirement in MCA,
and the paper does not establish the script's numerical threshold defaults.

The script selects the plugin's **RGB preset**, rather than estimating
Herovici-specific stain vectors. Red and Blue are output-channel labels;
mapping them to collagen maturation or collagen types requires independent
validation of the staining and segmentation. The cited method papers do not
validate MCA's threshold defaults for a particular specimen.

## Software and libraries

The setup instructions follow the **QuPath 0.7.0** API and documentation.
Its source dependency catalog specifies ImageJ1 **1.54p** and Groovy **5.0.4**.
These are reference versions, not an automatic installation lock or a claim
that this complete GUI workflow was tested on every platform. Record the
actual QuPath, embedded ImageJ, plugin and Java versions used for a study.

| Library or component | Classes used by the script | Role and source |
|---|---|---|
| QuPath scripting and core | `qupath.lib.gui.scripting.QPEx.*`, `qupath.lib.common.GeneralTools`, `qupath.lib.regions.RegionRequest`, `qupath.lib.roi.interfaces.ROI` | Current image/project, names, native-resolution regions and ROI geometry; bundled with QuPath |
| QuPath JavaFX dialogs | `qupath.fx.dialogs.Dialogs`, imported as `QuPathDialogs` | Scope selection; the alias avoids a name collision in QuPath's script context |
| QuPath ImageJ extension | `qupath.imagej.gui.IJExtension`, `qupath.imagej.tools.IJTools` | Embedded ImageJ initialization and region/calibration conversion |
| ImageJ1 core | `ij.IJ`, `ij.ImagePlus`, `ij.WindowManager` | Commands, image containers and windows |
| ImageJ1 dialogs and output | `ij.gui.GenericDialog`, `ij.io.DirectoryChooser`, `ij.measure.ResultsTable`, `ij.plugin.filter.Analyzer`, `ij.text.TextWindow` | Threshold input, output folder, measurements, CSV and table cleanup |
| ImageJ1 pixel processing | `ij.process.ColorProcessor`, `ij.process.ImageProcessor` | Set pixels outside the annotation to white |
| Colour Deconvolution2 | External command `Colour Deconvolution2`; called through `IJ.run` | Gabriel Landini's plugin, installed separately; not a Groovy import |
| Apache Groovy | `groovy.transform.CompileStatic`; standard script/collection support | Script execution and compiled ROI pixel loop; supplied by QuPath |
| Java standard library | `java.io.File`, implicitly available `IOException`, collections and standard exceptions | Filesystem, data structures and error handling; use QuPath's runtime |

No Python, PyImageJ, scyjava, jgo, Maven or Conda installation is required for
this script. The Python backend configured in `code/mca_tools/fiji_config.py`
does not control QuPath's embedded ImageJ. An external Fiji installation can
provide the plugin directory, but does not replace QuPath's runtime.

## Install and prepare

1. Install [QuPath](https://qupath.github.io/) for your operating system.
   Use its standard desktop distribution with the ImageJ extension.
2. Install **Colour Deconvolution2**, using the
   [author's installation instructions](https://blog.bham.ac.uk/intellimic/g-landini-software/colour-deconvolution-2/).
   Place the plugin JAR in a local ImageJ `plugins` directory, or enable the
   Colour Deconvolution2 update site in a separate Fiji installation.
3. In QuPath 0.7, choose **Extensions > ImageJ > Set local ImageJ directory...**
   and select that ImageJ/Fiji installation. Restart QuPath after changing
   plugins. Check that its embedded ImageJ can access the exact command
   `Colour Deconvolution2`; the older `Colour Deconvolution` is different.
4. Download and open the script using the instructions below. VS Code is
   optional for editing; execution is in QuPath's Script Editor.
5. Open a brightfield RGB image or a QuPath project and create named **area
   annotations** around the tissue regions to analyze. Verify the source
   pixel calibration. Save the project and its annotations.
6. Save any unrelated work in embedded ImageJ. The script clears its Results
   tables and closes its image/utility windows without save prompts.
7. Create a **new, empty output folder** for this run. Existing filenames can
   be overwritten if a previous output folder is reused.

Use modest-sized annotations for the first run. The script reads each
bounding box at downsample **1.0**, with no resizing. A large whole-slide
annotation can exceed ImageJ's array or memory limits. See
[QuPath's ImageJ documentation](https://qupath.readthedocs.io/en/0.7/docs/advanced/imagej.html).

## Download the script and open it in QuPath

### Download the single Groovy file

1. Open the
   [script's GitHub page](https://github.com/alexdolskii/MCA-tools/blob/main/qupath_code/qupath_herovici_analysis.groovy).
2. Above the code, click **Download raw file** (the download-arrow button).
   Alternatively, open the
   [raw script](https://raw.githubusercontent.com/alexdolskii/MCA-tools/main/qupath_code/qupath_herovici_analysis.groovy)
   and use your browser's **Save As** command if it displays the code.
3. Save it as **`qupath_herovici_analysis.groovy`** in a permanent folder,
   for example `Documents/MCA-tools/qupath_code`. Keep the `.groovy`
   extension; check that the filename does not end in `.groovy.txt` or
   `.html`. The downloaded file should contain plain script text.

You can download this public file without installing Git or Conda. To
download the entire repository instead, open
[MCA-tools](https://github.com/alexdolskii/MCA-tools), choose
**Code > Download ZIP**, extract the archive, and find the file inside
`MCA-tools-main/qupath_code`. Extract the ZIP before opening the script.

### Load the file into QuPath

1. Start QuPath and open the image/project with the annotations you prepared.
2. Choose **Automate > Show script editor** in QuPath's main window.
3. In the **Script Editor**, choose **File > Open...**, browse to the saved
   `qupath_herovici_analysis.groovy` file and open it. Use the editor's File
   menu, rather than the main window's image-opening command.
4. Confirm that the code appears in an editor tab and the script language
   is **Groovy**. If a language selection is needed, select Groovy in the
   editor's language menu.
5. Choose **Run > Run** in the Script Editor once. The first expected dialog
   is **Herovici analysis - processing scope**. Continue with the settings
   described in the next section.

Opening the file in the Script Editor is how this script is added for use
in QuPath. It is not a QuPath extension JAR and does not belong in the
extensions folder. **Colour Deconvolution2** is the separate ImageJ plugin
installed in the preparation steps above.

Keep the saved `.groovy` file for later sessions and reopen it using the
same editor command. When updating, download a new copy, reopen that copy
and record the repository revision used for the analysis. See also
[QuPath's scripting guide](https://qupath.readthedocs.io/en/0.7/docs/scripting/overview.html).

## Run

1. Load the script as described above and choose **Run > Run** once in the
   Script Editor. The script handles project iteration itself; do not combine
   its project mode with the editor's separate project-wide run command.
2. Choose **Current open image** or **Entire QuPath project**.
3. Enter whole-number thresholds from 0 to 255, with minimum no greater than
   maximum. The defaults are Red **0-100** and Blue **0-103**. These thresholds
   apply to the plugin's 8-bit component images and need dataset-specific QC.
4. Select the new output folder. Watch the script console for progress,
   skipped images and failures.
5. Inspect the exported originals, masked crops, red/blue masks and CSV
   before accepting the run. Save the console text with the experiment record.

All annotations are processed, not only the selected annotation. Project
mode includes the live annotations for the currently open project image;
other entries are read from their saved project data. Images without
annotations are skipped. An error in one image is reported and subsequent
project images can continue; this is not proof that the whole project succeeded.

## Results and measurements

For current-image mode, the following directories appear directly under the
chosen output folder. Project mode creates one image-named parent folder
per project entry, containing the same layout.

| Directory | Files | Contents |
|---|---|---|
| `01_annotation_exports` | `<base>_original.tif` | Full-resolution rectangular annotation bounding box |
| `01_annotation_exports` | `<base>_masked.tif` | Same crop, with pixels outside the ROI set to white |
| `02_colour_deconvolution` | `<base>_masked_Red.tif`, `_Green.tif`, `_Blue.tif` | Component images saved before threshold conversion |
| `02_colour_deconvolution` | `<base>_masked_Red_mask.tif`, `_Blue_mask.tif` | Binary masks used for area measurements |
| `03_run_logs` | `Summary_Mask_Analysis.csv` | One row per processed annotation |
| `03_run_logs` | `Colour_Deconvolution.png` | Plugin legend/matrix image when available; replaced on each annotation within that image |

`<base>` combines the image name and annotation name after filename
sanitization. Use distinct annotation names and inspect the resulting names.
The original export includes the entire bounding box; the masked export
defines the area to exclude from colour analysis.

| CSV column | Meaning |
|---|---|
| `Image Name` | Combined image/annotation identifier, ending in `_masked` |
| `Red Area`, `Blue Area` | ImageJ `Area` after thresholding and `Convert to Mask`, with `Area` and `Limit to threshold` enabled |
| `Red MinThr`, `Red MaxThr` | Thresholds applied to the red component |
| `Blue MinThr`, `Blue MaxThr` | Thresholds applied to the blue component |

**Units:** ImageJ area uses the active spatial calibration. A correctly
micrometer-calibrated image gives µm²; an uncalibrated image gives pixel².
Check **Image > Properties...** on the saved channel/mask TIFFs and compare
with the QuPath source calibration. The CSV does not label its area unit or
provide both units as separate columns. Do not infer units from the column
name or import the Python SHG table definitions into this workflow.

The script does not calculate collagen percentages, a red/blue ratio,
integrated density or group statistics, and does not add measurements to
QuPath's annotation table. Its temporary ImageJ `Results` table contains
only the latest measurement and is discarded; use the saved summary CSV.

## Code structure and review

The file remains a self-contained Groovy script for straightforward use in
QuPath's editor. It already separates responsibilities into named functions:

| Section | Main functions |
|---|---|
| User input and validation | `promptForProcessingScope`, `promptForThresholdSettings`, `validateProcessingContext`, `chooseOutputRoot` |
| Workflow and image lifecycle | `runHeroviciWorkflow`, `processCurrentImage`, `processProject`, `recordImageResult`, `recordImageFailure` |
| Per-image outputs | `processOneImage`, `createImageOutputLayout`, `saveSummaryCsv` |
| Per-annotation analysis | `processOneAnnotation`, `saveOriginalAnnotation`, `saveMaskedAnnotation`, `saveAndMeasureColourChannels` |
| ImageJ operations | `maskOutsideBackground`, `runColourDeconvolution2`, `thresholdConvertSaveAndMeasure` |
| Cleanup | `closeWithoutPrompt`, `discardTemporaryMeasurementsAndCloseTables`, `closeAllImageJWindows`, `closeImageJCompletely` |
| Files and names | `ensureDirectory`, `validThresholdPair`, `createUniqueFileName`, `sanitizeFileComponent` |

The 20 October 2026 review confirmed that comments, identifiers, dialogs and
script-authored messages are in English. The documentation/header update
preserves the executable analysis sequence and default thresholds.
This review does not constitute an end-to-end QuPath GUI validation on
histological images; the Python CI suite does not run this Groovy workflow.

Points to check during a representative-data run:

- Match masks to stained structures and ensure the whitened exterior is not
  counted. Verify positive and negative regions; channel labels alone do not
  establish biological specificity.
- Record ImageJ binary-mask settings and inspect mask foreground/background.
  The script sets measurement options but does not reset all global ImageJ
  preferences or explicitly set the plugin's output mode.
- Confirm image calibration and report area units with the CSV. ImageJ area
  is reported to three decimal places in the summary.
- Check the console for failures and the expected number of annotation rows.
  Failure details are printed to the console, not saved to a structured
  per-run status file. An image-level failure can leave partial TIFF output
  without a complete summary for that image.
- Keep separate run folders. The current script has no automatic timestamped
  run directory, checksum manifest or collision-proof naming across all
  pre-existing files. Save source annotations, software versions and console
  output alongside the exported results.

## References

1. **Primary methodological basis:** Samyukta S, et al. **An Evaluation of the
   Prognosticative Value of Hyalinization in the Biological Behaviour of Oral
   Lesions Using Image Analysis.** *Asian Pacific Journal of Cancer Prevention*.
   2022;23(8):2829-2834.
   [doi:10.31557/APJCP.2022.23.8.2829](https://doi.org/10.31557/APJCP.2022.23.8.2829),
   [PMID:36037140](https://pubmed.ncbi.nlm.nih.gov/36037140/).
2. Landini G, Martinelli G, Piccinini F. **Colour deconvolution: stain unmixing
   in histological imaging.** *Bioinformatics*. 2021;37(10):1485-1487.
   [doi:10.1093/bioinformatics/btaa847](https://doi.org/10.1093/bioinformatics/btaa847).
3. Ruifrok AC, Johnston DA. **Quantification of histochemical staining by
   color deconvolution.** *Anal Quant Cytol Histol*. 2001;23(4):291-299.
   [PMID:11531144](https://pubmed.ncbi.nlm.nih.gov/11531144/).
4. Bankhead P, et al. **QuPath: Open source software for digital pathology
   image analysis.** *Scientific Reports*. 2017;7:16878.
   [doi:10.1038/s41598-017-17204-5](https://doi.org/10.1038/s41598-017-17204-5).
5. Schneider CA, Rasband WS, Eliceiri KW. **NIH Image to ImageJ: 25 years of
   image analysis.** *Nature Methods*. 2012;9:671-675.
   [doi:10.1038/nmeth.2089](https://doi.org/10.1038/nmeth.2089).
6. If Fiji is used to supply plugins: Schindelin J, et al. **Fiji: an
   open-source platform for biological-image analysis.** *Nature Methods*.
   2012;9:676-682. [doi:10.1038/nmeth.2019](https://doi.org/10.1038/nmeth.2019).

Software sources:
[QuPath](https://github.com/qupath/qupath),
[QuPath 0.7.0 dependency catalog](https://github.com/qupath/qupath/blob/v0.7.0/gradle/libs.versions.toml),
[Colour Deconvolution2 source and download](https://github.com/landinig/IJ-Colour_Deconvolution2),
[ImageJ1](https://imagej.net/ij/),
[Apache Groovy](https://groovy-lang.org/).
External libraries retain their own licenses and attribution requirements.

For a standalone procedure ready to adapt for protocols.io, see
[the QuPath/Herovici protocol](../docs/protocols_io_qupath_herovici.md).
