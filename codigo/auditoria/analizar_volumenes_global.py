
from pathlib import Path
import gc

import nibabel as nib
import numpy as np
import pandas as pd


PROYECTO = Path(__file__).resolve().parents[2]
DATASET = PROYECTO / "datos" / "BraTS2023-GLI-Dataset"
SALIDA = PROYECTO / "resultados" / "auditoria"

SALIDA.mkdir(parents=True, exist_ok=True)

ETIQUETAS = [1, 2, 3]


def buscar_mascara(estudio):
    archivos = sorted(estudio.glob("*seg.nii*"))

    if len(archivos) != 1:
        raise FileNotFoundError(
            f"{estudio.name}: se esperaba una máscara y "
            f"se encontraron {len(archivos)}."
        )

    return archivos[0]


def analizar_mascara(archivo):
    imagen = nib.load(str(archivo))
    datos = np.asanyarray(imagen.dataobj)

    if not np.isfinite(datos).all():
        raise ValueError(
            f"Valores no finitos en {archivo.name}"
        )

    etiquetas_encontradas = np.unique(datos)

    if not np.isin(etiquetas_encontradas, [0, 1, 2, 3]).all():
        raise ValueError(
            f"Etiquetas inesperadas en {archivo.name}: "
            f"{etiquetas_encontradas.tolist()}"
        )

    total = datos.size
    conteos = {
        etiqueta: int(np.count_nonzero(datos == etiqueta))
        for etiqueta in ETIQUETAS
    }

    no_fondo = int(np.count_nonzero(datos != 0))

    resultado = {
        "sample_id": archivo.name.replace("-seg.nii.gz", "")
                                 .replace("-seg.nii", ""),
        "total_voxeles": int(total),
        "voxeles_fondo": int(np.count_nonzero(datos == 0)),
        "voxeles_no_fondo": no_fondo,
        "porcentaje_no_fondo": no_fondo / total * 100,
        "combinacion_etiquetas": str(
            etiquetas_encontradas.astype(int).tolist()
        ),
    }

    for etiqueta in ETIQUETAS:
        cantidad = conteos[etiqueta]
        resultado[f"voxeles_etiqueta_{etiqueta}"] = cantidad
        resultado[f"porcentaje_etiqueta_{etiqueta}"] = (
            cantidad / total * 100
        )

    return resultado


estudios = sorted(
    carpeta for carpeta in DATASET.iterdir()
    if carpeta.is_dir() and carpeta.name.startswith("BraTS-GLI-")
)

if not estudios:
    raise FileNotFoundError(
        f"No se encontraron estudios en {DATASET}"
    )

resultados = []
errores = []

print(f"Estudios encontrados: {len(estudios)}")
print("Analizando las máscaras una por una...\n")

for i, estudio in enumerate(estudios, start=1):
    try:
        mascara = buscar_mascara(estudio)
        fila = analizar_mascara(mascara)
        fila["study_id"] = estudio.name
        resultados.append(fila)

    except Exception as error:
        errores.append({
            "study_id": estudio.name,
            "error": str(error)
        })

    if i % 100 == 0 or i == len(estudios):
        print(f"Procesados: {i}/{len(estudios)}")

    # Evitar conservar datos de una máscara en memoria.
    gc.collect()


detalle = pd.DataFrame(resultados)

ruta_detalle = SALIDA / "volumenes_por_estudio.csv"
detalle.to_csv(ruta_detalle, index=False, encoding="utf-8-sig")

if errores:
    pd.DataFrame(errores).to_csv(
        SALIDA / "errores_analisis_volumenes.csv",
        index=False,
        encoding="utf-8-sig"
    )

if detalle.empty:
    raise RuntimeError(
        "No se pudo analizar ninguna máscara. "
        "Revisa errores_analisis_volumenes.csv."
    )

columnas_resumen = [
    "voxeles_no_fondo",
    "porcentaje_no_fondo",
    "voxeles_etiqueta_1",
    "porcentaje_etiqueta_1",
    "voxeles_etiqueta_2",
    "porcentaje_etiqueta_2",
    "voxeles_etiqueta_3",
    "porcentaje_etiqueta_3",
]

resumen = detalle[columnas_resumen].describe(
    percentiles=[0.10, 0.25, 0.50, 0.75, 0.90]
).T

resumen.to_csv(
    SALIDA / "resumen_global_volumenes.csv",
    encoding="utf-8-sig"
)

print("\n" + "=" * 65)
print("RESUMEN GLOBAL DE VOLÚMENES")
print("=" * 65)
print(f"Máscaras analizadas: {len(detalle)}")
print(f"Errores: {len(errores)}")
print("\nEstadísticas descriptivas:")
print(resumen.round(4).to_string())

print("\nArchivos generados:")
print(ruta_detalle)
print(SALIDA / "resumen_global_volumenes.csv")

if errores:
    print(SALIDA / "errores_analisis_volumenes.csv")

print("\nAnálisis finalizado.")
