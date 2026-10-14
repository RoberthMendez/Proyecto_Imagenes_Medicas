
from pathlib import Path
import pandas as pd


# ============================================================
# 1. RUTAS
# ============================================================

PROYECTO = Path(__file__).resolve().parents[2]

CARPETA_AUDITORIA = PROYECTO / "resultados" / "auditoria"
INVENTARIO = CARPETA_AUDITORIA / "inventario.csv"
AUDITORIA_MASCARAS = (
    CARPETA_AUDITORIA / "auditoria_calidad_mascaras.csv"
)

# El manifiesto definitivo va directamente en resultados/
MANIFEST = PROYECTO / "resultados" / "manifest.csv"


# ============================================================
# 2. VERIFICAR ARCHIVOS
# ============================================================

for archivo in [INVENTARIO, AUDITORIA_MASCARAS]:
    if not archivo.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {archivo}"
        )

inventario = pd.read_csv(INVENTARIO, dtype=str).fillna("")
mascaras = pd.read_csv(AUDITORIA_MASCARAS, dtype=str).fillna("")


# ============================================================
# 3. PREPARAR AUDITORÍA DE MÁSCARAS
# ============================================================

# Normalizar el identificador para evitar diferencias por espacios.
# Normalizar los identificadores.
inventario["study_id"] = inventario["study_id"].str.strip()
inventario["subject_key"] = inventario["subject_key"].str.strip()
mascaras["study_id"] = mascaras["study_id"].str.strip()

# Construir el identificador completo del estudio en el inventario.
inventario["study_id"] = (
    "BraTS-GLI-"
    + inventario["subject_key"].str.zfill(5)
    + "-"
    + inventario["study_id"].str.zfill(3)
)

# Convertir los campos de auditoría a booleanos reales.
for columna in [
    "mascara_legible",
    "geometria_compatible",
    "requiere_revision",
]:
    mascaras[columna] = (
        mascaras[columna]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )

# Comprobar que no haya identificadores repetidos en la auditoría.
duplicados = mascaras["study_id"].duplicated()

if duplicados.any():
    ids = mascaras.loc[duplicados, "study_id"].tolist()
    raise ValueError(
        f"Hay estudios repetidos en la auditoría de máscaras: {ids[:10]}"
    )

mascaras_por_estudio = mascaras.set_index("study_id").to_dict("index")


# ============================================================
# 4. CONSTRUIR MANIFIESTO
# ============================================================

modalidades = ["t1n", "t1c", "t2w", "t2f", "seg"]
registros = []

for _, fila in inventario.iterrows():

    estudio = fila["study_id"]
    paciente = fila["subject_key"]

    # Verificar que existan y sean legibles los cinco archivos.
    archivos_correctos = all(
        str(fila.get(f"{modalidad}_{campo}", ""))
        .strip().lower() == "true"
        for modalidad in modalidades
        for campo in ["exists", "readable"]
    )

    # Recuperar auditoría de este estudio.
    auditoria = mascaras_por_estudio.get(estudio)

    if auditoria is None:
        mascara_disponible = False
        calidad_mascara_correcta = False
    else:
        mascara_disponible = (
            auditoria.get("mascara_legible") is True
        )

        calidad_mascara_correcta = (
            auditoria.get("mascara_legible") is True
            and auditoria.get("geometria_compatible") is True
            and auditoria.get("requiere_revision") is False
        )

    # El estado solo es válido si los archivos y la máscara
    # pasaron las comprobaciones automáticas.
    if archivos_correctos and calidad_mascara_correcta:
        estado_calidad = "válido"
    else:
        estado_calidad = "pendiente_revision"

    registros.append({
        "subject_key": paciente,
        "sample_id": estudio,
        "study_eye_visit_key": estudio,
        "label": "tumor_segmentation",
        "reference_available": mascara_disponible,
        "qc_status": estado_calidad,
        "exclusion_reason": "",
        "duplicate_group": "",
        "split": "",
    })


# ============================================================
# 5. ORDENAR Y GUARDAR
# ============================================================

columnas = [
    "subject_key",
    "sample_id",
    "study_eye_visit_key",
    "label",
    "reference_available",
    "qc_status",
    "exclusion_reason",
    "duplicate_group",
    "split",
]

manifest = pd.DataFrame(registros, columns=columnas)

manifest = manifest.sort_values(
    ["subject_key", "sample_id"],
    kind="stable"
)

MANIFEST.parent.mkdir(parents=True, exist_ok=True)

manifest.to_csv(
    MANIFEST,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 6. RESUMEN
# ============================================================

print("\nManifest generado correctamente.")
print(f"Ubicación: {MANIFEST}")
print(f"Total de estudios: {len(manifest)}")
print(f"Pacientes únicos: {manifest['subject_key'].nunique()}")

print("\nDisponibilidad de máscaras:")
print(manifest["reference_available"].value_counts(dropna=False))

print("\nEstados de calidad:")
print(manifest["qc_status"].value_counts(dropna=False))

print("\nPrimeros diez registros:")
print(manifest.head(10).to_string(index=False))
