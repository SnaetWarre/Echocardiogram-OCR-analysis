import sys
import json
import base64
import io
import traceback
from PIL import Image

def load_surya_models():
    """Load the Surya models. This happens once on startup."""
    try:
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            foundation_predictor = FoundationPredictor()
            det_predictor = DetectionPredictor()
            rec_predictor = RecognitionPredictor(foundation_predictor)
            
        return det_predictor, rec_predictor
    except Exception as e:
        # If model loading fails, print error as JSON and exit
        error_msg = {"error": f"Failed to load Surya models: {str(e)}\n{traceback.format_exc()}"}
        print(json.dumps(error_msg), flush=True)
        sys.exit(1)

def main():
    # Load models on startup
    det_predictor, rec_predictor = load_surya_models()
    from surya.common.surya.schema import TaskNames
    
    # Signal readiness to the parent process by writing a specific JSON message to stdout
    print(json.dumps({"status": "ready"}), flush=True)
    
    import re
    
    # Event loop: read from stdin, write to stdout
    while True:
        line = sys.stdin.readline()
        if not line:
            break
            
        line = line.strip()
        if not line:
            continue
            
        try:
            req = json.loads(line)
            req_id = req.get("id")
            image_b64 = req.get("image_base64")
            
            if not image_b64:
                raise ValueError("Missing 'image_base64' in request")
                
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            import contextlib
            with contextlib.redirect_stdout(sys.stderr):
                predictions = rec_predictor([image], [TaskNames.ocr_with_boxes], det_predictor=det_predictor)
                
            texts = []
            if predictions[0].text_lines:
                for tline in predictions[0].text_lines:
                    # Strip HTML formatting tags (like <b>, <i>) that Surya adds
                    clean_text = re.sub(r"<[^>]+>", "", tline.text)
                    texts.append(clean_text)
                    
            full_text = "\n".join(texts)
            
            res = {
                "id": req_id,
                "text": full_text,
                "confidence": 0.99
            }
            print(json.dumps(res), flush=True)
            
        except Exception as e:
            # Send error back for this specific request
            res = {
                "id": req.get("id", "unknown"),
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            print(json.dumps(res), flush=True)

if __name__ == "__main__":
    main()
