
from pathlib import Path
import csv
import numpy as np
import nibabel as nib

PROYECTO = Path(__file__).resolve().parent.parent.parent
BASE = PROYECTO / "datos" / "BraTS2023-GLI-Dataset"
SALIDA = PROYECTO / "resultados/auditoria" / "auditoria_calidad_mascaras.csv"

MODALIDADES = ["t1n", "t1c", "t2w", "t2f"]
ETIQUETAS_ESPERADAS = {0, 1, 2, 3}


def cargar_imagen(ruta):
    imagen = nib.load(str(ruta))
    datos = imagen.get_fdata()
    return imagen, datos


def revisar_estudio(estudio):
    nombre = estudio.name
    mask_path = estudio / f"{nombre}-seg.nii.gz"

    resultado = {
        "study_id": nombre,
        "mascara_legible": False,
        "dimensiones_mascara": "",
        "geometria_compatible": True,
        "modalidades_con_problemas": "",
        "valores_etiquetas": "",
        "etiquetas_inesperadas": "",
        "voxeles_fondo": "",
        "voxeles_tumor": "",
        "voxeles_por_etiqueta": "",
        "hallazgos": "",
        "requiere_revision": False,
    }

    hallazgos = []

    try:
        mascara_img, mascara = cargar_imagen(mask_path)
        resultado["mascara_legible"] = True
    except Exception as error:
        resultado["hallazgos"] = f"No se pudo leer la máscara: {error}"
        resultado["requiere_revision"] = True
        return resultado

    resultado["dimensiones_mascara"] = str(mascara.shape)

    if not np.isfinite(mascara).all():
        hallazgos.append("Máscara con valores no finitos")

    valores, conteos = np.unique(mascara, return_counts=True)
    valores_enteros = set()

    for valor in valores:
        if not float(valor).is_integer():
            hallazgos.append("Máscara con etiquetas no enteras")
            continue
        valores_enteros.add(int(valor))

    resultado["valores_etiquetas"] = str(sorted(valores_enteros))

    inesperadas = valores_enteros - ETIQUETAS_ESPERADAS
    resultado["etiquetas_inesperadas"] = str(sorted(inesperadas))

    if inesperadas:
        hallazgos.append("Hay etiquetas fuera del conjunto esperado {0,1,2,3}")

    resultado["voxeles_fondo"] = int(np.count_nonzero(mascara == 0))
    resultado["voxeles_tumor"] = int(np.count_nonzero(mascara != 0))

    resultado["voxeles_por_etiqueta"] = "; ".join(
        f"{int(valor)}:{int(conteo)}"
        for valor, conteo in zip(valores, conteos)
    )

    if resultado["voxeles_tumor"] == 0:
        hallazgos.append("Máscara sin vóxeles etiquetados como tumor")

    modalidades_problema = []

    for modalidad in MODALIDADES:
        ruta = estudio / f"{nombre}-{modalidad}.nii.gz"

        try:
            imagen = nib.load(str(ruta))
            _ = imagen.get_fdata()

            if imagen.shape != mascara_img.shape:
                modalidades_problema.append(
                    f"{modalidad}: dimensiones diferentes"
                )
                continue

            if not np.allclose(
                imagen.affine, mascara_img.affine,
                rtol=0, atol=1e-3
            ):
                modalidades_problema.append(
                    f"{modalidad}: geometría diferente"
                )

        except Exception as error:
            modalidades_problema.append(
                f"{modalidad}: error de lectura ({type(error).__name__})"
            )

    resultado["modalidades_con_problemas"] = "; ".join(
        modalidades_problema
    )

    if modalidades_problema:
        hallazgos.append("Problemas de correspondencia con las MRI")

    resultado["hallazgos"] = "; ".join(hallazgos)
    resultado["requiere_revision"] = bool(hallazgos)

    return resultado


def main():
    if not BASE.is_dir():
        raise FileNotFoundError(f"No se encuentra el dataset: {BASE}")

    estudios = sorted(
        carpeta for carpeta in BASE.iterdir()
        if carpeta.is_dir()
        and carpeta.name.startswith("BraTS-GLI-")
        and len(carpeta.name.split("-")) == 4
    )

    filas = []

    for indice, estudio in enumerate(estudios, start=1):
        filas.append(revisar_estudio(estudio))

        if indice % 100 == 0 or indice == len(estudios):
            print(f"Estudios revisados: {indice}/{len(estudios)}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)

    with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=list(filas[0].keys())
        )
        escritor.writeheader()
        escritor.writerows(filas)

    con_hallazgos = sum(f["requiere_revision"] for f in filas)

    print("\nAUDITORÍA TERMINADA")
    print(f"Estudios revisados: {len(filas)}")
    print(f"Estudios que requieren revisión: {con_hallazgos}")
    print(f"Sin hallazgos automáticos: {len(filas) - con_hallazgos}")
    print(f"Reporte: {SALIDA}")


if __name__ == "__main__":
    main()
