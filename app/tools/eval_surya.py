import sys
import json
import argparse
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

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

class SuryaBatchWorker:
    def __init__(self):
        self.worker_script = Path("/tmp/surya_eval_worker_batch.py")
        self.create_worker_script()

    def create_worker_script(self):
        code = """import sys
import json
from pathlib import Path
from PIL import Image

try:
    from surya.common.surya.schema import TaskNames
    from surya.detection import DetectionPredictor
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    
    import contextlib
    import io
    import sys
    with contextlib.redirect_stdout(sys.stderr):
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
except ImportError as e:
    import json
    import sys
    print(json.dumps({"error": str(e)}))
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        return
    img_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    
    results = {}
    try:
        import contextlib
        
        for img_file in img_dir.glob("*.png"):
            image = Image.open(str(img_file)).convert("RGB")
            
            with contextlib.redirect_stdout(sys.stderr):
                predictions_by_image = rec_predictor([image], [TaskNames.ocr_with_boxes], det_predictor=det_predictor)

            texts = []
            if predictions_by_image[0].text_lines:
                for line in predictions_by_image[0].text_lines:
                    texts.append(line.text)
                
            results[img_file.name] = {
                "text": " ".join(texts),
                "confidence": 0.99
            }
            
        with open(out_path, "w") as f:
            json.dump(results, f)
            
    except Exception as e:
        import traceback
        with open(out_path, "w") as f:
            json.dump({"error": traceback.format_exc()}, f)
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
        self.worker_script.write_text(code)

class SequentialSuryaEngine(OcrEngine):
    def __init__(self, cache, expected_order):
        super().__init__()
        self.cache = cache
        self.expected_order = expected_order
        self.idx = 0
            
    def extract(self, img):
        if self.idx >= len(self.expected_order):
            return OcrResult(text="", confidence=0.0, tokens=[], engine_name="surya")
        
        expected_filename = self.expected_order[self.idx]
        png_filename = f"{expected_filename}.png"
        res = self.cache.get(png_filename, {})
        
        self.idx += 1
        return OcrResult(text=res.get("text", ""), confidence=res.get("confidence", 0.0), tokens=[], engine_name="surya")

def preload_surya_batch(labeled_files) -> dict:
    """Pre-runs Surya on the entire dataset via a single background mamba process."""
    from app.pipeline.echo_ocr_pipeline import preprocess_roi
    from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
    from app.io.dicom_loader import load_dicom_series
    
    worker = SuryaBatchWorker()
    results_cache = {}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        import cv2
        
        print("Extracting and saving dataset frames to tmpdir...")
        detector = TopLeftBlueGrayBoxDetector()
        for lf in labeled_files:
            try:
                series = load_dicom_series(lf.path)
                # Find first frame with a text box
                img_np = None
                for frame_idx in range(series.frame_count):
                    frame = series.get_frame(frame_idx)
                    detection = detector.detect(frame)
                    if detection.present and detection.bbox is not None:
                        x, y, bw, bh = detection.bbox
                        roi = frame[y : y + bh, x : x + bw]
                        img_np = preprocess_roi(roi)
                        if img_np is not None and img_np.size > 0:
                            break
                            
                if img_np is None:
                    continue
                    
                out_name = f"{lf.path.name}.png"
                if len(img_np.shape) == 2:
                    pil_image = Image.fromarray(img_np).convert("RGB")
                else:
                    rgb_arr = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_arr)
                pil_image.save(dir_path / out_name, format="PNG")
            except Exception as e:
                import traceback
                print(f"Extraction error for {lf.path.name}: {e}")
                traceback.print_exc()
                
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_out:
            json_path = json_out.name
            
        print("Running full Surya OCR background process (this avoids PyTorch memory leaks)...")
        try:
            subprocess.run(
                ["mamba", "run", "-n", "surya", "python", str(worker.worker_script), str(dir_path), json_path],
                capture_output=True,
                check=True
            )
            
            with open(json_path, "r") as f:
                data = json.load(f)
                
            if "error" in data:
                print(f"Surya Batch Error: {data['error']}")
            else:
                results_cache = data
                
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8') if e.stderr else 'Unknown error'
            print(f"Surya wrapper crashed: {err_msg}")
        finally:
            Path(json_path).unlink(missing_ok=True)
            
    return results_cache

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels.md"))
    parser.add_argument("--parser", default="local_llm")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    labeled_files = parse_labels(labels_path)
    print(f"Parsed {len(labeled_files)} labeled files\\n")

    # 1. Preload everything
    cache = preload_surya_batch(labeled_files)
    
    # 2. Extract strictly in the order `run_evaluation` intends to call them
    expected_order = [lf.path.name for lf in labeled_files]
    seq_engine = SequentialSuryaEngine(cache, expected_order)

    print("\\n--- Evaluating with: surya ---")
    
    # We need a dummy class with parser attribute for run_evaluation
    class DummyArgs:
        def __init__(self, p):
            self.parser = p
            
    scores = run_evaluation(labeled_files, seq_engine, verbose=True, args=DummyArgs(args.parser))
    _print_summary("surya", scores)

if __name__ == "__main__":
    main()
