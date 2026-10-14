
from pathlib import Path
from collections import defaultdict
import csv
import hashlib

# Rutas del proyecto
PROYECTO = Path(__file__).resolve().parent.parent.parent
BASE = PROYECTO / "datos" / "BraTS2023-GLI-Dataset"
SALIDA = PROYECTO / "resultados/auditoria"

MODALIDADES = ["t1n", "t1c", "t2w", "t2f", "seg"]


def calcular_sha256(ruta):
    """Calcula la huella digital exacta del archivo."""
    sha256 = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha256.update(bloque)

    return sha256.hexdigest()


def guardar_csv(ruta, columnas, filas):
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def main():
    if not BASE.is_dir():
        raise FileNotFoundError(
            f"No se encontró la carpeta del dataset: {BASE}"
        )

    SALIDA.mkdir(parents=True, exist_ok=True)

    estudios = sorted(
        carpeta
        for carpeta in BASE.iterdir()
        if carpeta.is_dir()
        and carpeta.name.startswith("BraTS-GLI-")
        and len(carpeta.name.split("-")) == 4
    )

    # Huellas digitales agrupadas por modalidad
    archivos_por_hash = defaultdict(list)

    # Huellas de los cinco archivos para cada estudio
    huellas_por_estudio = {}
    pacientes_por_estudio = {}

    archivos_revisados = 0
    archivos_faltantes = []

    for indice, estudio in enumerate(estudios, start=1):
        partes = estudio.name.split("-")
        paciente = partes[2]

        huellas_estudio = {}
        pacientes_por_estudio[estudio.name] = paciente

        for modalidad in MODALIDADES:
            archivo = estudio / f"{estudio.name}-{modalidad}.nii.gz"

            if not archivo.is_file():
                archivos_faltantes.append({
                    "study_id": estudio.name,
                    "subject_key": paciente,
                    "modalidad": modalidad,
                    "archivo_esperado": archivo.name,
                })
                continue

            huella = calcular_sha256(archivo)
            archivos_revisados += 1
            huellas_estudio[modalidad] = huella

            archivos_por_hash[(modalidad, huella)].append({
                "study_id": estudio.name,
                "subject_key": paciente,
                "archivo": archivo.name,
                "ruta_relativa": str(archivo.relative_to(PROYECTO)),
            })

        if len(huellas_estudio) == len(MODALIDADES):
            huellas_por_estudio[estudio.name] = tuple(
                huellas_estudio[m] for m in MODALIDADES
            )

        if indice % 100 == 0 or indice == len(estudios):
            print(f"Estudios procesados: {indice}/{len(estudios)}")

    # 1. Archivos idénticos dentro de una misma modalidad
    filas_archivos = []
    grupo_archivo = 0

    for (modalidad, huella), elementos in archivos_por_hash.items():
        if len(elementos) > 1:
            grupo_archivo += 1

            for elemento in elementos:
                filas_archivos.append({
                    "grupo_duplicado": f"ARCH-{grupo_archivo:04d}",
                    "modalidad": modalidad,
                    "sha256": huella,
                    **elemento,
                    "cantidad_archivos_identicos": len(elementos),
                })

    guardar_csv(
        SALIDA / "reporte_archivos_identicos.csv",
        [
            "grupo_duplicado",
            "modalidad",
            "sha256",
            "study_id",
            "subject_key",
            "archivo",
            "ruta_relativa",
            "cantidad_archivos_identicos",
        ],
        filas_archivos,
    )

    # 2. Estudios con los cinco archivos idénticos
    estudios_por_huella = defaultdict(list)

    for estudio, huellas in huellas_por_estudio.items():
        estudios_por_huella[huellas].append(estudio)

    filas_estudios = []
    grupo_estudio = 0

    for huellas, nombres in estudios_por_huella.items():
        if len(nombres) > 1:
            grupo_estudio += 1

            for nombre in nombres:
                filas_estudios.append({
                    "grupo_duplicado": f"EST-{grupo_estudio:04d}",
                    "study_id": nombre,
                    "subject_key": pacientes_por_estudio[nombre],
                    "estudios_con_los_cinco_archivos_identicos": len(nombres),
                })

    guardar_csv(
        SALIDA / "reporte_estudios_identicos.csv",
        [
            "grupo_duplicado",
            "study_id",
            "subject_key",
            "estudios_con_los_cinco_archivos_identicos",
        ],
        filas_estudios,
    )

    # 3. Pacientes con varios estudios: no implica duplicación
    estudios_por_paciente = defaultdict(list)

    for estudio in estudios:
        paciente = estudio.name.split("-")[2]
        estudios_por_paciente[paciente].append(estudio.name)

    filas_pacientes = []

    for paciente, nombres in sorted(estudios_por_paciente.items()):
        if len(nombres) > 1:
            for nombre in nombres:
                filas_pacientes.append({
                    "subject_key": paciente,
                    "study_id": nombre,
                    "cantidad_estudios_del_paciente": len(nombres),
                })

    guardar_csv(
        SALIDA / "reporte_pacientes_mult_estudio.csv",
        [
            "subject_key",
            "study_id",
            "cantidad_estudios_del_paciente",
        ],
        filas_pacientes,
    )

    # 4. Archivos que faltaron durante el análisis
    guardar_csv(
        SALIDA / "reporte_archivos_faltantes.csv",
        [
            "study_id",
            "subject_key",
            "modalidad",
            "archivo_esperado",
        ],
        archivos_faltantes,
    )

    print("\nREPORTE TERMINADO")
    print(f"Estudios encontrados: {len(estudios)}")
    print(f"Archivos analizados: {archivos_revisados}")
    print(f"Grupos de archivos idénticos: {grupo_archivo}")
    print(f"Grupos de estudios completamente idénticos: {grupo_estudio}")
    print(f"Pacientes con varios estudios: {sum(len(v) > 1 for v in estudios_por_paciente.values())}")
    print(f"Archivos faltantes durante el análisis: {len(archivos_faltantes)}")
    print(f"Reportes guardados en: {SALIDA}")


if __name__ == "__main__":
    main()
