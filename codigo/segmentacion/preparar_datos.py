
from pathlib import Path

import numpy as np

from codigo.segmentacion.cargar_datos import cargar_estudio


def normalizar_modalidad(imagen: np.ndarray) -> np.ndarray:
    """Normaliza los vóxeles no nulos de una modalidad."""

    imagen = imagen.astype(np.float32, copy=False)
    mascara_valida = imagen != 0

    if not np.any(mascara_valida):
        return np.zeros_like(imagen, dtype=np.float32)

    valores = imagen[mascara_valida]
    media = valores.mean()
    desviacion = valores.std()

    resultado = np.zeros_like(imagen, dtype=np.float32)

    if desviacion > 1e-8:
        resultado[mascara_valida] = (
            valores - media
        ) / desviacion
    else:
        resultado[mascara_valida] = valores - media

    return resultado


def preparar_estudio(estudio_id: str) -> dict:
    """Carga un estudio y prepara sus modalidades y máscara."""

    estudio = cargar_estudio(estudio_id)

    imagenes = {
        nombre: normalizar_modalidad(datos)
        for nombre, datos in estudio["imagenes"].items()
    }

    mascara = estudio["mascara"]

    if not np.isin(np.unique(mascara), [0, 1, 2, 3]).all():
        raise ValueError(f"Etiquetas inesperadas en {estudio_id}")

    return {
        "estudio_id": estudio_id,
        "imagenes": imagenes,
        "mascara": mascara,
        "forma": estudio["forma"],
    }


if __name__ == "__main__":
    estudio_id = "BraTS-GLI-00000-000"
    resultado = preparar_estudio(estudio_id)

    # Tomamos un corte axial central para la prueba.
    indice = resultado["forma"][2] // 2

    corte_entrada = np.stack(
        [
            resultado["imagenes"][modalidad][:, :, indice]
            for modalidad in ("t1n", "t1c", "t2w", "t2f")
        ],
        axis=0,
    )

    corte_mascara = resultado["mascara"][:, :, indice]

    print("Estudio:", resultado["estudio_id"])
    print("Forma del volumen:", resultado["forma"])
    print("Forma del corte de entrada:", corte_entrada.shape)
    print("Forma de la máscara:", corte_mascara.shape)
    print("Etiquetas presentes:", np.unique(corte_mascara))
    print("Entrada finita:", np.isfinite(corte_entrada).all())
    print(
        "Desviación por modalidad:",
        {
            nombre: round(float(corte_entrada[i].std()), 4)
            for i, nombre in enumerate(("t1n", "t1c", "t2w", "t2f"))
        },
    )

    assert corte_entrada.shape == (4, 240, 240)
    assert corte_mascara.shape == (240, 240)
    assert np.isfinite(corte_entrada).all()

    print("Prueba de preparación superada.")
