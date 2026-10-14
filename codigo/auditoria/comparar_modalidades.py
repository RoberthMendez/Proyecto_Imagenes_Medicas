import nibabel as nib
import numpy as np
from pathlib import Path

estudio = (
    Path(__file__).resolve().parent.parent.parent
    / "datos"
    / "BraTS2023-GLI-Dataset"
    / "BraTS-GLI-00000-000"
)

for modalidad in ["t1n", "t1c", "t2w", "t2f", "seg"]:
    comprimido = estudio / f"{estudio.name}-{modalidad}.nii.gz"
    carpeta = estudio / f"{estudio.name}-{modalidad}.nii"

    archivos = list(carpeta.glob("*.nii")) if carpeta.is_dir() else []

    if not comprimido.is_file() or len(archivos) != 1:
        print(f"{modalidad}: estructura inesperada; requiere revisión")
        continue

    img_a = nib.load(str(archivos[0]))
    img_b = nib.load(str(comprimido))

    iguales = (
        img_a.shape == img_b.shape
        and np.array_equal(img_a.affine, img_b.affine)
        and np.array_equal(img_a.get_fdata(), img_b.get_fdata())
    )

    print(f"{modalidad}: imágenes idénticas = {iguales}")
