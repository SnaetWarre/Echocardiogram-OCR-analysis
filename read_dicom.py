import os

import matplotlib.pyplot as plt
import pydicom

from cineviewer.dicom_data import load_dicom_content
from cineviewer.viewer import CineViewer


DICOM_FILE = "../database_stage/files/p10/p10002221/s94106955/94106955_0068.dcm"


def _inspect_sequences(ds: pydicom.Dataset) -> None:
    print("\n=== DICOM Overview ===")
    pixel = ds.pixel_array
    print(f"Pixel array shape: {pixel.shape}")
    print(f"Pixel array dtype: {pixel.dtype}")

    sequences = [f"{e.tag} ({e.keyword or 'Unknown'})" for e in ds if e.VR == "SQ"]
    if sequences:
        print("Sequences:")
        for item in sequences:
            print(f"  {item}")


def main() -> None:
    if not os.path.exists(DICOM_FILE):
        raise FileNotFoundError(DICOM_FILE)

    ds = pydicom.dcmread(DICOM_FILE)
    _inspect_sequences(ds)

    content = load_dicom_content(DICOM_FILE)
    if content.patient_info:
        print("Patient info:")
        for key, value in content.patient_info.items():
            print(f"  {key}: {value}")

    viewer = CineViewer(content)
    plt.show()


if __name__ == "__main__":
    main()
