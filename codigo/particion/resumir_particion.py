
from pathlib import Path
import pandas as pd
import ast

# ============================================================
# 1. RUTAS DEL PROYECTO
# ============================================================

RAIZ = Path(__file__).resolve().parents[2]

RUTA_MANIFEST = (
    RAIZ / "resultados" / "particion" / "manifest_con_split.csv"
)
RUTA_INVENTARIO = (
    RAIZ / "resultados" / "auditoria" / "inventario.csv"
)
RUTA_MASCARAS = (
    RAIZ / "resultados" / "auditoria"
    / "auditoria_calidad_mascaras.csv"
)
RUTA_SALIDA = (
    RAIZ / "resultados" / "particion"
    / "resumen_conteos_particion.csv"
)

# ============================================================
# 2. CARGAR LOS RESULTADOS DE LAS AUDITORÍAS
# ============================================================

manifest = pd.read_csv(
    RUTA_MANIFEST,
    dtype={"sample_id": str, "split": str}
)

inventario = pd.read_csv(
    RUTA_INVENTARIO,
    dtype={"study_path": str}
).rename(columns={"study_path": "sample_id"})

mascaras = pd.read_csv(
    RUTA_MASCARAS,
    dtype={"study_id": str}
).rename(columns={"study_id": "sample_id"})

# ============================================================
# 3. RELACIONAR LOS ESTUDIOS Y COMPROBAR CORRESPONDENCIAS
# ============================================================


datos = manifest.merge(
    inventario.drop(columns=["subject_key"]),
    on="sample_id",
    how="left",
    validate="one_to_one",
    indicator="inventario_match"
)


datos = datos.merge(
    mascaras[
        [
            "sample_id",
            "mascara_legible",
            "valores_etiquetas",
            "requiere_revision",
        ]
    ],
    on="sample_id",
    how="left",
    validate="one_to_one",
    indicator="mascara_match"
)

if not datos["inventario_match"].eq("both").all():
    raise ValueError(
        "Hay estudios sin correspondencia en el inventario."
    )

if not datos["mascara_match"].eq("both").all():
    raise ValueError(
        "Hay estudios sin correspondencia en la auditoría."
    )

if datos["split"].isna().any():
    raise ValueError("Hay estudios sin partición asignada.")

particiones_validas = {"train", "validation", "test"}

if set(datos["split"].unique()) != particiones_validas:
    raise ValueError("Las particiones no coinciden con las esperadas.")

# ============================================================
# 4. CONTAR PACIENTES, ESTUDIOS Y ARCHIVOS
# ============================================================

modalidades = ["t1n", "t1c", "t2w", "t2f", "seg"]
filas = []

for particion in ["train", "validation", "test"]:
    grupo = datos[datos["split"] == particion].copy()

    fila = {
        "particion": particion,
        "pacientes": grupo["subject_key"].nunique(),
        "estudios": len(grupo),
        "archivos_esperados": len(grupo) * len(modalidades),
        "archivos_existentes": 0,
        "archivos_legibles": 0,
        "mascaras_legibles": int(
            grupo["mascara_legible"].fillna(False).sum()
        ),
        "mascaras_con_revision": int(
            grupo["requiere_revision"].fillna(True).sum()
        ),
    }

    for modalidad in modalidades:
        existentes = int(
            grupo[f"{modalidad}_exists"].fillna(False).sum()
        )
        legibles = int(
            grupo[f"{modalidad}_readable"].fillna(False).sum()
        )

        fila[f"{modalidad}_existentes"] = existentes
        fila[f"{modalidad}_legibles"] = legibles

        fila["archivos_existentes"] += existentes
        fila["archivos_legibles"] += legibles

    filas.append(fila)

resumen = pd.DataFrame(filas)

# ============================================================
# 5. RESUMIR LAS COMBINACIONES DE ETIQUETAS
# ============================================================

resumen_etiquetas = []

for particion in ["train", "validation", "test"]:
    grupo = datos[datos["split"] == particion]

    etiquetas = grupo["valores_etiquetas"].dropna().apply(
        lambda valor: "[" + ",".join(
            str(int(x))
            for x in ast.literal_eval(valor)
        ) + "]"
    )

    conteos = etiquetas.value_counts().sort_index()

    for combinacion, cantidad in conteos.items():
        resumen_etiquetas.append({
            "particion": particion,
            "combinacion_etiquetas": combinacion,
            "estudios": int(cantidad),
        })

tabla_etiquetas = pd.DataFrame(resumen_etiquetas)

# ============================================================
# 6. GUARDAR Y MOSTRAR LOS RESULTADOS
# ============================================================

RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)

resumen.to_csv(
    RUTA_SALIDA,
    index=False,
    encoding="utf-8-sig"
)

RUTA_ETIQUETAS = (
    RAIZ / "resultados" / "particion"
    / "resumen_etiquetas_particion.csv"
)

tabla_etiquetas.to_csv(
    RUTA_ETIQUETAS,
    index=False,
    encoding="utf-8-sig"
)

print("\n=== RESUMEN POR PARTICIÓN ===")
print(resumen.to_string(index=False))

print("\n=== COMBINACIONES DE ETIQUETAS ===")
print(tabla_etiquetas.to_string(index=False))

print("\nArchivos generados:")
print(RUTA_SALIDA)
print(RUTA_ETIQUETAS)

print("\nLa partición original no fue modificada.")
