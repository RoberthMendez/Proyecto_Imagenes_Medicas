from pathlib import Path
import csv

# Ruta del dataset
BASE = (
    Path(__file__).resolve().parent.parent
    / ".."
    / "datos"
    / "BraTS2023-GLI-Dataset"
).resolve()

SALIDA = (
    Path(__file__).resolve().parent.parent
    / ".."
    / "resultados/auditoria"
    / "inventario.csv"
).resolve()

SECUENCIAS = ["t1n", "t1c", "t2w", "t2f", "seg"]

columnas = [
    "subject_key",
    "study_id",
    "study_path",
    "t1n_exists",
    "t1c_exists",
    "t2w_exists",
    "t2f_exists",
    "seg_exists",
    "t1n_readable",
    "t1c_readable",
    "t2w_readable",
    "t2f_readable",
    "seg_readable",
]

import nibabel as nib

estudios = sorted(
    carpeta
    for carpeta in BASE.iterdir()
    if carpeta.is_dir()
    and carpeta.name.startswith("BraTS-GLI-")
    and len(carpeta.name.split("-")) == 4
)

filas = []

for estudio in estudios:
    partes = estudio.name.split("-")
    subject_key = partes[2]
    study_id = partes[3]

    fila = {
        "subject_key": subject_key,
        "study_id": study_id,
        "study_path": estudio.name,
    }

    for secuencia in SECUENCIAS:
        archivo = estudio / f"{estudio.name}-{secuencia}.nii.gz"
        existe = archivo.is_file()
        legible = False

        if existe:
            try:
                imagen = nib.load(str(archivo))
                _ = imagen.shape
                legible = True
            except Exception:
                legible = False

        fila[f"{secuencia}_exists"] = existe
        fila[f"{secuencia}_readable"] = legible

    filas.append(fila)

SALIDA.parent.mkdir(parents=True, exist_ok=True)

with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo_csv:
    escritor = csv.DictWriter(archivo_csv, fieldnames=columnas)
    escritor.writeheader()
    escritor.writerows(filas)

pacientes = {fila["subject_key"] for fila in filas}

print("Inventario inicial terminado.")
print(f"Estudios encontrados: {len(filas)}")
print(f"Identificadores de paciente distintos: {len(pacientes)}")
print(f"Archivo guardado en: {SALIDA}")