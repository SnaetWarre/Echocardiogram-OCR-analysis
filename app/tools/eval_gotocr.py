"""
GOT-OCR 2.0 evaluation bridge.

Mirrors the same architecture as eval_surya.py:
  1. Pre-extract all text ROIs from the DL environment (DICOM → crop → preprocess)
  2. Pass image directory to a single GOT-OCR subprocess running in the `gotocr` env
  3. Compare the returned texts against the ground-truth labels
"""
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

from app.ocr.preprocessing import preprocess_roi
from app.pipeline.ocr_engines import OcrEngine, OcrResult
from app.pipeline.gotocr_normalizer import normalize_gotocr_text
from app.repo_paths import DEFAULT_EXACT_LINES_PATH
from app.validation.datasets import parse_labels
from app.validation.evaluation import print_summary, run_evaluation


# ---------------------------------------------------------------------------
# Worker script (written to /tmp and executed in the `gotocr` mamba env)
# ---------------------------------------------------------------------------

_WORKER_SCRIPT = """\
import sys
import json
from pathlib import Path
from PIL import Image

MODEL_ID = "stepfun-ai/GOT-OCR-2.0-hf"

try:
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
except ImportError as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)

def load_model():
    import contextlib, sys as _sys
    with contextlib.redirect_stdout(_sys.stderr):
        processor = AutoProcessor.from_pretrained(MODEL_ID)
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            dtype=torch.float16,
            device_map="auto",
        )
        model.eval()
    return processor, model

def run_ocr(processor, model, image: Image.Image) -> str:
    import contextlib, sys as _sys
    with contextlib.redirect_stdout(_sys.stderr):
        inputs = processor(image, return_tensors="pt").to(model.device, torch.float16)
        generated_ids = model.generate(
            **inputs,
            do_sample=False,
            tokenizer=processor.tokenizer,
            stop_strings="<|im_end|>",
            max_new_tokens=512,
        )
        # Decode only the newly generated tokens (exclude the input prompt tokens)
        new_tokens = generated_ids[:, inputs["input_ids"].shape[1]:]
        return processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()

def main():
    if len(sys.argv) < 3:
        return
    img_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    try:
        processor, model = load_model()
        print(f"GOT-OCR model loaded on {next(model.parameters()).device}", file=sys.stderr)
    except Exception:
        import traceback
        with open(out_path, "w") as f:
            json.dump({"error": traceback.format_exc()}, f)
        sys.exit(1)

    results = {}
    images = sorted(img_dir.glob("*.png"))
    print(f"Processing {len(images)} images...", file=sys.stderr)
    for i, img_file in enumerate(images):
        try:
            image = Image.open(str(img_file)).convert("RGB")
            text = run_ocr(processor, model, image)
            results[img_file.name] = {"text": text, "confidence": 0.99}
            print(f"  [{i+1}/{len(images)}] {img_file.name}: {text[:60]!r}", file=sys.stderr)
        except Exception:
            import traceback
            tb = traceback.format_exc()
            print(f"  [{i+1}/{len(images)}] ERROR: {tb}", file=sys.stderr)
            results[img_file.name] = {"text": "", "error": tb}

    with open(out_path, "w") as f:
        json.dump(results, f)
    print(f"Done. Results written to {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
"""

_WORKER_PATH = Path("/tmp/gotocr_eval_worker.py")


class GoTocrBatchWorker:
    def __init__(self):
        _WORKER_PATH.write_text(_WORKER_SCRIPT)

    @property
    def script(self) -> Path:
        return _WORKER_PATH


# ---------------------------------------------------------------------------
# Sequential engine (replays cached predictions in the order run_evaluation calls them)
# ---------------------------------------------------------------------------

