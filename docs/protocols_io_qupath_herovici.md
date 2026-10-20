# Automated annotation export and Herovici colour-area analysis using QuPath and Colour Deconvolution2

**Temporary protocols.io draft.** Retain during review; remove after agreement
and transfer to protocols.io. The permanent user instructions are in the
[QuPath guide](../qupath_code/README.md).

This is a standalone draft for **protocols.io**, not a published protocol.
Copy its title, abstract, materials and numbered procedure into the
corresponding fields. It describes the independent Groovy workflow in
`qupath_code/qupath_herovici_analysis.groovy`. The
[Python SHG protocol](protocols_io.md) is a separate procedure.

## Status and scope

Documentation date: **20 October 2026**. Script analysis version: **1**.
The executable analysis was reviewed from MCA-tools commit
`2e343232cfbc76307eebf121920aad158bf8d32d`; the accompanying update adds
documentation and method attribution without changing that sequence.
Record the exact repository commit and installed software versions used
when adapting this protocol.

This draft is based on source/API review. An end-to-end QuPath GUI run on
representative histological images remains necessary before reporting a
validated experimental protocol. Passing Python SHG tests is not validation
of this separate workflow.

## Abstract

This procedure automates annotation export and colour-based area
measurement in Herovici-stained brightfield histological images. A Groovy
script running in QuPath exports each annotation bounding box at native
resolution, saves the original RGB crop, and replaces pixels outside the
annotation with white. QuPath's embedded ImageJ runs Colour Deconvolution2
with the RGB preset. Red and blue components are thresholded and converted
to binary masks, and ImageJ area measurements are saved together with the
threshold settings in an annotation-level CSV file. Component images,
masks and a plugin legend/matrix image support visual review.

This workflow is **based on and adapted from the Herovici image-analysis
approach of Samyukta et al. (2022), PMID 36037140**. It helps automate that
analysis through QuPath annotations and ImageJ operations. The underlying
Colour Deconvolution2 software is described by Landini, Martinelli and
Piccinini (2021), building on Ruifrok and Johnston (2001). Its contribution
is workflow automation and output organization. The RGB preset and threshold
defaults require validation for the actual staining and acquisition
conditions; they do not by themselves identify collagen subtypes or maturity.

## Relationship to the source method

Samyukta et al. used Herovici-stained oral-lesion images, scale calibration,
colour separation and manually adjusted thresholds to measure red/blue areas.
This protocol adapts that image-analysis approach; it does not reproduce
the study's specimen preparation, cohort, acquisition or statistical analysis.

| Aspect | Implementation in this MCA adaptation |
|---|---|
| Image input | Native-resolution QuPath annotation crops; no resizing to the paper's 640 × 480 acquisition dimensions |
| Spatial scale | Calibration transferred by QuPath/ImageJ and checked in saved TIFFs |
| Threshold selection | User-selected numerical bounds applied throughout the run; defaults 0-100/0-103 are MCA settings, not thresholds established by the article |
| Automation | Current-image or project processing, ROI exterior masking, component/mask export and CSV summaries |

The output remains red/blue mask area. Any biological interpretation and
subsequent statistics must be specified for the study being performed.

## Materials and software

| Item | Requirement |
|---|---|
| Computer | Desktop system with memory and disk space for full-resolution RGB annotation crops and several derivative images |
| Input | Brightfield RGB histological images with Herovici staining and known acquisition/calibration information |
| QuPath | Desktop application with its ImageJ extension; instructions refer to the 0.7.0 API |
| ImageJ1 | Embedded in QuPath; QuPath 0.7.0's source catalog lists 1.54p |
| Colour Deconvolution2 | Gabriel Landini's external ImageJ plugin, installed in a directory accessible to QuPath |
| Groovy and Java | Use the runtimes provided with QuPath; its 0.7.0 catalog lists Groovy 5.0.4 |
| Fiji desktop, optional | Can provide a local ImageJ installation and the plugin update site |
| MCA script | `qupath_code/qupath_herovici_analysis.groovy` from MCA-tools |
| Output and records | A new empty output folder, source annotations, software-version record and saved console output |

