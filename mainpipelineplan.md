# Human-in-the-Loop OCR Validation Pipeline

## Goal
Integrate the Surya + Local LLM OCR pipeline into the DICOM viewer to enable a "Validation Mode" where users can review AI extractions, correct them if necessary, and save the verified results as new high-quality ground-truth labels for future evaluations.

## User Review Required
> [!IMPORTANT]
> The validation process will append to a file named `validation_labels.md` in the current working directory. Ensure this location is suitable for your data collection strategy.

## Architecture & Components

### 1. Automated Service Management
To ensure a seamless user experience, the application will manage its own background services:
- **Service Process Manager**: A background thread responsible for:
  - Starting `ollama serve` if it's not already running.
  - Initializing the persistent `SuryaOcrEngine` worker.
  - Verifying both services are responding (e.g., via HTTP ping for Ollama and `READY` signal for Surya).

### 2. Startup & Splash Screen
#### [NEW] `app/ui/dialogs/startup_dialog.py`
A lightweight splash window that appears immediately upon launching the app.
- **Visuals**: Shows a progress bar and status messages (e.g., "Starting Ollama...", "Loading Surya Models...", "Ready!").
- **Logic**: Blocks the `MainWindow` from appearing until all services are healthy. If a service fails to start, it provides a troubleshooting guide.

### 3. Data Models & State
- **ValidationSession**: A new state object within `ViewerState` (or a singleton) to track the current session's metrics:
  - `total_validated_frames`: Count of frames processed by the user.
  - `total_ai_correct`: Count of measurements where the user clicked "Correct".
  - `total_ai_incorrect`: Count of measurements the user had to modify or delete.
  - `session_labels`: In-memory list of validated `(path, measurements)` pairs.

### 4. UI Components

#### [NEW] `app/ui/dialogs/validation_dialog.py`
A modal or non-modal dialog for reviewing AI results while keeping the image visible.
- **Visual Integration**: 
  - The dialog should be docked to the side OR be a semi-transparent floating panel, ensuring the **Main DICOM Viewer remains visible** behind it so the user can see the text pixels they are validating.
- **Center Section**: `ValidationFeedbackWidget` for each measurement:
  - Displays: `AI Prediction: [Name] [Value] [Unit]`
  - **Option 1: [Approve]** (Green Button) -> Takes the AI label as-is.
  - **Option 2: [Wrong / Correct]** -> Opens an input field: "Correct Result: [__________]".
- **Bottom Section**: "Submit All to Dataset" button.

#### [MODIFY] `app/ui/main_window.py`
- Add a new "OCR Validation" action to the toolbar (hotkey `V`).
- This action triggers a specialized `AiRunWorker` using the **Surya + Local LLM** configuration.
- On completion, instead of just showing overlays, it launches the `ValidationDialog`.

#### [NEW] `app/ui/components/validation_stats.py`
A small overlay or widget in the Bottom-Right of the viewer showing:
- **Session Accuracy**: `(Correct / Total) %`
- **Measurement Count**: `X verified measurements today.`

### 3. Pipeline Configuration
- Force `EchoOcrPipeline` to use:
  - `ocr_engine`: `SuryaOcrEngine` (Persistent Worker)
  - `parser`: `LocalLlmMeasurementParser` (via Ollama)
  - `preprocess`: `scale_factor=3`, `scale_algo="lanczos"`, `contrast_mode="none"` (The A/B Test winning config).

## Implementation Steps

### Phase 1: Infrastructure & Startup
1. **Service Process Manager**: Implement the background logic to check for and spawn `ollama serve` and the `SuryaOcrEngine` worker.
2. **Startup Dialog**: Create the `StartupDialog` splash screen that hooks into the Service Manager to show real-time initialization progress.

### Phase 2: Core Feedback Logic
1. **Validation UI**: Create the `ValidationFeedbackWidget` (floating or docked) that allows for Approve/Correct interaction.
2. **LabelWriter**: Implement the logic to append verified records to `validation_labels.md`.

### Phase 3: UI Integration
1. **Validation Toolbar**: Add the "Validation" trigger to the `MainWindow`.
2. **Context Preservation**: Ensure the `ValidationDialog` is non-modal or docked so the DICOM viewer remains interactive/visible.

### Phase 4: Benchmarking
1. **Accuracy Tracker**: Implement the real-time session stats (Accuracy %, Count).
2. **Session Summary**: Add the final summary popup with the "Highest score seen" tracking.

## Verification Plan

### Manual Verification
1. Load a new DICOM file.
2. Click "Run OCR Validation".
3. Observe the dialog with AI results.
4. Modify one measurement and approve another.
5. Click "Save to Dataset".
6. Verify that `validation_labels.md` contains the new labels in the correct format.
7. Verify the accuracy stats update correctly.
