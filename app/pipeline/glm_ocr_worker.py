import sys
import json
import base64
import io
import os
import traceback
import contextlib
import tempfile
import uuid
from PIL import Image

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

def load_glm_ocr_model():
    """Load the GLM-OCR model and processor."""
    try:
        from transformers import AutoProcessor, AutoModelForImageTextToText

        # Hub id or local directory (snapshots use cache after first download).
        _model = os.environ.get("GLM_OCR_MODEL", "").strip()
        MODEL_PATH = _model if _model else "zai-org/GLM-OCR"
        
        with (
            open(os.devnull, "w", encoding="utf-8") as devnull,
            contextlib.redirect_stdout(devnull),
            contextlib.redirect_stderr(devnull),
        ):
            processor = AutoProcessor.from_pretrained(MODEL_PATH)
            model = AutoModelForImageTextToText.from_pretrained(
                pretrained_model_name_or_path=MODEL_PATH,
                torch_dtype="auto",
                device_map="auto",
                trust_remote_code=True
            )
            
        return processor, model
    except Exception as e:
        error_msg = {"error": f"Failed to load GLM-OCR model: {str(e)}\n{traceback.format_exc()}"}
        print(json.dumps(error_msg), flush=True)
        sys.exit(1)

def main():
    processor, model = load_glm_ocr_model()
    
    # Signal readiness to the parent process
    print(json.dumps({"status": "ready"}), flush=True)
    
    while True:
        line = sys.stdin.readline()
        if not line:
            break
            
        line = line.strip()
        if not line:
            continue
            
        tmp_path = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            image_b64 = req.get("image_base64")
            
            if not image_b64:
                raise ValueError("Missing 'image_base64' in request")
                
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            temp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(temp_dir, f"glm_ocr_tmp_{uuid.uuid4().hex}.png")
            image.save(tmp_path)
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "url": tmp_path
                        },
                        {
                            "type": "text",
                            "text": "Text Recognition:"
                        }
                    ],
                }
            ]
            
            with (
                open(os.devnull, "w", encoding="utf-8") as devnull,
                contextlib.redirect_stdout(devnull),
                contextlib.redirect_stderr(devnull),
            ):
                inputs = processor.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_dict=True,
                    return_tensors="pt"
                ).to(model.device)
                inputs.pop("token_type_ids", None)
                
                generated_ids = model.generate(**inputs, max_new_tokens=8192)
                output_text = processor.decode(generated_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            
            clean_text = output_text.strip()

            tokens = [
                {
                    "text": line_text.strip(),
                    "confidence": 0.99,
                    "bbox": None
                }
                for line_text in clean_text.split('\n') if line_text.strip()
            ]
            
            res = {
                "id": req_id,
                "text": clean_text,
                "confidence": 0.99,
                "tokens": tokens,
            }
            print(json.dumps(res), flush=True)
            
        except Exception as e:
            res = {
                "id": req.get("id", "unknown"),
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            print(json.dumps(res), flush=True)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

if __name__ == "__main__":
    main()
