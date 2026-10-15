from pathlib import Path
import csv

import nibabel as nib
import numpy as np


PROYECTO = Path(__file__).resolve().parents[2]
BASE = PROYECTO / "datos" / "BraTS2023-GLI-Dataset"
CARPETA_SALIDA = PROYECTO / "resultados" / "auditoria"
SALIDA_INVENTARIO = CARPETA_SALIDA / "inventario.csv"
SALIDA_MASCARAS = CARPETA_SALIDA / "auditoria_calidad_mascaras.csv"

SECUENCIAS = ("t1n", "t1c", "t2w", "t2f", "seg")
COLUMNAS_INVENTARIO = [
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
MODALIDADES = ("t1n", "t1c", "t2w", "t2f")
ETIQUETAS_ESPERADAS = {0, 1, 2, 3}


def inventariar_estudio(estudio):
    """Comprueba por separado la existencia y lectura de cada archivo."""
    partes = estudio.name.split("-")
    fila = {
        "subject_key": partes[2],
        "study_id": partes[3],
        "study_path": estudio.name,
    }
    imagenes_cargadas = {}

    for secuencia in SECUENCIAS:
        archivo = estudio / f"{estudio.name}-{secuencia}.nii.gz"
        existe = archivo.is_file()
        legible = False

        if existe:
            try:
                imagen = nib.load(str(archivo))
                _ = imagen.shape
                imagenes_cargadas[secuencia] = imagen
                legible = True
            except Exception:
                legible = False

        fila[f"{secuencia}_exists"] = existe
        fila[f"{secuencia}_readable"] = legible

    return fila, imagenes_cargadas


def cargar_imagen(ruta, modalidad, imagenes_cargadas):
    """Reutiliza el NIfTI ya abierto y carga sus datos de vóxeles."""
    imagen = imagenes_cargadas.get(modalidad)

    if imagen is None:
        imagen = nib.load(str(ruta))
        imagenes_cargadas[modalidad] = imagen

    return imagen, imagen.get_fdata()


def revisar_estudio(estudio, imagenes_cargadas):
    nombre = estudio.name
    ruta_mascara = estudio / f"{nombre}-seg.nii.gz"

    resultado = {
        "study_id": nombre,
        "mascara_legible": False,
        "dimensiones_mascara": "",
        # None indica que no hay datos suficientes para comprobarla.
        "geometria_compatible": None,
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
        mascara_img, mascara = cargar_imagen(
            ruta_mascara, "seg", imagenes_cargadas
        )
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
    geometria_comprobada = True
    geometria_incompatible = False

    for modalidad in MODALIDADES:
        ruta = estudio / f"{nombre}-{modalidad}.nii.gz"

        try:
            imagen, _ = cargar_imagen(ruta, modalidad, imagenes_cargadas)
        except Exception as error:
            geometria_comprobada = False
            modalidades_problema.append(
                f"{modalidad}: error de lectura ({type(error).__name__})"
            )
            continue

        if imagen.shape != mascara_img.shape:
            geometria_incompatible = True
            modalidades_problema.append(
                f"{modalidad}: dimensiones diferentes"
            )
            continue

        try:
            geometria_modalidad_compatible = np.allclose(
                imagen.affine,
                mascara_img.affine,
                rtol=0,
                atol=1e-3,
            )
        except Exception as error:
            geometria_comprobada = False
            modalidades_problema.append(
                f"{modalidad}: geometría no comprobable ({type(error).__name__})"
            )
            continue

        if not geometria_modalidad_compatible:
            geometria_incompatible = True
            modalidades_problema.append(
                f"{modalidad}: geometría diferente"
            )

    if geometria_incompatible:
        resultado["geometria_compatible"] = False
    elif geometria_comprobada:
        resultado["geometria_compatible"] = True

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
        carpeta
        for carpeta in BASE.iterdir()
        if carpeta.is_dir()
        and carpeta.name.startswith("BraTS-GLI-")
        and len(carpeta.name.split("-")) == 4
    )

    inventario = []
    auditoria_mascaras = []

    for indice, estudio in enumerate(estudios, start=1):
        fila_inventario, imagenes_cargadas = inventariar_estudio(estudio)
        inventario.append(fila_inventario)
        auditoria_mascaras.append(
            revisar_estudio(estudio, imagenes_cargadas)
        )

        if indice % 100 == 0 or indice == len(estudios):
            print(f"Estudios revisados: {indice}/{len(estudios)}")

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    with SALIDA_INVENTARIO.open(
        "w", newline="", encoding="utf-8-sig"
    ) as archivo:
        escritor = csv.DictWriter(
            archivo, fieldnames=COLUMNAS_INVENTARIO
        )
        escritor.writeheader()
        escritor.writerows(inventario)

    columnas_mascaras = list(auditoria_mascaras[0].keys())
    with SALIDA_MASCARAS.open(
        "w", newline="", encoding="utf-8-sig"
    ) as archivo:
        escritor = csv.DictWriter(
            archivo, fieldnames=columnas_mascaras
        )
        escritor.writeheader()
        escritor.writerows(auditoria_mascaras)

    con_hallazgos = sum(
        fila["requiere_revision"] for fila in auditoria_mascaras
    )
    pacientes = {fila["subject_key"] for fila in inventario}

    print("\nAUDITORÍA DE ESTUDIOS TERMINADA")
    print(f"Estudios encontrados: {len(inventario)}")
    print(f"Pacientes distintos: {len(pacientes)}")
    print(f"Estudios que requieren revisión: {con_hallazgos}")
    print(f"Inventario: {SALIDA_INVENTARIO}")
    print(f"Calidad de máscaras: {SALIDA_MASCARAS}")


if __name__ == "__main__":
    main()
