from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from app.pipeline.ocr.char_cnn_arch import CHAR_CNN_VARIANTS, build_char_fallback_cnn, default_cnn_variant


def _resolve_training_device(name: str) -> str:
    key = (name or "cpu").strip().lower()
    if key in ("auto", "default"):
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    return str(name).strip() or "cpu"


def _train_time_augment_gray(gray_u8: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Light geometric + photometric jitter on uint8 grayscale (before resize to CNN input)."""
    g = gray_u8.astype(np.uint8, copy=False)
    if g.size == 0:
        return g
    h, w = int(g.shape[0]), int(g.shape[1])
    if h >= 3 and w >= 3:
        center = (w * 0.5, h * 0.5)
        angle = float(rng.uniform(-10.0, 10.0))
        scale = float(rng.uniform(0.9, 1.1))
        M = cv2.getRotationMatrix2D(center, angle, scale)
        M[0, 2] += float(rng.uniform(-1.5, 1.5))
        M[1, 2] += float(rng.uniform(-1.5, 1.5))
        g = cv2.warpAffine(
            g,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
    out = g.astype(np.float32)
    out = out * float(rng.uniform(0.88, 1.12)) + float(rng.uniform(-12.0, 12.0))
    out = np.clip(out, 0, 255).astype(np.uint8)
    if rng.random() < 0.35:
        sig = float(rng.uniform(0.2, 1.0))
        g2 = cv2.GaussianBlur(out, (3, 3), sigmaX=sig)
        out = g2
    if rng.random() < 0.45:
        out = np.clip(out.astype(np.float32) + float(rng.normal(0.0, 6.0)), 0, 255).astype(np.uint8)
    return out


class CharDataset(Dataset):
    def __init__(
        self,
        *,
        dataset_root: Path,
        samples: list[dict[str, Any]],
        charset: str,
        input_size: int,
        augment: bool = False,
    ) -> None:
        self.dataset_root = dataset_root
        self.samples = samples
        self.charset = charset
        self.input_size = int(input_size)
        self.augment = bool(augment)
        self.label_to_index = {label: idx for idx, label in enumerate(charset)}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        sample = self.samples[index]
        rel = Path(str(sample["image_path"]))
        path = self.dataset_root / rel
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            image = np.ones((self.input_size, self.input_size), dtype=np.uint8) * 255
        if self.augment:
            image = _train_time_augment_gray(image, np.random.default_rng())
        image = cv2.resize(image, (self.input_size, self.input_size), interpolation=cv2.INTER_AREA)
        arr = image.astype(np.float32) / 255.0
        tensor = torch.from_numpy(arr).unsqueeze(0)
        label = str(sample["label"])
        target = int(self.label_to_index[label])
        return tensor, target


@dataclass
class TrainConfig:
    dataset_dir: Path
    output_root: Path
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    patience: int
    min_delta: float
    input_size: int
    device: str
    train_augment: bool
    early_stop: bool
    min_epochs: int
    label_smoothing: float
    lr_scheduler_factor: float
    lr_scheduler_patience: int
    cnn_variant: str


def _load_manifest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    charset = str(payload.get("charset") or "")
    samples = payload.get("samples", []) if isinstance(payload.get("samples"), list) else []
    if not charset:
        raise ValueError(f"Missing charset in {path}")
    return charset, samples


def _compute_loader_mean_std(loader: DataLoader) -> tuple[float, float]:
    sums = 0.0
    sq_sums = 0.0
    count = 0
    for images, _targets in loader:
        arr = images.numpy()
        sums += float(arr.sum())
        sq_sums += float((arr * arr).sum())
        count += int(arr.size)
    if count <= 0:
        return 0.5, 0.25
    mean = sums / count
    var = max(1e-8, (sq_sums / count) - (mean * mean))
    return float(mean), float(np.sqrt(var))


def _evaluate(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: str,
    mean: float,
    std: float,
) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total = 0
    wrong = 0
    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device)
            images = (images - float(mean)) / max(float(std), 1e-6)
            targets = targets.to(device)
            logits = model(images)
            loss = loss_fn(logits, targets)
            total_loss += float(loss.item()) * int(images.size(0))
            preds = torch.argmax(logits, dim=1)
            wrong += int((preds != targets).sum().item())
            total += int(images.size(0))
    if total <= 0:
        return 0.0, 1.0
    return total_loss / total, wrong / total


def train(config: TrainConfig) -> dict[str, Any]:
    train_charset, train_samples = _load_manifest(config.dataset_dir / "train_manifest.json")
    val_charset, val_samples = _load_manifest(config.dataset_dir / "val_manifest.json")
    if train_charset != val_charset:
        raise ValueError("Train and val charset mismatch")
    charset = train_charset

    stats_dataset = CharDataset(
        dataset_root=config.dataset_dir,
        samples=train_samples,
        charset=charset,
        input_size=config.input_size,
        augment=False,
    )
    stats_loader = DataLoader(stats_dataset, batch_size=config.batch_size, shuffle=False)
    mean, std = _compute_loader_mean_std(stats_loader)

    train_dataset = CharDataset(
        dataset_root=config.dataset_dir,
        samples=train_samples,
        charset=charset,
        input_size=config.input_size,
        augment=config.train_augment,
    )
    val_dataset = CharDataset(
        dataset_root=config.dataset_dir,
        samples=val_samples,
        charset=charset,
        input_size=config.input_size,
        augment=False,
    )

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False)

    def _normalize_batch(images: torch.Tensor) -> torch.Tensor:
        return (images - mean) / max(std, 1e-6)

    class_weights = np.ones(len(charset), dtype=np.float32)
    labels = [sample["label"] for sample in train_samples]
    counts = {ch: labels.count(ch) for ch in charset}
    max_count = max(counts.values()) if counts else 1
    for idx, label in enumerate(charset):
        class_weights[idx] = float(max_count) / float(max(1, counts.get(label, 0)))

    device = _resolve_training_device(config.device)
    if device.startswith("cuda"):
        torch.backends.cudnn.benchmark = True

    model = build_char_fallback_cnn(len(charset), config.cnn_variant).to(device)
    loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device),
        label_smoothing=float(config.label_smoothing),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=float(config.lr_scheduler_factor),
        patience=int(config.lr_scheduler_patience),
        min_lr=1e-7,
    )

    best_cer = 1.0
    best_state = None
    best_epoch = -1
    history: list[dict[str, float]] = []
    stale_epochs = 0
    min_epochs = max(1, min(int(config.min_epochs), int(config.epochs)))

    for epoch in range(config.epochs):
        model.train()
        running_loss = 0.0
        seen = 0
        for images, targets in train_loader:
            images = _normalize_batch(images.to(device))
            targets = targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = loss_fn(logits, targets)
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item()) * int(images.size(0))
            seen += int(images.size(0))

        train_loss = running_loss / max(1, seen)
        val_loss, val_cer = _evaluate(model, val_loader, loss_fn, device, mean, std)
        lr_now = float(optimizer.param_groups[0]["lr"])
        scheduler.step(val_loss)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": float(train_loss),
                "val_loss": float(val_loss),
                "val_cer": float(val_cer),
                "lr": lr_now,
            }
        )
        print(
            f"[epoch {epoch + 1:03d}/{config.epochs}] "
            f"train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} "
            f"val_cer={val_cer:.4f} "
            f"lr={lr_now:.3e}",
            flush=True,
        )

        if val_cer + config.min_delta < best_cer:
            best_cer = val_cer
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
            best_epoch = epoch
            stale_epochs = 0
            print(
                f"  -> new best: val_cer={best_cer:.4f} at epoch {best_epoch + 1}",
                flush=True,
            )
        else:
            if epoch + 1 < min_epochs:
                stale_epochs = 0
            else:
                stale_epochs += 1
            if (
                config.early_stop
                and epoch + 1 >= min_epochs
                and stale_epochs >= int(config.patience)
            ):
                print(
                    f"Early stopping at epoch {epoch + 1} (no val_cer improvement for {stale_epochs} epochs).",
                    flush=True,
                )
                break

    if best_state is None:
        best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = config.output_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    torch.save({"state_dict": best_state}, out_dir / "model.pt")
    (out_dir / "charset.json").write_text(
        json.dumps(
            {"charset": charset, "input_size": config.input_size, "cnn_variant": str(config.cnn_variant)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "normalization.json").write_text(
        json.dumps({"mean": mean, "std": std}, indent=2) + "\n",
        encoding="utf-8",
    )

    metrics = {
        "best_epoch": int(best_epoch),
        "best_val_cer": float(best_cer),
        "epochs_run": len(history),
        "early_stopped": bool(config.early_stop and len(history) < int(config.epochs)),
        "history": history,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "device": device,
        "train_augment": bool(config.train_augment),
        "min_epochs": int(min_epochs),
        "label_smoothing": float(config.label_smoothing),
        "cnn_variant": str(config.cnn_variant),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    (config.output_root / "latest.txt").write_text(str(out_dir.as_posix()) + "\n", encoding="utf-8")
    return {"artifact_dir": str(out_dir), **metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description="Train compact char fallback CNN model.")
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Dataset dir with train/val manifests")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/ocr_redesign/char_model"),
        help="Versioned model output root",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=150,
        help="Maximum epochs (full run with --no-early-stop; otherwise upper cap).",
    )
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument("--learning-rate", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=2e-4)
    parser.add_argument(
        "--patience",
        type=int,
        default=30,
        help="Stop if val CER does not improve for this many epochs (after --min-epochs).",
    )
    parser.add_argument(
        "--min-epochs",
        type=int,
        default=60,
        help="Always train at least this many epochs before early stopping can trigger.",
    )
    parser.add_argument(
        "--no-early-stop",
        action="store_true",
        help="Run all --epochs; still save the checkpoint with best val CER seen at any epoch.",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.08,
        help="Cross-entropy label smoothing (0 to disable). Reduces overconfidence on tiny val sets.",
    )
    parser.add_argument(
        "--lr-scheduler-factor",
        type=float,
        default=0.5,
        help="ReduceLROnPlateau: multiply LR by this when val loss plateaus.",
    )
    parser.add_argument(
        "--lr-scheduler-patience",
        type=int,
        default=5,
        help="ReduceLROnPlateau: epochs with no val-loss improvement before LR drop.",
    )
    parser.add_argument("--min-delta", type=float, default=5e-4)
    parser.add_argument("--input-size", type=int, default=24)
    parser.add_argument(
        "--cnn-variant",
        type=str,
        choices=list(CHAR_CNN_VARIANTS),
        default=default_cnn_variant(),
        help="Backbone size; must match at inference (stored in charset.json).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="cuda | cpu | auto (pick CUDA when torch was built with CUDA and a GPU is visible).",
    )
    parser.add_argument(
        "--no-train-augment",
        action="store_true",
        help="Disable random rotation/shift/blur on training images each epoch.",
    )
    args = parser.parse_args()

    result = train(
        TrainConfig(
            dataset_dir=args.dataset_dir,
            output_root=args.output_root,
            epochs=int(args.epochs),
            batch_size=int(args.batch_size),
            learning_rate=float(args.learning_rate),
            weight_decay=float(args.weight_decay),
            patience=int(args.patience),
            min_delta=float(args.min_delta),
            input_size=int(args.input_size),
            device=str(args.device),
            train_augment=not bool(args.no_train_augment),
            early_stop=not bool(args.no_early_stop),
            min_epochs=int(args.min_epochs),
            label_smoothing=float(args.label_smoothing),
            lr_scheduler_factor=float(args.lr_scheduler_factor),
            lr_scheduler_patience=int(args.lr_scheduler_patience),
            cnn_variant=str(args.cnn_variant),
        )
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
