/*
 * QuPath -> internal ImageJ/Fiji -> Colour Deconvolution2
 * Complete Herovici annotation export and analysis workflow.
 *
 * Version 1
 *
 * Analysis logic intentionally preserved from the original two-step workflow:
 *   1. Export each QuPath annotation bounding box at downsample 1.0.
 *   2. Save the unmasked RGB image.
 *   3. Set all pixels outside the annotation ROI to pure white.
 *   4. Save the masked RGB image.
 *   5. Run Colour Deconvolution2 with vectors=RGB.
 *   6. Save raw Colour_1 (Red), Colour_2 (Green), and Colour_3 (Blue).
 *   7. Threshold Red and Blue, Convert to Mask, save masks, and Measure Area
 *      using ImageJ's Area + Limit to threshold measurement settings.
 *   8. Save Summary_Mask_Analysis.csv and Colour_Deconvolution.png as logs.
 *
 * The standard ImageJ Results table is temporary. It is deliberately cleared,
 * closed without a save prompt, and not exported as Results.csv because it only
 * contains the final single-channel measurement.
 *
 * Processing scopes:
 *   - Current open image
 *   - Entire QuPath project
 *
 * Current-image output:
 *   selected_output_folder/
 *       01_annotation_exports/
 *       02_colour_deconvolution/
 *       03_run_logs/
 *
 * Entire-project output:
 *   selected_output_folder/
 *       image_1_name/
 *           01_annotation_exports/
 *           02_colour_deconvolution/
 *           03_run_logs/
 *       image_2_name/
 *           ...
 *
 * Run from QuPath: Automate -> Show script editor -> Open -> Run.
 */

import static qupath.lib.gui.scripting.QPEx.*

import qupath.imagej.gui.IJExtension
import qupath.imagej.tools.IJTools
import qupath.lib.common.GeneralTools
// QuPath may already expose a symbol named Dialogs in its script context.
// Use the current JavaFX dialog API through an alias to prevent Groovy's
// "The name Dialogs is already declared" compilation error. The former
// qupath.lib.gui.dialogs.Dialogs API is deprecated and scheduled for removal.
import qupath.fx.dialogs.Dialogs as QuPathDialogs
import qupath.lib.regions.RegionRequest
import qupath.lib.roi.interfaces.ROI

import groovy.transform.CompileStatic

import ij.IJ
import ij.ImagePlus
import ij.WindowManager
import ij.gui.GenericDialog
import ij.io.DirectoryChooser
import ij.measure.ResultsTable
import ij.plugin.filter.Analyzer
import ij.process.ColorProcessor
import ij.process.ImageProcessor
import ij.text.TextWindow

import java.io.File


// =============================================================================
// Entry point
// =============================================================================

String processingScope = promptForProcessingScope()
if (processingScope == null) {
    print 'Analysis cancelled by user.'
    return
}

Map settings = promptForThresholdSettings(processingScope)
if (settings == null) {
    print 'Analysis cancelled by user.'
    return
}

def currentImageData = getCurrentImageData()
def project = getProject()

if (!validateProcessingContext(settings, currentImageData, project)) {
    return
}

File outputRoot = chooseOutputRoot()
if (outputRoot == null) {
    print 'Analysis cancelled: no output folder selected.'
    return
}

def currentProjectEntry = settings.processEntireProject && currentImageData != null
        ? getProjectEntry()
        : null
runHeroviciWorkflow(
        settings,
        currentImageData,
        currentProjectEntry,
        project,
        outputRoot
)


// =============================================================================
// User input and validation
// =============================================================================

String promptForProcessingScope() {
    List<String> scopeOptions = [
            'Current open image',
            'Entire QuPath project'
    ]

    // Use a QuPath-native dialog for the processing scope. This dialog is
    // displayed before ImageJ is initialized, so the choice cannot be hidden
    // behind or skipped by ImageJ's own window lifecycle.
    return QuPathDialogs.showChoiceDialog(
            'Herovici analysis - processing scope',
            'Select which images should be analyzed:',
            scopeOptions,
            scopeOptions[0]
    ) as String
}


