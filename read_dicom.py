import os
import numpy as np
import pydicom
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.text import Text

DICOM_FILE = "../database_stage/files/p10/p10002221/s94106955/94106955_0068.dcm"

def get_fps(ds, default_fps=30.0):
    if "RecommendedDisplayFrameRate" in ds:
        try:
            return float(ds.RecommendedDisplayFrameRate)
        except Exception:
            pass
    if "FrameTime" in ds:
        try:
            ms = float(ds.FrameTime)
            if ms > 0:
                return 1000.0 / ms
        except Exception:
            pass
    return default_fps

def extract_patient_info(ds):
    """Extract patient information from DICOM dataset."""
    info = {}
    tags = {
        "PatientName": ("Patient's Name", "PatientName"),
        "PatientID": ("Patient ID", "PatientID"),
        "PatientBirthDate": ("Birth Date", "PatientBirthDate"),
        "PatientSex": ("Sex", "PatientSex"),
        "StudyDate": ("Study Date", "StudyDate"),
        "StudyTime": ("Study Time", "StudyTime"),
        "StudyDescription": ("Study Description", "StudyDescription"),
        "SeriesDescription": ("Series Description", "SeriesDescription"),
        "InstitutionName": ("Institution", "InstitutionName"),
    }
    
    for key, (label, tag) in tags.items():
        if hasattr(ds, tag):
            value = getattr(ds, tag)
            if value:
                if isinstance(value, pydicom.valuerep.PersonName):
                    info[label] = str(value)
                else:
                    info[label] = str(value)
    
    return info

def extract_overlays(ds):
    """Extract overlay data from DICOM dataset."""
    overlays = []
    
    # Check for overlays in groups 60xx (6000-601E)
    for group in range(0x6000, 0x601F, 2):
        if (group, 0x3000) in ds:  # OverlayData exists
            try:
                overlay_data = ds.overlay_array(group)
                
                # Get overlay metadata
                overlay_rows = None
                overlay_cols = None
                overlay_origin = None
                overlay_frames = None
                
                if (group, 0x0010) in ds:  # OverlayRows
                    overlay_rows = ds[group, 0x0010].value
                if (group, 0x0011) in ds:  # OverlayColumns
                    overlay_cols = ds[group, 0x0011].value
                if (group, 0x0050) in ds:  # OverlayOrigin
                    overlay_origin = ds[group, 0x0050].value
                if (group, 0x0015) in ds:  # NumberOfFramesInOverlay
                    overlay_frames = ds[group, 0x0015].value
                
                overlays.append({
                    'data': overlay_data,
                    'group': group,
                    'rows': overlay_rows,
                    'cols': overlay_cols,
                    'origin': overlay_origin,
                    'frames': overlay_frames
                })
            except Exception as e:
                print(f"Warning: Could not extract overlay from group {group:04X}: {e}")
                continue
    
    return overlays

