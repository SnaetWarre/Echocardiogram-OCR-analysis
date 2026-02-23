from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

from .dicom_data import DicomContent, load_dicom_content


class CineViewer:
    def __init__(self, content: Optional[DicomContent] = None, start_dir: Optional[Path] = None):
        self.content: Optional[DicomContent] = None
        self.frames: Optional[np.ndarray] = None
        self.n = 0
        self.fps = 30.0
        self.idx = 0
        self.playing = False
        self._last_dir = start_dir or Path.cwd()

        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.22, right=0.75)

        blank = np.zeros((512, 512), dtype=np.uint8)
        self._is_color = False
        self.img = self.ax.imshow(blank, cmap="gray")
        self.ax.axis("off")
        self.title = self.ax.set_title(self._title_text())

        self.empty_text = self.ax.text(
            0.5,
            0.5,
            "No DICOM loaded\nClick Open File or Open Folder",
            ha="center",
            va="center",
            transform=self.ax.transAxes,
            fontsize=12,
            color="#666666",
        )
        self.info_text = None

        ax_slider = plt.axes([0.15, 0.11, 0.55, 0.04])
        self.slider = Slider(ax_slider, "Frame", 0, 1, valinit=0, valstep=1)
        self.slider.on_changed(self.on_slider)

        ax_prev = plt.axes([0.15, 0.03, 0.1, 0.05])
        ax_play = plt.axes([0.27, 0.03, 0.12, 0.05])
        ax_next = plt.axes([0.41, 0.03, 0.1, 0.05])
        ax_open_folder = plt.axes([0.77, 0.11, 0.18, 0.05])
        ax_open_file = plt.axes([0.77, 0.03, 0.18, 0.05])

        neutral_color = "#f2f2f2"
        neutral_hover = "#e6e6e6"
        action_color = "#e8f1ff"
        action_hover = "#d6e6ff"

        self.btn_prev = Button(ax_prev, "Prev", color=neutral_color, hovercolor=neutral_hover)
        self.btn_play = Button(ax_play, "Play", color=neutral_color, hovercolor=neutral_hover)
        self.btn_next = Button(ax_next, "Next", color=neutral_color, hovercolor=neutral_hover)
        self.btn_open_folder = Button(ax_open_folder, "Open Folder", color=action_color, hovercolor=action_hover)
        self.btn_open_file = Button(ax_open_file, "Open File", color=action_color, hovercolor=action_hover)

        for btn in (
            self.btn_prev,
            self.btn_play,
            self.btn_next,
            self.btn_open_folder,
            self.btn_open_file,
        ):
            btn.label.set_fontsize(9)

        self.btn_prev.on_clicked(self.on_prev)
        self.btn_play.on_clicked(self.on_play_pause)
        self.btn_next.on_clicked(self.on_next)
        self.btn_open_folder.on_clicked(self.on_open_folder)
        self.btn_open_file.on_clicked(self.on_open_file)

        interval_ms = max(1, int(1000 / self.fps))
        self.timer = self.fig.canvas.new_timer(interval=interval_ms)
        self.timer.add_callback(self.tick)

        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

        if content is not None:
            self.load_content(content)

    def _pick_dicom_file(self, start_dir: Path) -> Optional[Path]:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            print(f"Could not open file picker: {exc}")
            return None

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        filetypes = [("DICOM files", "*.dcm"), ("All files", "*.*")]
        path = filedialog.askopenfilename(
            title="Select a DICOM file",
            initialdir=str(start_dir),
            filetypes=filetypes,
        )
        root.destroy()
        if not path:
            return None
        return Path(path)

    def _pick_dicom_folder(self, start_dir: Path) -> Optional[Path]:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            print(f"Could not open folder picker: {exc}")
            return None

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(
            title="Select a folder",
            initialdir=str(start_dir),
        )
        root.destroy()
        if not path:
            return None
        return Path(path)

    def _load_from_path(self, path: Path) -> None:
        if not path.exists():
            print(f"File not found: {path}")
            return
        try:
            content = load_dicom_content(str(path))
        except Exception as exc:
            print(f"Could not load DICOM: {exc}")
            return
        self.load_content(content, source_path=path)

    def load_content(self, content: DicomContent, source_path: Optional[Path] = None) -> None:
        self.content = content
        self.frames = content.frames
        self.n = int(self.frames.shape[0]) if self.frames is not None else 0
        self.fps = float(content.fps) if content.fps else 30.0
        self.idx = 0
        self.playing = False
        self.btn_play.label.set_text("Play")
        if source_path:
            self._last_dir = source_path.parent
        if self.n == 0:
            self._set_empty_state()
            return

        self._is_color = len(self.frames.shape) == 4 and self.frames.shape[-1] in (3, 4)
        if self._is_color:
            self.img.set_cmap(None)
        else:
            self.img.set_cmap("gray")
        self.img.set_data(self.frames[self.idx])
        self.empty_text.set_visible(False)
        self._update_patient_info()
        self._update_slider_range()

        interval_ms = max(1, int(1000 / self.fps))
        self.timer.interval = interval_ms
        self.update_view()

    def _set_empty_state(self) -> None:
        self.frames = None
        self.n = 0
        self.idx = 0
        self.playing = False
        self.btn_play.label.set_text("Play")
        self.img.set_data(np.zeros((512, 512), dtype=np.uint8))
        self.img.set_cmap("gray")
        self.empty_text.set_visible(True)
        self._update_patient_info()
        self._update_slider_range()
        self.update_view()

    def _update_slider_range(self) -> None:
        max_val = max(0, self.n - 1)
        slider_max = max(1, max_val)
        self.slider.valmin = 0
        self.slider.valmax = slider_max
        self.slider.ax.set_xlim(0, slider_max)
        self.slider.valstep = 1
        self.slider.eventson = False
        self.slider.set_val(min(self.idx, max_val) if self.n else 0)
        self.slider.eventson = True

    def on_open_file(self, _event) -> None:
        path = self._pick_dicom_file(self._last_dir)
        if path:
            self._load_from_path(path)

    def on_open_folder(self, _event) -> None:
        folder = self._pick_dicom_folder(self._last_dir)
        if folder:
            self._last_dir = folder
            path = self._pick_dicom_file(folder)
            if path:
                self._load_from_path(path)

    def _title_text(self) -> str:
        if self.n == 0:
            return "No DICOM loaded"
        state = "Playing" if self.playing else "Paused"
        return f"Frame {self.idx + 1}/{self.n} | {self.fps:.2f} FPS | {state}"

    def _update_patient_info(self) -> None:
        if self.info_text:
            self.info_text.remove()
            self.info_text = None
        if not self.content or not self.content.patient_info:
            return
        lines = [f"{k}: {v}" for k, v in self.content.patient_info.items()]
        self.info_text = self.fig.text(
            0.76,
            0.95,
            "\n".join(lines),
            fontsize=9,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.8},
            family="monospace",
        )

    def update_view(self) -> None:
        if self.frames is None or self.n == 0:
            self.title.set_text(self._title_text())
            self.empty_text.set_visible(True)
            self.fig.canvas.draw_idle()
            return

        self.img.set_data(self.frames[self.idx])
        self.title.set_text(self._title_text())
        self.empty_text.set_visible(False)

        self.slider.eventson = False
        self.slider.set_val(self.idx)
        self.slider.eventson = True
        self.fig.canvas.draw_idle()

    def on_slider(self, val) -> None:
        if self.frames is None or self.n == 0:
            return
        self.idx = max(0, min(int(val), self.n - 1))
        self.update_view()

    def on_prev(self, _event) -> None:
        if self.n == 0:
            return
        self.idx = (self.idx - 1) % self.n
        self.update_view()

    def on_next(self, _event) -> None:
        if self.n == 0:
            return
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_play_pause(self, _event) -> None:
        if self.n == 0:
            return
        self.playing = not self.playing
        self.btn_play.label.set_text("Pause" if self.playing else "Play")
        if self.playing:
            self.timer.start()
        else:
            self.timer.stop()
        self.update_view()

    def tick(self) -> None:
        if not self.playing or self.n == 0:
            return
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_key(self, event) -> None:
        if event.key in ("o",):
            self.on_open_file(None)
            return
        if self.n == 0:
            return
        if event.key in (" ", "p"):
            self.on_play_pause(None)
        elif event.key in ("right", "d"):
            self.on_next(None)
        elif event.key in ("left", "a"):
            self.on_prev(None)