Map promptForThresholdSettings(String processingScope) {
    String entireProjectOption = 'Entire QuPath project'

    def dialog = new GenericDialog('Herovici analysis - thresholds')
    dialog.addMessage(
            "Selected scope: ${processingScope}\n" +
            'Thresholds are applied to the 8-bit Colour Deconvolution2 output channels.'
    )
    dialog.addNumericField('Red minimum threshold', 0, 0)
    dialog.addNumericField('Red maximum threshold', 100, 0)
    dialog.addNumericField('Blue minimum threshold', 0, 0)
    dialog.addNumericField('Blue maximum threshold', 103, 0)
    dialog.showDialog()

    if (dialog.wasCanceled()) {
        return null
    }

    int redMin = (int) dialog.getNextNumber()
    int redMax = (int) dialog.getNextNumber()
    int blueMin = (int) dialog.getNextNumber()
    int blueMax = (int) dialog.getNextNumber()

    if (!validThresholdPair(redMin, redMax) ||
            !validThresholdPair(blueMin, blueMax)) {
        IJ.showMessage(
                'Invalid thresholds',
                'Each threshold must be between 0 and 255, and minimum must not exceed maximum.'
        )
        return null
    }

    return [
            processingScope   : processingScope,
            processEntireProject: processingScope == entireProjectOption,
            redMin            : redMin,
            redMax            : redMax,
            blueMin           : blueMin,
            blueMax           : blueMax
    ]
}


boolean validateProcessingContext(
        Map settings,
        def currentImageData,
        def project
) {
    if (!settings.processEntireProject && currentImageData == null) {
        IJ.showMessage(
                'No image open',
                'Open an image in QuPath before using Current open image mode.'
        )
        return false
    }

    if (settings.processEntireProject && project == null) {
        IJ.showMessage(
                'No project open',
                'Open a QuPath project before using Entire QuPath project mode.'
        )
        return false
    }

    if (settings.processEntireProject && project.getImageList().isEmpty()) {
        IJ.showMessage(
                'Empty project',
                'The current QuPath project contains no images.'
        )
        return false
    }

    return true
}


File chooseOutputRoot() {
    def chooser = new DirectoryChooser(
            'Select the output folder for the complete analysis'
    )
    String outputRootPath = chooser.getDirectory()
    if (outputRootPath == null) {
        return null
    }

    def outputRoot = new File(outputRootPath)
    ensureDirectory(outputRoot)
    return outputRoot
}


// =============================================================================
// Workflow orchestration
// =============================================================================

void runHeroviciWorkflow(
        Map settings,
        def currentImageData,
        def currentProjectEntry,
        def project,
        File outputRoot
) {
    def stats = [processed: 0, skipped: 0, failures: []]
    def imageJInstance = null

    try {
        imageJInstance = initializeEmbeddedImageJ()
        prepareImageJWorkspace()
        printRunConfiguration(settings, outputRoot)

        if (settings.processEntireProject) {
            processProject(
                    project,
                    currentImageData,
                    currentProjectEntry,
                    outputRoot,
                    settings,
                    stats
            )
        } else {
            processCurrentImage(
                    currentImageData,
                    outputRoot,
                    settings,
                    stats
            )
        }
    } finally {
        // All measurements are disposable intermediates. Clear them first so
        // ImageJ can never ask whether the final measurement should be saved.
        closeImageJCompletely(imageJInstance)
    }

    printRunSummary(stats, outputRoot)
}


def initializeEmbeddedImageJ() {
    // Also loads commands from the Fiji/ImageJ directory configured in QuPath.
    def imageJInstance = IJExtension.getImageJInstance()
    if (imageJInstance == null) {
        throw new IllegalStateException(
                'QuPath could not initialize its internal ImageJ instance.'
        )
    }
    return imageJInstance
}


void prepareImageJWorkspace() {
    closeAllImageJWindows()

    // Match the original ImageJ macro measurement configuration exactly.
    IJ.run('Set Measurements...', 'area limit redirect=None decimal=3')
}


void printRunConfiguration(Map settings, File outputRoot) {
    print "Processing scope: ${settings.processingScope}"
    print "Output root: ${outputRoot.getAbsolutePath()}"
    print "Thresholds: Red ${settings.redMin}-${settings.redMax}; " +
            "Blue ${settings.blueMin}-${settings.blueMax}"
}