class SequentialGoTocrEngine(OcrEngine):
    def __init__(self, cache: dict, expected_order: list[str], normalize: bool = True):
        super().__init__()
        self.ordered_results = [
            cache.get(f"{name}.png", {}) for name in expected_order
        ]
        self.idx = 0
        self.normalize = normalize

    def extract(self, image) -> OcrResult:
        if self.idx >= len(self.ordered_results):
            return OcrResult(text="", confidence=0.0, tokens=[], engine_name="gotocr")
        res = self.ordered_results[self.idx]
        self.idx += 1
        raw_text = res.get("text", "")
        normalized_text = normalize_gotocr_text(raw_text) if self.normalize else raw_text
        return OcrResult(
            text=normalized_text,
            confidence=res.get("confidence", 0.0),
            tokens=[],
            engine_name="gotocr",
        )


# ---------------------------------------------------------------------------
# Preloading: extract every DICOM ROI, save to tmpdir, run worker once
# ---------------------------------------------------------------------------

def preload_gotocr_batch(labeled_files) -> dict:
    """Pre-runs GOT-OCR on the entire dataset in ONE subprocess call using the strict measurement ROI detector."""
    from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
    from app.io.dicom_loader import load_dicom_series
    import cv2

    worker = GoTocrBatchWorker()
    # Uses the strict color-thresholded measurement ROI detector, not the old broad top-left heuristic.
    detector = TopLeftBlueGrayBoxDetector()
    results_cache: dict = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)

        print("Extracting and saving dataset frames to tmpdir...")
        for lf in labeled_files:
            try:
                series = load_dicom_series(lf.path)
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
                    print(f"  ⚠ No text box found in {lf.path.name}")
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
                print(f"  ✗ Extraction error for {lf.path.name}: {e}")
                traceback.print_exc()

        saved = list(dir_path.glob("*.png"))
        print(f"Saved {len(saved)} ROI images. Running GOT-OCR 2.0 (this may take a few minutes)...")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as jf:
            json_path = jf.name

        try:
            result = subprocess.run(
                ["mamba", "run", "-n", "gotocr", "python", str(worker.script), str(dir_path), json_path],
                capture_output=False,  # let progress stream to terminal
                check=True,
            )

            with open(json_path) as f:
                data = json.load(f)

            if "error" in data and isinstance(data, dict) and len(data) == 1:
                print(f"GOT-OCR batch error: {data['error']}")
            else:
                results_cache = data
                ok = sum(1 for v in data.values() if v.get("text"))
                print(f"GOT-OCR extracted text from {ok}/{len(saved)} images.")

        except subprocess.CalledProcessError as e:
            print(f"GOT-OCR subprocess crashed with exit code {e.returncode}")
        finally:
            Path(json_path).unlink(missing_ok=True)

    return results_cache


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(DEFAULT_EXACT_LINES_PATH))
    parser.add_argument("--split", default="validation")
    parser.add_argument("--parser", default="local_llm")
    parser.add_argument("--no-normalize", action="store_true", help="Disable GOT-OCR normalizer (for comparison)")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    split_filter = {
        item.strip().lower()
        for item in args.split.split(",")
        if item.strip()
    }
    labeled_files = parse_labels(labels_path, split_filter=split_filter)
    print(f"Parsed {len(labeled_files)} labeled files\n")

    cache = preload_gotocr_batch(labeled_files)

    expected_order = [lf.path.name for lf in labeled_files]
    normalize = not args.no_normalize
    seq_engine = SequentialGoTocrEngine(cache, expected_order, normalize=normalize)

    engine_label = "gotocr-2.0" if normalize else "gotocr-2.0 (raw)"
    print(f"\n--- Evaluating with: {engine_label} (normalizer={'ON' if normalize else 'OFF'}) ---")

    class DummyArgs:
        def __init__(self, p):
            self.parser = p

    scores = run_evaluation(labeled_files, seq_engine, verbose=True, args=DummyArgs(args.parser))
    print_summary("gotocr-2.0", scores)


if __name__ == "__main__":
    main()