QuPath supplies the scripting, ROI, region, dialog and ImageJ-conversion
libraries. ImageJ1 supplies the image, threshold, measurement, file-output
and window APIs. Groovy supplies `CompileStatic` and script execution;
Java supplies standard filesystem and collection classes. The exact import
inventory is in the [QuPath README](../qupath_code/README.md#software-and-libraries).
Python, Conda, PyImageJ and the Python Fiji endpoint are not used here.

## Procedure

### 1. Install and connect the software

Install [QuPath](https://qupath.github.io/) with its ImageJ extension. Install
Colour Deconvolution2 according to the
[plugin author's instructions](https://blog.bham.ac.uk/intellimic/g-landini-software/colour-deconvolution-2/),
using its JAR in an ImageJ plugins directory or its Fiji update site.
In QuPath 0.7, choose **Extensions > ImageJ > Set local ImageJ directory...**
and select the local ImageJ/Fiji installation. Restart QuPath and verify
that embedded ImageJ has the command `Colour Deconvolution2`.

### 2. Download the script and record software information

Open the
[script's GitHub page](https://github.com/alexdolskii/MCA-tools/blob/main/qupath_code/qupath_herovici_analysis.groovy)
and click **Download raw file** (the download-arrow button above the code).
Alternatively, open the
[raw file](https://raw.githubusercontent.com/alexdolskii/MCA-tools/main/qupath_code/qupath_herovici_analysis.groovy)
and use the browser's **Save As** command. Save the plain-text file as
**`qupath_herovici_analysis.groovy`** in a permanent folder such as
`Documents/MCA-tools/qupath_code`. Check that `.txt` or `.html` has not been
added to its filename.

An alternative is **Code > Download ZIP** on the
[repository page](https://github.com/alexdolskii/MCA-tools). Extract the ZIP
and locate the script in `MCA-tools-main/qupath_code`. Git and Conda are
not required for either download route.

Record QuPath, embedded ImageJ, plugin and Java versions, operating system,
script/repository revision, sample identifiers, stain protocol/batch,
scanner settings, pixel size and intended analysis unit. The script does
not automatically save a software-version manifest or structured failure log.

### 3. Prepare annotations

Open the RGB images in QuPath, either individually or in a project. Check
their spatial calibration. Draw named area annotations around the regions
of interest, following a predefined selection rule. Avoid overlapping ROIs
if their areas will later be summed. Save annotations and project data.
Use distinct names and check sanitized filenames in the output.

Start with small representative positive and negative regions. The script
exports full-resolution bounding boxes at downsample 1.0 and does not resize
to a fixed image size. Very large regions may exceed available memory or
ImageJ's array limits.

### 4. Prepare the output and ImageJ workspace

Create a new, empty folder for this run. Reusing a folder can overwrite
files. Save unrelated ImageJ work first: this script discards ImageJ Results
tables and closes image/utility windows without save prompts.

### 5. Open the script and choose the processing scope

In QuPath's main window, choose **Automate > Show script editor**. In the
Script Editor's **File > Open...** menu, select the downloaded
`qupath_herovici_analysis.groovy` file. Confirm that the source code appears
in an editor tab and the language is **Groovy**; select Groovy in the
editor's language menu if needed. Choose **Run > Run** once in that editor.
The first expected dialog is **Herovici analysis - processing scope**.

The `.groovy` file is loaded as a script, not installed as a QuPath extension
JAR. Colour Deconvolution2 is the separate ImageJ plugin from step 1. Keep
the downloaded file and reopen it in the Script Editor for later sessions.

Select **Current open image** or **Entire QuPath project**. The script
iterates through project entries itself, so do not also invoke the editor's
project-wide batch runner.

All annotations in each image are considered. In project mode the currently
open image uses its live hierarchy, including unsaved annotation edits;
other images use saved project data. Images without annotations are skipped.

### 6. Set thresholds and start processing

Enter whole-number lower and upper thresholds between 0 and 255. The
minimum must not exceed the maximum. Defaults are **Red 0-100** and
**Blue 0-103**. These are starting settings for the plugin's 8-bit component
images, not universal thresholds established by the cited publications.
Select the output folder and monitor the script console.

Use a predefined threshold-selection procedure on representative images,
then apply the chosen settings consistently to the intended comparison set.
Record ImageJ binary-mask preferences and inspect mask polarity. The script
sets `Area` and `Limit to threshold` measurements; it does not reset every
global ImageJ preference or explicitly supply the plugin output-mode option.

### 7. Review images and execution status

For each test annotation, compare the original RGB crop, white-background
masked crop, component images and binary red/blue masks. Confirm that masks
follow the intended stained regions and exclude the exterior/background.
Save the console output and check its processed, skipped and failed counts.
An image-level failure can leave partial output without a complete summary;
do not treat those TIFF files as a completed analysis.

### 8. Verify calibration and collect the summary

Open saved component/mask TIFFs in ImageJ and inspect **Image > Properties...**.
Compare their pixel size and units with the QuPath source. ImageJ area is
in µm² when calibrated in micrometers and in pixel² when uncalibrated.
Record the verified unit alongside the CSV; the CSV itself does not label it
or supply separate pixel² and µm² columns.

Collect `03_run_logs/Summary_Mask_Analysis.csv` from each image output folder.
Keep source images, annotations, thresholds, calibration and version records
with the results. Define any later normalization, ratios or statistical
analysis separately; this script does not calculate them.

## Expected results

Current-image mode creates three directories directly in the selected
folder. Project mode creates one image-named parent directory per entry.

| Location | Expected output |
|---|---|
| `01_annotation_exports` | `<base>_original.tif` and `<base>_masked.tif` for each processed annotation |
| `02_colour_deconvolution` | `<base>_masked_Red.tif`, `_Green.tif`, `_Blue.tif`, `_Red_mask.tif` and `_Blue_mask.tif` |
| `03_run_logs` | `Summary_Mask_Analysis.csv`; `Colour_Deconvolution.png` when the plugin legend is available |

`<base>` combines sanitized image and annotation names. The legend PNG is
shared within each image output and overwritten by later annotations using
the same RGB vectors. No permanent ImageJ `Results.csv` is produced.

The summary has one row per successfully processed annotation within a
completed image, with these columns:

| Column | Interpretation |
|---|---|
| `Image Name` | Combined image/annotation identifier ending in `_masked` |
| `Red Area`, `Blue Area` | Threshold-limited ImageJ area after mask conversion; units must be verified separately |
| `Red MinThr`, `Red MaxThr` | Red-component threshold bounds |
| `Blue MinThr`, `Blue MaxThr` | Blue-component threshold bounds |

These outputs describe colour-mask area. They do not directly report
collagen concentration, percentage tissue coverage, integrated density,
collagen subtype, a red/blue ratio or a clinical classification.

## Troubleshooting

| Observation | Action |
|---|---|
| `Colour Deconvolution2` command not found | Confirm the plugin is installed and visible to QuPath's embedded ImageJ; restart after configuring the local directory |
| Expected `Colour_1`, `Colour_2`, `Colour_3` images missing | Verify RGB input, plugin version and its 8-bit transmittance output; the script expects the original channel naming |
| Import or dialog error | Check the installed QuPath API/version; retain the `QuPathDialogs` alias |
| No rows or skipped image | Check that saved/live area annotations exist for the selected scope |
| Memory/array error | Use a smaller annotation and rerun into a new output folder; the script always exports at full resolution |
| Unexpectedly large/small area | Review threshold bounds, binary mask polarity, source calibration and the saved masks |
| Incomplete results | Review failed-image messages, partial TIFFs and CSV row counts; rerun affected data after resolving the cause |

## References and attribution

1. **Primary methodological basis:** Samyukta S, et al. *Asian Pacific Journal
   of Cancer Prevention*. 2022;23(8):2829-2834.
   [Article: PMID 36037140](https://pubmed.ncbi.nlm.nih.gov/36037140/).
   https://doi.org/10.31557/APJCP.2022.23.8.2829
2. Landini G, Martinelli G, Piccinini F. Colour deconvolution: stain unmixing
   in histological imaging. *Bioinformatics*. 2021;37(10):1485-1487.
   https://doi.org/10.1093/bioinformatics/btaa847
3. Ruifrok AC, Johnston DA. Quantification of histochemical staining by color
   deconvolution. *Anal Quant Cytol Histol*. 2001;23(4):291-299.
   https://pubmed.ncbi.nlm.nih.gov/11531144/
4. Bankhead P, et al. QuPath: Open source software for digital pathology image
   analysis. *Scientific Reports*. 2017;7:16878.
   https://doi.org/10.1038/s41598-017-17204-5
5. Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ: 25 years of image
   analysis. *Nature Methods*. 2012;9:671-675.
   https://doi.org/10.1038/nmeth.2089
6. If Fiji is used: Schindelin J, et al. Fiji: an open-source platform for
   biological-image analysis. *Nature Methods*. 2012;9:676-682.
   https://doi.org/10.1038/nmeth.2019

Software and implementation:
[MCA-tools](https://github.com/alexdolskii/MCA-tools),
[Colour Deconvolution2](https://github.com/landinig/IJ-Colour_Deconvolution2),
[QuPath ImageJ integration](https://qupath.readthedocs.io/en/0.7/docs/advanced/imagej.html).
When adapting the protocol, also document the exact tissue preparation and
staining procedure actually used in the experiment.