void processCurrentImage(
        def imageData,
        File outputRoot,
        Map settings,
        Map stats
) {
    String imageName = imageData.getServer().getMetadata().getName()

    try {
        Map result = processOneImage(
                imageData,
                imageName,
                outputRoot,
                settings
        )
        recordImageResult(stats, result)
    } catch (Exception e) {
        recordImageFailure(stats, imageName, e)
    }
}


void processProject(
        def project,
        def currentImageData,
        def currentProjectEntry,
        File outputRoot,
        Map settings,
        Map stats
) {
    def entries = project.getImageList()
    def usedImageFolderNames = [:].withDefault { 0 }

    entries.eachWithIndex { entry, imageIndex ->
        String entryName = entry.getImageName() ?: "Image_${imageIndex + 1}"
        String folderName = createUniqueFileName(
                GeneralTools.getNameWithoutExtension(entryName),
                usedImageFolderNames
        )
        File imageOutputDir = new File(outputRoot, folderName)

        def entryImageData = null
        boolean usesCurrentlyOpenImage = false

        print "Project image ${imageIndex + 1}/${entries.size()}: ${entryName}"

        try {
            // Use the live hierarchy for the currently open project image so
            // unsaved annotation edits made immediately before running are included.
            if (currentImageData != null &&
                    currentProjectEntry != null &&
                    entry == currentProjectEntry) {
                entryImageData = currentImageData
                usesCurrentlyOpenImage = true
            } else {
                entryImageData = entry.readImageData()
            }

            Map result = processOneImage(
                    entryImageData,
                    entryName,
                    imageOutputDir,
                    settings
            )
            recordImageResult(stats, result)

        } catch (Exception e) {
            recordImageFailure(stats, entryName, e)

        } finally {
            // No per-measurement Results file is retained. All output logs and
            // image files have already been written at this point.
            closeAllImageJWindows()

            if (entryImageData != null && !usesCurrentlyOpenImage) {
                closeImageServer(entryImageData, entryName)
            }
        }
    }
}


void recordImageResult(Map stats, Map result) {
    if (result.status == 'processed') {
        stats.processed = (stats.processed as int) + 1
    } else {
        stats.skipped = (stats.skipped as int) + 1
    }
}


void recordImageFailure(Map stats, String imageName, Exception error) {
    String message = error.getMessage() ?: error.getClass().getSimpleName()
    stats.failures << "${imageName}: ${message}"
    print "ERROR while processing '${imageName}': ${message}"
}


void closeImageServer(def imageData, String imageName) {
    try {
        imageData.getServer().close()
    } catch (Exception e) {
        print "Warning: could not close the server for '${imageName}': ${e.getMessage()}"
    }
}


void printRunSummary(Map stats, File outputRoot) {
    print 'Herovici export and analysis finished.'
    print "Processed images: ${stats.processed}"
    print "Skipped images without annotations: ${stats.skipped}"

    if (!stats.failures.isEmpty()) {
        print "Failed images: ${stats.failures.size()}"
        stats.failures.each { print "  - ${it}" }
    }

    print 'All temporary ImageJ measurements and windows were discarded.'
    print "Output root: ${outputRoot.getAbsolutePath()}"
}


// =============================================================================
// Process one QuPath image
// =============================================================================

