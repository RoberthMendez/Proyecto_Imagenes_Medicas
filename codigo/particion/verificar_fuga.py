
from pathlib import Path
import pandas as pd
from itertools import combinations

# ============================================================
# 1. RUTAS
# ============================================================

RAIZ = Path(__file__).resolve().parents[2]

RUTA_SPLIT = (
    RAIZ / "resultados" / "particion" / "split.csv"
)

CARPETA_SALIDA = (
    RAIZ / "resultados" / "particion"
)

RUTA_INTERSECCIONES = (
    CARPETA_SALIDA / "reporte_intersecciones_particiones.csv"
)

RUTA_RESUMEN = (
    CARPETA_SALIDA / "reporte_verificacion_no_solapamiento.csv"
)

# ============================================================
# 2. CARGAR Y VALIDAR EL SPLIT
# ============================================================

if not RUTA_SPLIT.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {RUTA_SPLIT}"
    )

split = pd.read_csv(
    RUTA_SPLIT,
    dtype={"group_key": str, "split": str}
)

columnas_requeridas = {
    "group_key", "split", "n_samples",
    "label_summary", "evidence_level"
}

faltantes = columnas_requeridas - set(split.columns)

if faltantes:
    raise ValueError(
        f"Faltan columnas requeridas: {sorted(faltantes)}"
    )

if split["group_key"].isna().any():
    raise ValueError("Hay grupos sin identificador.")

if split["split"].isna().any():
    raise ValueError("Hay grupos sin partición.")

if split["group_key"].duplicated().any():
    raise ValueError(
        "Hay group_key repetidos en split.csv."
    )

particiones = ["train", "validation", "test"]

if set(split["split"].unique()) != set(particiones):
    raise ValueError(
        "Las particiones no coinciden con train, validation y test."
    )

# ============================================================
# 3. COMPROBAR INTERSECCIONES ENTRE PARTICIONES
# ============================================================

grupos = {
    particion: set(
        split.loc[split["split"] == particion, "group_key"]
    )
    for particion in particiones
}

filas = []

for a, b in combinations(particiones, 2):
    interseccion = sorted(grupos[a] & grupos[b])

    filas.append({
        "particion_a": a,
        "particion_b": b,
        "n_grupos_a": len(grupos[a]),
        "n_grupos_b": len(grupos[b]),
        "n_grupos_compartidos": len(interseccion),
        "grupos_compartidos": "; ".join(interseccion),
        "resultado": (
            "CORRECTO" if len(interseccion) == 0
            else "FUGA_DETECTADA"
        ),
    })

reporte = pd.DataFrame(filas)

# ============================================================
# 4. RESUMEN GLOBAL Y GUARDADO DE EVIDENCIAS
# ============================================================

CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

reporte.to_csv(
    RUTA_INTERSECCIONES,
    index=False,
    encoding="utf-8-sig"
)

sin_solapamiento = (
    reporte["n_grupos_compartidos"].eq(0).all()
)

resumen = pd.DataFrame([{
    "grupos_totales": split["group_key"].nunique(),
    "grupos_train": len(grupos["train"]),
    "grupos_validation": len(grupos["validation"]),
    "grupos_test": len(grupos["test"]),
    "intersecciones_evaluadas": len(reporte),
    "todas_las_intersecciones_vacias": sin_solapamiento,
    "resultado_global": (
        "CORRECTO" if sin_solapamiento
        else "REVISAR_SOLAPAMIENTO"
    ),
}])

resumen.to_csv(
    RUTA_RESUMEN,
    index=False,
    encoding="utf-8-sig"
)

print("\n=== INTERSECCIONES ENTRE PARTICIONES ===")
print(reporte.to_string(index=False))

print("\n=== RESUMEN GLOBAL ===")
print(resumen.to_string(index=False))

print("\nReportes guardados:")
print(RUTA_INTERSECCIONES)
print(RUTA_RESUMEN)

if not sin_solapamiento:
    raise SystemExit(
        "ERROR: se detectaron grupos compartidos entre particiones."
    )

print("\nVERIFICACIÓN COMPLETADA: no hay group_key compartidos.")
