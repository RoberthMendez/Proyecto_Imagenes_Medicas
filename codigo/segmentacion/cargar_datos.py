
from pathlib import Path

import nibabel as nib
import numpy as np


# Rutas del proyecto
PROYECTO = Path(__file__).resolve().parents[2]
DATASET = PROYECTO / "datos" / "BraTS2023-GLI-Dataset"

MODALIDADES = ("t1n", "t1c", "t2w", "t2f")
NOMBRE_MASCARA = "seg"


def buscar_archivo(estudio: Path, modalidad: str) -> Path:
    """Encuentra exactamente un archivo NIfTI para una modalidad."""
    archivos = sorted(estudio.glob(f"*{modalidad}.nii*"))

    if len(archivos) != 1:
        raise FileNotFoundError(
            f"Se esperaba un archivo para '{modalidad}' "
            f"en {estudio.name}, pero se encontraron {len(archivos)}."
        )

    return archivos[0]


def cargar_estudio(estudio_id: str) -> dict:
    """
    Carga las cuatro modalidades y la máscara de un estudio.

    Devuelve:
        imagenes: diccionario con las cuatro modalidades.
        mascara: etiquetas de referencia como enteros.
        affine: matriz de transformación espacial.
        estudio_id: identificador del estudio.
    """
    estudio = DATASET / estudio_id

    if not estudio.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta del estudio: {estudio}"
        )

    imagenes = {}
    affine_referencia = None
    forma_referencia = None

    for modalidad in (*MODALIDADES, NOMBRE_MASCARA):
        archivo = buscar_archivo(estudio, modalidad)
        nifti = nib.load(str(archivo))

        if len(nifti.shape) != 3:
            raise ValueError(
                f"{archivo.name}: se esperaba una imagen 3D, "
                f"pero tiene dimensiones {nifti.shape}."
            )

        if forma_referencia is None:
            forma_referencia = nifti.shape
            affine_referencia = nifti.affine
        else:
            if nifti.shape != forma_referencia:
                raise ValueError(
                    f"Dimensiones incompatibles en {archivo.name}: "
                    f"{nifti.shape} frente a {forma_referencia}."
                )

            if not np.allclose(
                nifti.affine, affine_referencia, rtol=1e-5, atol=1e-5
            ):
                raise ValueError(
                    f"Geometría espacial incompatible en {archivo.name}."
                )

        datos = np.asarray(nifti.dataobj)

        if not np.isfinite(datos).all():
            raise ValueError(
                f"Se encontraron valores no finitos en {archivo.name}."
            )

        if modalidad == NOMBRE_MASCARA:
            etiquetas = np.unique(datos)

            if not np.isin(etiquetas, [0, 1, 2, 3]).all():
                raise ValueError(
                    f"Etiquetas inesperadas en la máscara: {etiquetas}."
                )

            imagenes_mascara = datos.astype(np.uint8, copy=False)
        else:
            imagenes[modalidad] = datos.astype(
                np.float32, copy=False
            )

    return {
        "estudio_id": estudio_id,
        "imagenes": imagenes,
        "mascara": imagenes_mascara,
        "affine": affine_referencia,
        "forma": forma_referencia,
    }


if __name__ == "__main__":
    estudio_prueba = "BraTS-GLI-00000-000"
    resultado = cargar_estudio(estudio_prueba)

    print("=" * 50)
    print("PRUEBA DEL CARGADOR REUTILIZABLE")
    print("=" * 50)
    print("Estudio:", resultado["estudio_id"])
    print("Dimensiones:", resultado["forma"])

    for modalidad, datos in resultado["imagenes"].items():
        print(
            f"{modalidad}: forma={datos.shape}, "
            f"tipo={datos.dtype}"
        )

    print(
        "Máscara:",
        f"forma={resultado['mascara'].shape},",
        f"tipo={resultado['mascara'].dtype}"
    )
    print(
        "Etiquetas:",
        np.unique(resultado["mascara"]).tolist()
    )
    print("Geometría compatible: sí")
    print("Prueba completada correctamente.")