Map processOneImage(
        def imageData,
        String displayName,
        File imageOutputDir,
        Map settings
) {
    if (imageData == null) {
        throw new IllegalArgumentException(
                "No QuPath image data were available for '${displayName}'."
        )
    }

    def server = imageData.getServer()
    String rawImageName = GeneralTools.getNameWithoutExtension(
            server.getMetadata().getName()
    )
    String imageName = sanitizeFileComponent(rawImageName)
    def annotations = imageData.getHierarchy().getAnnotationObjects()

    if (annotations.isEmpty()) {
        print "  Skipped '${displayName}': no annotations were found."
        return [status: 'skipped', annotations: 0]
    }

    Map outputLayout = createImageOutputLayout(imageOutputDir)
    def summaryRows = []
    def usedAnnotationNames = [:].withDefault { 0 }
    boolean colourDeconvolutionLogSaved = false

    resetMeasurementModel()

    print "  Found annotations: ${annotations.size()}"
    print "  Image output: ${imageOutputDir.getAbsolutePath()}"

    annotations.eachWithIndex { annotation, annotationIndex ->
        Map annotationResult = processOneAnnotation(
                server,
                annotation,
                annotationIndex,
                annotations.size(),
                imageName,
                usedAnnotationNames,
                outputLayout,
                settings
        )

        if (annotationResult.processed) {
            summaryRows << annotationResult.summaryRow
            colourDeconvolutionLogSaved =
                    colourDeconvolutionLogSaved ||
                    annotationResult.colourDeconvolutionLogSaved
        }
    }

    if (summaryRows.isEmpty()) {
        print "  Skipped '${displayName}': no valid annotation ROIs were processed."
        discardTemporaryMeasurementsAndCloseTables()
        return [status: 'skipped', annotations: annotations.size()]
    }

    File summaryFile = saveSummaryCsv(
            summaryRows,
            outputLayout.runLogsDir as File,
            settings
    )

    // The last Measure command leaves one row in ImageJ's standard Results
    // table. It is not a complete log, so discard it instead of saving it.
    discardTemporaryMeasurementsAndCloseTables()

    if (!colourDeconvolutionLogSaved) {
        print '  Warning: the Colour Deconvolution matrix window was not found; ' +
                'its PNG log was not saved.'
    }

    print "  Summary log: ${summaryFile.getAbsolutePath()}"
    return [status: 'processed', annotations: summaryRows.size()]
}


Map createImageOutputLayout(File imageOutputDir) {
    def layout = [
            annotationExportDir: new File(imageOutputDir, '01_annotation_exports'),
            deconvolutionDir   : new File(imageOutputDir, '02_colour_deconvolution'),
            runLogsDir         : new File(imageOutputDir, '03_run_logs')
    ]

    layout.values().each { ensureDirectory(it as File) }
    return layout
}


File saveSummaryCsv(
        List summaryRows,
        File runLogsDir,
        Map settings
) {
    def summary = new ResultsTable()
    summary.setPrecision(3)

    summaryRows.each { row ->
        summary.incrementCounter()
        summary.addValue('Image Name', row.imageName as String)
        summary.addValue('Red Area', row.redArea as double)
        summary.addValue('Red MinThr', settings.redMin as int)
        summary.addValue('Red MaxThr', settings.redMax as int)
        summary.addValue('Blue Area', row.blueArea as double)
        summary.addValue('Blue MinThr', settings.blueMin as int)
        summary.addValue('Blue MaxThr', settings.blueMax as int)
    }

    File summaryFile = new File(runLogsDir, 'Summary_Mask_Analysis.csv')
    summary.save(summaryFile.getAbsolutePath())
    return summaryFile
}


// =============================================================================
// Process one annotation without changing the analysis sequence
// =============================================================================

Map processOneAnnotation(
        def server,
        def annotation,
        int annotationIndex,
        int annotationCount,
        String imageName,
        Map usedAnnotationNames,
        Map outputLayout,
        Map settings
) {
    ROI roi = annotation.getROI()
    if (roi == null) {
        print "  Skipping annotation ${annotationIndex + 1}: it has no ROI."
        return [processed: false]
    }

    String rawAnnotationName = annotation.getName()
    if (rawAnnotationName == null || rawAnnotationName.trim().isEmpty()) {
        rawAnnotationName = "Annotation_${annotationIndex + 1}"
    }

    String annotationName = createUniqueFileName(
            rawAnnotationName,
            usedAnnotationNames
    )
    String baseName = "${imageName}_${annotationName}"
    String maskedBaseName = "${baseName}_masked"

    print "  Processing annotation ${annotationIndex + 1}/${annotationCount}: " +
            annotationName

    ImagePlus inputImage = null
    List<ImagePlus> colourImages = []
    ImagePlus colourDeconvolutionLogImage = null

    try {
        // Exact bounding-box extraction at full resolution (downsample = 1.0).
        def request = RegionRequest.createInstance(server.getPath(), 1.0, roi)
        inputImage = IJTools.convertToImagePlus(server, request).getImage()
        inputImage.setTitle(maskedBaseName)

        double originX = request.getX()
        double originY = request.getY()

        saveOriginalAnnotation(
                inputImage,
                outputLayout.annotationExportDir as File,
                baseName
        )

        maskOutsideBackground(
                inputImage.getProcessor(),
                roi,
                originX,
                originY
        )
        inputImage.updateAndDraw()

        saveMaskedAnnotation(
                inputImage,
                outputLayout.annotationExportDir as File,
                maskedBaseName
        )

        Map deconvolutionResult = runColourDeconvolution2(inputImage)
        colourImages = deconvolutionResult.channels as List<ImagePlus>
        colourDeconvolutionLogImage =
                deconvolutionResult.logImage as ImagePlus

        boolean logSaved = saveColourDeconvolutionLog(
                colourDeconvolutionLogImage,
                outputLayout.runLogsDir as File
        )

        Map areas = saveAndMeasureColourChannels(
                colourImages,
                outputLayout.deconvolutionDir as File,
                maskedBaseName,
                settings
        )

        print "    Saved and measured: Red Area=${areas.red}; " +
                "Blue Area=${areas.blue}"

        return [
                processed                  : true,
                colourDeconvolutionLogSaved: logSaved,
                summaryRow                : [
                        imageName: maskedBaseName,
                        redArea  : areas.red,
                        blueArea : areas.blue
                ]
        ]

    } finally {
        colourImages.each { closeWithoutPrompt(it) }
        closeWithoutPrompt(colourDeconvolutionLogImage)
        closeWithoutPrompt(inputImage)
    }
}


