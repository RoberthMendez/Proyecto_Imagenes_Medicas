
from pathlib import Path

import numpy as np
import pandas as pd

from codigo.segmentacion.preparar_datos import preparar_estudio
from codigo.segmentacion.dataset_2d import Dataset2D


PROYECTO = Path(__file__).resolve().parents[2]
RUTA_SALIDA = (
    PROYECTO
    / "resultados"
    / "segmentacion"
    / "auditoria_normalizacion.csv"
)

MODALIDADES = ("t1n", "t1c", "t2w", "t2f")


def resumir_modalidad(estudio_id, nombre, imagen):
    imagen = np.asarray(imagen)
    validos = imagen != 0
    valores = imagen[validos]

    if valores.size == 0:
        return {
            "estudio": estudio_id,
            "modalidad": nombre,
            "voxeles_validos": 0,
            "proporcion_no_cero": 0.0,
            "media": np.nan,
            "desviacion": np.nan,
            "minimo": np.nan,
            "maximo": np.nan,
            "valores_no_finitos": int(
                (~np.isfinite(imagen)).sum()
            ),
        }

    return {
        "estudio": estudio_id,
        "modalidad": nombre,
        "voxeles_validos": int(validos.sum()),
        "proporcion_no_cero": float(validos.mean()),
        "media": float(valores.mean()),
        "desviacion": float(valores.std()),
        "minimo": float(valores.min()),
        "maximo": float(valores.max()),
        "valores_no_finitos": int(
            (~np.isfinite(imagen)).sum()
        ),
    }


def main():
    filas = []

    # Revisar los mismos dos estudios usados para el entrenamiento.
    train = Dataset2D("train", max_estudios=2)
    estudios_train = list(train.estudios)

    # Revisar cinco estudios del conjunto de validación.
    validation = Dataset2D("validation", max_estudios=5)
    estudios_validation = list(validation.estudios)

    estudios = [
        ("train", estudio_id)
        for estudio_id in estudios_train
    ] + [
        ("validation", estudio_id)
        for estudio_id in estudios_validation
    ]

    for particion, estudio_id in estudios:
        preparado = preparar_estudio(estudio_id)

        for modalidad in MODALIDADES:
            fila = resumir_modalidad(
                estudio_id,
                modalidad,
                preparado["imagenes"][modalidad],
            )
            fila["particion"] = particion
            filas.append(fila)

    df = pd.DataFrame(filas)

    columnas = [
        "particion",
        "estudio",
        "modalidad",
        "voxeles_validos",
        "proporcion_no_cero",
        "media",
        "desviacion",
        "minimo",
        "maximo",
        "valores_no_finitos",
    ]

    df = df[columnas]
    df.to_csv(RUTA_SALIDA, index=False)

    print("\nAuditoría de normalización")
    print(df.to_string(index=False))
    print("\nReporte guardado en:", RUTA_SALIDA)

    if (df["valores_no_finitos"] > 0).any():
        print("\nADVERTENCIA: se encontraron valores no finitos.")

    if (df["desviacion"].fillna(0) < 0.5).any():
        print(
            "\nADVERTENCIA: hay modalidades con desviación "
            "estándar normalizada inferior a 0.5."
        )


if __name__ == "__main__":
    main()
