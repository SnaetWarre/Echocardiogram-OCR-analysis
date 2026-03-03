import sys
import argparse
import itertools
import csv
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.echo_ocr_eval_labels import parse_labels, run_evaluation
from app.pipeline.ocr_engines import SuryaOcrEngine
from app.pipeline.echo_ocr_pipeline import preprocess_roi as original_preprocess_roi
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.gotocr_normalizer import normalize_gotocr_text
from app.pipeline.ocr_engines import OcrResult

class NormalizedSuryaEngine:
    def __init__(self):
        self._engine = SuryaOcrEngine()
        self.name = "surya (ab_test)"
        
    def extract(self, image) -> OcrResult:
        res = self._engine.extract(image)
        norm_text = normalize_gotocr_text(res.text)
        return OcrResult(text=norm_text, confidence=res.confidence, tokens=res.tokens, engine_name=self.name)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels.md"))
    parser.add_argument("--parser", default="regex")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "ab_test_results.csv"))
    args = parser.parse_args()

    labels_path = Path(args.labels)
    labeled_files = parse_labels(labels_path)
    print(f"Parsed {len(labeled_files)} labeled files for A/B testing.\\n")

    # The engine runs its persistent subprocess
    engine = NormalizedSuryaEngine()

    grid = {
        "crop_mode": ["loose", "tight"],
        "scale_factor": [2, 3],
        "scale_algo": ["cubic", "lanczos"],
        "contrast_mode": ["none", "clahe", "adaptive_threshold"]
    }
    
    keys = list(grid.keys())
    combinations = list(itertools.product(*(grid[k] for k in keys)))
    total_runs = len(combinations)
    
    print(f"Starting A/B test with {total_runs} permutations.\\n")
    
    results = []
    
    class DummyArgs:
        def __init__(self, p):
            self.parser = p

    for i, values in enumerate(combinations, 1):
        params = dict(zip(keys, values))
        print(f"--- Run {i}/{total_runs} ---")
        print(f"Params: {params}")
        
        # Create a proxy function bound to these params
        def proxy_preprocess_roi(roi):
            return original_preprocess_roi(
                roi, 
                scale_factor=params["scale_factor"], 
                scale_algo=params["scale_algo"], 
                contrast_mode=params["contrast_mode"]
            )
            
        def proxy_detector():
            return TopLeftBlueGrayBoxDetector(crop_mode=params["crop_mode"])
            
        with patch('app.tools.echo_ocr_eval_labels.preprocess_roi', side_effect=proxy_preprocess_roi):
            with patch('app.tools.echo_ocr_eval_labels.TopLeftBlueGrayBoxDetector', side_effect=proxy_detector):
                scores = run_evaluation(labeled_files, engine, verbose=False, args=DummyArgs(args.parser))
                
        # Calculate derived metrics
        value_match_rate = scores["value_match_rate"]
        full_match_rate = scores["full_match_rate"]
        elapsed = scores["elapsed_s"]
        
        print(f"Result: Value Match: {value_match_rate:.1%}, Full Match: {full_match_rate:.1%}, Time: {elapsed:.1f}s\\n")
        
        row = {**params, "value_match": value_match_rate, "full_match": full_match_rate, "time_s": elapsed}
        results.append(row)
        
        # Write incrementally
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(keys) + ["value_match", "full_match", "time_s"])
            writer.writeheader()
            writer.writerows(results)

    print(f"\\nA/B test complete. Results saved to {args.output}")

    # Sort results to find the best
    best_value = max(results, key=lambda x: x["value_match"])
    best_full = max(results, key=lambda x: x["full_match"])
    
    print("\\n--- BEST VALUE MATCH ---")
    print(f"{best_value['value_match']:.1%} with params: { {k: best_value[k] for k in keys} }")
    
    print("\\n--- BEST FULL MATCH ---")
    print(f"{best_full['full_match']:.1%} with params: { {k: best_full[k] for k in keys} }")

if __name__ == "__main__":
    main()