void saveOriginalAnnotation(
        ImagePlus inputImage,
        File annotationExportDir,
        String baseName
) {
    File outputFile = new File(
            annotationExportDir,
            "${baseName}_original.tif"
    )
    IJ.saveAs(inputImage, 'Tiff', outputFile.getAbsolutePath())
}


void saveMaskedAnnotation(
        ImagePlus inputImage,
        File annotationExportDir,
        String maskedBaseName
) {
    File outputFile = new File(
            annotationExportDir,
            "${maskedBaseName}.tif"
    )
    IJ.saveAs(inputImage, 'Tiff', outputFile.getAbsolutePath())
}


boolean saveColourDeconvolutionLog(
        ImagePlus logImage,
        File runLogsDir
) {
    if (logImage == null) {
        return false
    }

    // RGB vectors are identical for all annotations. Overwriting preserves the
    // same last-call behavior as the previous combined script.
    IJ.saveAs(
            logImage,
            'PNG',
            new File(
                    runLogsDir,
                    'Colour_Deconvolution.png'
            ).getAbsolutePath()
    )
    return true
}


Map saveAndMeasureColourChannels(
        List<ImagePlus> colourImages,
        File deconvolutionDir,
        String maskedBaseName,
        Map settings
) {
    ImagePlus redImage = colourImages[0]
    ImagePlus greenImage = colourImages[1]
    ImagePlus blueImage = colourImages[2]

    IJ.saveAs(
            redImage,
            'Tiff',
            new File(
                    deconvolutionDir,
                    "${maskedBaseName}_Red.tif"
            ).getAbsolutePath()
    )
    double redArea = thresholdConvertSaveAndMeasure(
            redImage,
            settings.redMin as int,
            settings.redMax as int,
            new File(
                    deconvolutionDir,
                    "${maskedBaseName}_Red_mask.tif"
            )
    )

    IJ.saveAs(
            greenImage,
            'Tiff',
            new File(
                    deconvolutionDir,
                    "${maskedBaseName}_Green.tif"
            ).getAbsolutePath()
    )

    IJ.saveAs(
            blueImage,
            'Tiff',
            new File(
                    deconvolutionDir,
                    "${maskedBaseName}_Blue.tif"
            ).getAbsolutePath()
    )
    double blueArea = thresholdConvertSaveAndMeasure(
            blueImage,
            settings.blueMin as int,
            settings.blueMax as int,
            new File(
                    deconvolutionDir,
                    "${maskedBaseName}_Blue_mask.tif"
            )
    )

    return [red: redArea, blue: blueArea]
}


// =============================================================================
// ImageJ analysis helpers
// =============================================================================

