import sys
import argparse
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.echo_ocr_eval_labels import (
    parse_labels,
    OcrEngine,
    OcrResult,
    run_evaluation,
    _print_summary,
)
from app.pipeline.ocr_engines import SuryaOcrEngine
from app.pipeline.gotocr_normalizer import normalize_gotocr_text

class NormalizedSuryaEngine:
    def __init__(self):
        self._engine = SuryaOcrEngine()
        self.name = "surya (normalized)"
        
    def extract(self, image) -> OcrResult:
        res = self._engine.extract(image)
        norm_text = normalize_gotocr_text(res.text)
        return OcrResult(text=norm_text, confidence=res.confidence, tokens=res.tokens, engine_name=self.name)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels.md"))
    parser.add_argument("--parser", default="regex")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    labeled_files = parse_labels(labels_path)
    print(f"Parsed {len(labeled_files)} labeled files\n")

    # The engine now handles its own persistent subprocess!
    engine = NormalizedSuryaEngine()

    print("\n--- Evaluating with: surya ---")
    
    # We need a dummy class with parser attribute for run_evaluation
    class DummyArgs:
        def __init__(self, p):
            self.parser = p
            
    scores = run_evaluation(labeled_files, engine, verbose=True, args=DummyArgs(args.parser))
    _print_summary("surya", scores)

if __name__ == "__main__":
    main()
