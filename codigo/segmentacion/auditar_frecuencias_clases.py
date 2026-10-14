
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

from codigo.segmentacion.dataset_2d import Dataset2D


PROYECTO = Path(__file__).resolve().parents[2]
SALIDA = (
    PROYECTO
    / "resultados"
    / "segmentacion"
    / "frecuencias_clases_train.csv"
)

NUM_ESTUDIOS = 50


def main():
    dataset = Dataset2D(
        "train",
        max_estudios=NUM_ESTUDIOS,
    )

    conteos = np.zeros(4, dtype=np.int64)
    filas = []

    print(
        f"Analizando las máscaras de "
        f"{len(dataset.estudios)} estudios de entrenamiento."
    )

    for estudio_id in dataset.estudios:
        carpeta = (
            PROYECTO
            / "datos"
            / "BraTS2023-GLI-Dataset"
            / estudio_id
        )

        archivos = sorted(carpeta.glob("*seg.nii*"))

        if len(archivos) != 1:
            raise FileNotFoundError(
                f"No se encontró una única máscara para {estudio_id}"
            )

        mascara = np.asarray(
            nib.load(str(archivos[0])).dataobj
        )

        if not np.isin(np.unique(mascara), [0, 1, 2, 3]).all():
            raise ValueError(
                f"Etiquetas inesperadas en {estudio_id}"
            )

        conteo_estudio = np.bincount(
            mascara.astype(np.uint8).ravel(),
            minlength=4,
        )

        conteos += conteo_estudio

        fila = {
            "estudio": estudio_id,
            "voxeles_totales": int(mascara.size),
        }

        for clase in range(4):
            fila[f"pixeles_clase_{clase}"] = int(
                conteo_estudio[clase]
            )

        filas.append(fila)

        print(f"Procesado: {estudio_id}")

    total = int(conteos.sum())
    frecuencias = conteos / total

    resumen = pd.DataFrame({
        "clase": range(4),
        "voxeles": conteos,
        "frecuencia": frecuencias,
    })

    print("\nFrecuencias globales de la muestra")
    print(resumen.to_string(index=False))

    print("\nPesos inversos a la raíz de la frecuencia:")
    pesos = np.zeros(4, dtype=np.float64)
    presentes = conteos > 0
    pesos[presentes] = 1 / np.sqrt(frecuencias[presentes])
    pesos[presentes] /= pesos[presentes].mean()
    pesos[0] *= 0.25

    print(pesos.tolist())

    pd.DataFrame(filas).to_csv(
        SALIDA.with_name("conteos_por_estudio_train.csv"),
        index=False,
    )

    resumen.to_csv(SALIDA, index=False)

    print("\nReporte guardado en:", SALIDA)


if __name__ == "__main__":
    main()
