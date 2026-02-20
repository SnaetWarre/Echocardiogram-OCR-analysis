import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

from .dicom_data import DicomContent


class CineViewer:
    def __init__(self, content: DicomContent):
        self.content = content
        self.frames = content.frames
        self.n = self.frames.shape[0]
        self.fps = content.fps
        self.idx = 0
        self.playing = False

        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.22, right=0.75)

        self._is_color = len(self.frames.shape) == 4 and self.frames.shape[-1] in (3, 4)
        first = self.frames[self.idx]
        self.img = self.ax.imshow(first if self._is_color else first, cmap=None if self._is_color else "gray")
        self.ax.axis("off")
        self.title = self.ax.set_title(self._title_text())

        self._draw_patient_info()

        ax_slider = plt.axes([0.15, 0.11, 0.7, 0.04])
        self.slider = Slider(ax_slider, "Frame", 0, self.n - 1, valinit=self.idx, valstep=1)
        self.slider.on_changed(self.on_slider)

        ax_prev = plt.axes([0.15, 0.03, 0.1, 0.05])
        ax_play = plt.axes([0.27, 0.03, 0.12, 0.05])
        ax_next = plt.axes([0.41, 0.03, 0.1, 0.05])

        self.btn_prev = Button(ax_prev, "Prev")
        self.btn_play = Button(ax_play, "Play")
        self.btn_next = Button(ax_next, "Next")

        self.btn_prev.on_clicked(self.on_prev)
        self.btn_play.on_clicked(self.on_play_pause)
        self.btn_next.on_clicked(self.on_next)

        interval_ms = max(1, int(1000 / self.fps))
        self.timer = self.fig.canvas.new_timer(interval=interval_ms)
        self.timer.add_callback(self.tick)

        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

    def _title_text(self) -> str:
        state = "Playing" if self.playing else "Paused"
        return f"Frame {self.idx + 1}/{self.n} | {self.fps:.2f} FPS | {state}"

    def _draw_patient_info(self) -> None:
        if not self.content.patient_info:
            return
        lines = [f"{k}: {v}" for k, v in self.content.patient_info.items()]
        self.fig.text(
            0.76,
            0.95,
            "\n".join(lines),
            fontsize=9,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.8},
            family="monospace",
        )

    def update_view(self) -> None:
        self.img.set_data(self.frames[self.idx])
        self.title.set_text(self._title_text())

        self.slider.eventson = False
        self.slider.set_val(self.idx)
        self.slider.eventson = True
        self.fig.canvas.draw_idle()

    def on_slider(self, val) -> None:
        self.idx = int(val)
        self.update_view()

    def on_prev(self, _event) -> None:
        self.idx = (self.idx - 1) % self.n
        self.update_view()

    def on_next(self, _event) -> None:
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_play_pause(self, _event) -> None:
        self.playing = not self.playing
        self.btn_play.label.set_text("Pause" if self.playing else "Play")
        if self.playing:
            self.timer.start()
        else:
            self.timer.stop()
        self.update_view()

    def tick(self) -> None:
        if not self.playing:
            return
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_key(self, event) -> None:
        if event.key in (" ", "p"):
            self.on_play_pause(None)
        elif event.key in ("right", "d"):
            self.on_next(None)
        elif event.key in ("left", "a"):
            self.on_prev(None)
