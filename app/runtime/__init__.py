from app.runtime.pipeline_presets import (
    DEFAULT_GUI_MAX_FRAMES,
    DEFAULT_GUI_OCR_ENGINE,
    DEFAULT_GUI_SEGMENTATION_MODE,
    DEFAULT_GUI_TARGET_LINE_HEIGHT_PX,
    GUI_OCR_ENGINE_NAMES,
    GuiOcrComparisonPipeline,
    build_gui_ocr_comparison_manager,
    build_gui_ocr_manager,
    build_validation_manager,
)
from app.runtime.startup_services import ServiceProcessManager, StartupServices

__all__ = [
    "DEFAULT_GUI_MAX_FRAMES",
    "DEFAULT_GUI_OCR_ENGINE",
    "DEFAULT_GUI_SEGMENTATION_MODE",
    "DEFAULT_GUI_TARGET_LINE_HEIGHT_PX",
    "GUI_OCR_ENGINE_NAMES",
    "GuiOcrComparisonPipeline",
    "ServiceProcessManager",
    "StartupServices",
    "build_gui_ocr_comparison_manager",
    "build_gui_ocr_manager",
    "build_validation_manager",
]