@CompileStatic
void maskOutsideBackground(
        ImageProcessor processor,
        ROI roi,
        double originX,
        double originY
) {
    int width = processor.getWidth()
    int height = processor.getHeight()

    if (processor instanceof ColorProcessor) {
        int[] pixels = (int[]) processor.getPixels()
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                if (!roi.contains(originX + x + 0.5d, originY + y + 0.5d)) {
                    pixels[y * width + x] = 16777215 // Pure white: 0xFFFFFF
                }
            }
        }
    } else {
        // Preserved fallback from the original script.
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                if (!roi.contains(originX + x + 0.5d, originY + y + 0.5d)) {
                    processor.setf(x, y, 255.0f)
                }
            }
        }
    }
}


Map runColourDeconvolution2(ImagePlus inputImage) {
    // Showing the temporary input is equivalent to selecting its window and
    // running the command in the original ImageJ macro.
    inputImage.show()
    IJ.selectWindow(inputImage.getTitle())

    Set imageIdsBefore = [] as Set
    int[] beforeList = WindowManager.getIDList()
    if (beforeList != null) {
        beforeList.each { imageIdsBefore.add(it) }
    }

    IJ.run('Colour Deconvolution2', 'vectors=RGB')

    String title = inputImage.getTitle()
    ImagePlus colour1 = WindowManager.getImage("${title}-(Colour_1)")
    ImagePlus colour2 = WindowManager.getImage("${title}-(Colour_2)")
    ImagePlus colour3 = WindowManager.getImage("${title}-(Colour_3)")

    List<ImagePlus> newImages = []
    int[] afterList = WindowManager.getIDList()
    if (afterList != null) {
        afterList.each { imageId ->
            if (!imageIdsBefore.contains(imageId)) {
                ImagePlus newImage = WindowManager.getImage(imageId as int)
                if (newImage != null) {
                    newImages << newImage
                }
            }
        }
    }

    ImagePlus logImage = newImages.find { image ->
        image.getTitle() == 'Colour Deconvolution' ||
                image.getTitle().startsWith('Colour Deconvolution-')
    }

    if (logImage == null) {
        logImage = WindowManager.getImage('Colour Deconvolution')
    }

    if (colour1 == null || colour2 == null || colour3 == null) {
        newImages.each { closeWithoutPrompt(it) }
        throw new IllegalStateException(
                "Colour Deconvolution2 did not create the expected Colour_1, " +
                "Colour_2 and Colour_3 images for '${title}'. " +
                'Confirm that QuPath is using the Fiji/ImageJ directory where ' +
                'Colour Deconvolution2 is installed.'
        )
    }

    return [
            channels: [colour1, colour2, colour3],
            logImage: logImage
    ]
}


double thresholdConvertSaveAndMeasure(
        ImagePlus channelImage,
        int minimumThreshold,
        int maximumThreshold,
        File maskFile
) {
    // Exact Java API equivalents of the original macro commands:
    // setThreshold(); Convert to Mask; saveAs(); Measure.
    IJ.setThreshold(channelImage, minimumThreshold, maximumThreshold)
    IJ.run(channelImage, 'Convert to Mask', '')
    IJ.saveAs(channelImage, 'Tiff', maskFile.getAbsolutePath())

    ResultsTable results = ResultsTable.getResultsTable()
    results.reset()
    IJ.run(channelImage, 'Measure', '')

    int lastRow = results.getCounter() - 1
    if (lastRow < 0) {
        throw new IllegalStateException(
                "ImageJ did not return an Area measurement for " +
                channelImage.getTitle()
        )
    }

    return results.getValue('Area', lastRow)
}


// =============================================================================
// ImageJ cleanup: discard temporary measurements without prompts
// =============================================================================

void resetMeasurementModel() {
    try {
        Analyzer.setUnsavedMeasurements(false)
        Analyzer.resetCounter()
    } catch (Exception ignored) {
    }

    // Defensive fallback for ImageJ builds where Analyzer cleanup is not
    // available or a third-party table has replaced the system table.
    try {
        ResultsTable.getResultsTable().reset()
    } catch (Exception ignored) {
    }
}