class CineViewer:
    def __init__(self, frames, fps, patient_info=None, overlays=None):
        self.frames = frames
        self.n = frames.shape[0]
        self.fps = fps
        self.idx = 0
        self.playing = False
        self.timer = None
        self.patient_info = patient_info or {}
        self.overlays = overlays or []

        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.22, right=0.75)

        self.img = self.ax.imshow(self.frames[self.idx], cmap='gray')
        self.ax.axis("off")
        self.title = self.ax.set_title(self._title_text())
        
        # Store overlay artists for updating
        self.overlay_artists = []
        
        # Display patient information
        self._display_patient_info()
        
        # Display overlays
        self._display_overlays()

        # Slider
        ax_slider = plt.axes([0.15, 0.11, 0.7, 0.04])
        self.slider = Slider(
            ax=ax_slider,
            label="Frame",
            valmin=0,
            valmax=self.n - 1,
            valinit=self.idx,
            valstep=1
        )
        self.slider.on_changed(self.on_slider)

        # Buttons
        ax_prev = plt.axes([0.15, 0.03, 0.1, 0.05])
        ax_play = plt.axes([0.27, 0.03, 0.12, 0.05])
        ax_next = plt.axes([0.41, 0.03, 0.1, 0.05])

        self.btn_prev = Button(ax_prev, "Prev")
        self.btn_play = Button(ax_play, "Play")
        self.btn_next = Button(ax_next, "Next")

        self.btn_prev.on_clicked(self.on_prev)
        self.btn_play.on_clicked(self.on_play_pause)
        self.btn_next.on_clicked(self.on_next)

        # Timer for autoplay
        interval_ms = int(1000 / self.fps)
        self.timer = self.fig.canvas.new_timer(interval=interval_ms)
        self.timer.add_callback(self.tick)

        # Keyboard shortcuts
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

    def _title_text(self):
        state = "Playing" if self.playing else "Paused"
        return f"Frame {self.idx+1}/{self.n} | {self.fps:.2f} FPS | {state}"
    
    def _display_patient_info(self):
        """Display patient information as text overlay."""
        if not self.patient_info:
            return
        
        # Create text box on the right side
        info_text = []
        for key, value in self.patient_info.items():
            info_text.append(f"{key}: {value}")
        
        info_str = "\n".join(info_text)
        
        # Position text box on the right side of the figure
        self.info_text = self.fig.text(
            0.76, 0.95, info_str,
            fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
            family='monospace'
        )
    
    def _display_overlays(self):
        """Display overlay graphics on the image."""
        if not self.overlays:
            return
        
        frame_height, frame_width = self.frames.shape[1], self.frames.shape[2]
        
        for overlay in self.overlays:
            overlay_data = overlay['data']
            origin = overlay['origin']
            
            # Handle multi-frame overlays
            if len(overlay_data.shape) == 3:
                # Overlay has frames
                overlay_frame = overlay_data[self.idx] if self.idx < overlay_data.shape[0] else overlay_data[0]
            else:
                # Single overlay for all frames
                overlay_frame = overlay_data
            
            # Resize overlay if needed to match image dimensions
            if overlay_frame.shape != (frame_height, frame_width):
                try:
                    from scipy import ndimage
                    zoom_y = frame_height / overlay_frame.shape[0]
                    zoom_x = frame_width / overlay_frame.shape[1]
                    overlay_frame = ndimage.zoom(overlay_frame, (zoom_y, zoom_x), order=0)
                except ImportError:
                    # Fallback: simple nearest-neighbor resize using numpy
                    y_indices = np.round(np.linspace(0, overlay_frame.shape[0]-1, frame_height)).astype(int)
                    x_indices = np.round(np.linspace(0, overlay_frame.shape[1]-1, frame_width)).astype(int)
                    overlay_frame = overlay_frame[np.ix_(y_indices, x_indices)]
            
            # Apply origin offset if specified
            if origin and len(origin) >= 2:
                # Origin is typically (row, column) offset
                pass  # Origin is already accounted for in overlay positioning
            
            # Create overlay image with transparency
            overlay_alpha = np.where(overlay_frame > 0, 0.5, 0)
            overlay_colored = np.zeros((*overlay_frame.shape, 4))
            overlay_colored[:, :, 0] = 1.0  # Red channel
            overlay_colored[:, :, 3] = overlay_alpha  # Alpha channel
            
            overlay_img = self.ax.imshow(overlay_colored, alpha=overlay_alpha, interpolation='nearest')
            self.overlay_artists.append(overlay_img)

    def update_view(self):
        self.img.set_data(self.frames[self.idx])
        self.title.set_text(self._title_text())
        
        # Update overlays if they are frame-specific
        for i, overlay in enumerate(self.overlays):
            overlay_data = overlay['data']
            if len(overlay_data.shape) == 3 and self.idx < overlay_data.shape[0]:
                # Multi-frame overlay - update the displayed frame
                frame_height, frame_width = self.frames.shape[1], self.frames.shape[2]
                overlay_frame = overlay_data[self.idx]
                
                # Resize if needed
                if overlay_frame.shape != (frame_height, frame_width):
                    try:
                        from scipy import ndimage
                        zoom_y = frame_height / overlay_frame.shape[0]
                        zoom_x = frame_width / overlay_frame.shape[1]
                        overlay_frame = ndimage.zoom(overlay_frame, (zoom_y, zoom_x), order=0)
                    except ImportError:
                        # Fallback: simple nearest-neighbor resize using numpy
                        y_indices = np.round(np.linspace(0, overlay_frame.shape[0]-1, frame_height)).astype(int)
                        x_indices = np.round(np.linspace(0, overlay_frame.shape[1]-1, frame_width)).astype(int)
                        overlay_frame = overlay_frame[np.ix_(y_indices, x_indices)]
                
                overlay_alpha = np.where(overlay_frame > 0, 0.5, 0)
                overlay_colored = np.zeros((*overlay_frame.shape, 4))
                overlay_colored[:, :, 0] = 1.0
                overlay_colored[:, :, 3] = overlay_alpha
                
                if i < len(self.overlay_artists):
                    self.overlay_artists[i].set_array(overlay_colored)
        
        self.slider.eventson = False
        self.slider.set_val(self.idx)
        self.slider.eventson = True
        self.fig.canvas.draw_idle()

    def on_slider(self, val):
        self.idx = int(val)
        self.update_view()

    def on_prev(self, _event):
        self.idx = (self.idx - 1) % self.n
        self.update_view()

    def on_next(self, _event):
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_play_pause(self, _event):
        self.playing = not self.playing
        self.btn_play.label.set_text("Pause" if self.playing else "Play")
        if self.playing:
            self.timer.start()
        else:
            self.timer.stop()
        self.update_view()

    def tick(self):
        if not self.playing:
            return
        self.idx = (self.idx + 1) % self.n
        self.update_view()

    def on_key(self, event):
        if event.key in (" ", "p"):
            self.on_play_pause(None)
        elif event.key in ("right", "d"):
            self.on_next(None)
        elif event.key in ("left", "a"):
            self.on_prev(None)

def main():
    if not os.path.exists(DICOM_FILE):
        raise FileNotFoundError(DICOM_FILE)

    ds = pydicom.dcmread(DICOM_FILE)
    frames = ds.pixel_array
    if frames.dtype != np.uint8:
        frames = np.clip(frames, 0, 255).astype(np.uint8)

    fps = get_fps(ds, 30.0)
    
    # Extract patient information and overlays
    patient_info = extract_patient_info(ds)
    overlays = extract_overlays(ds)
    
    print(f"Found {len(overlays)} overlay(s)")
    if patient_info:
        print("Patient information extracted:")
        for key, value in patient_info.items():
            print(f"  {key}: {value}")
    
    viewer = CineViewer(frames, fps, patient_info=patient_info, overlays=overlays)
    plt.show()

if __name__ == "__main__":
    main()