void discardTemporaryMeasurementsAndCloseTables() {
    resetMeasurementModel()

    def nonImageWindows = WindowManager.getAllNonImageWindows()
    if (nonImageWindows == null) {
        return
    }

    nonImageWindows.each { window ->
        if (!(window instanceof TextWindow)) {
            return
        }

        TextWindow textWindow = window as TextWindow

        // Clear both the backing ResultsTable and displayed rows. For the
        // standard Results window, close(false) explicitly suppresses
        // Analyzer.resetCounter() and its "Save 1 measurements?" dialog.
        try {
            textWindow.getResultsTable()?.reset()
        } catch (Exception ignored) {
        }
        try {
            textWindow.getTextPanel()?.clear()
        } catch (Exception ignored) {
        }

        try {
            textWindow.close(false)
        } catch (Exception ignored) {
            // Defensive fallback for older ImageJ builds.
            try {
                if (textWindow.getTitle() == 'Results') {
                    IJ.setTextPanel(null)
                }
                textWindow.setVisible(false)
                textWindow.dispose()
                WindowManager.removeWindow(textWindow)
            } catch (Exception ignoredAgain) {
            }
        }
    }

    resetMeasurementModel()
}


void closeWithoutPrompt(ImagePlus image) {
    if (image != null) {
        image.changes = false
        image.close()
    }
}


void closeAllImageJWindows() {
    // Close Results and any other ImageJ table first. WindowManager's generic
    // close method otherwise calls TextWindow.close() with prompting enabled.
    discardTemporaryMeasurementsAndCloseTables()

    int[] imageIds = WindowManager.getIDList()
    if (imageIds != null) {
        imageIds.each { imageId ->
            closeWithoutPrompt(WindowManager.getImage(imageId as int))
        }
    }

    // Close any remaining ImageJ utility windows. Text windows are routed
    // through the non-prompting path in case one appeared during cleanup.
    def remainingWindows = WindowManager.getAllNonImageWindows()
    if (remainingWindows != null) {
        remainingWindows.each { window ->
            if (window == null) {
                return
            }

            if (window instanceof TextWindow) {
                TextWindow textWindow = window as TextWindow
                try {
                    textWindow.getResultsTable()?.reset()
                    textWindow.getTextPanel()?.clear()
                    textWindow.close(false)
                } catch (Exception ignored) {
                    try {
                        textWindow.setVisible(false)
                        textWindow.dispose()
                        WindowManager.removeWindow(textWindow)
                    } catch (Exception ignoredAgain) {
                    }
                }
            } else {
                try {
                    window.setVisible(false)
                    window.dispose()
                    WindowManager.removeWindow(window)
                } catch (Exception ignored) {
                }
            }
        }
    }

    resetMeasurementModel()
}


void closeImageJCompletely(def imageJInstance) {
    closeAllImageJWindows()

    // Dispose only ImageJ's AWT toolbar/frame. Never call System.exit and never
    // close QuPath itself.
    def imageJApplication = imageJInstance != null
            ? imageJInstance
            : IJ.getInstance()

    if (imageJApplication != null) {
        try {
            imageJApplication.setVisible(false)
        } catch (Exception ignored) {
        }
        try {
            imageJApplication.dispose()
        } catch (Exception ignored) {
        }
    }
}


// =============================================================================
// File-system and naming helpers
// =============================================================================

void ensureDirectory(File directory) {
    if (!directory.exists() && !directory.mkdirs()) {
        throw new IOException(
                "Could not create output directory: ${directory.getAbsolutePath()}"
        )
    }

    if (!directory.isDirectory()) {
        throw new IOException(
                "Output path is not a directory: ${directory.getAbsolutePath()}"
        )
    }
}


boolean validThresholdPair(int minimumThreshold, int maximumThreshold) {
    return minimumThreshold >= 0 &&
            maximumThreshold <= 255 &&
            minimumThreshold <= maximumThreshold
}


String createUniqueFileName(String rawName, Map usedNames) {
    String baseName = sanitizeFileComponent(rawName)
    usedNames[baseName] = (usedNames[baseName] as int) + 1
    int occurrence = usedNames[baseName] as int

    return occurrence == 1
            ? baseName
            : "${baseName}_${occurrence}"
}


String sanitizeFileComponent(String value) {
    String sanitized = value == null
            ? ''
            : value.replaceAll('[^a-zA-Z0-9.-]', '_')
    return sanitized.isEmpty() ? 'Unnamed' : sanitized
}
