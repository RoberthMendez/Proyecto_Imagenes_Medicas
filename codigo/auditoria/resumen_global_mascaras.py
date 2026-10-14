
from pathlib import Path
from ast import literal_eval
import pandas as pd

PROYECTO = Path(__file__).resolve().parents[2]

AUDITORIA = (
    PROYECTO / "resultados" / "auditoria"
    / "auditoria_calidad_mascaras.csv"
)
MANIFEST = (
    PROYECTO / "resultados" / "particion"
    / "manifest_con_split.csv"
)
SALIDA = PROYECTO / "resultados" / "auditoria"

SALIDA.mkdir(parents=True, exist_ok=True)


def interpretar_etiquetas(valor):
    """Convierte valores como '[0, 1, 2, 3]' en una lista."""
    if pd.isna(valor):
        return []

    if isinstance(valor, (list, tuple, set)):
        return sorted({int(x) for x in valor})

    texto = str(valor).strip()

    try:
        resultado = literal_eval(texto)
        if isinstance(resultado, (list, tuple, set)):
            return sorted({int(x) for x in resultado})
        return [int(resultado)]
    except (ValueError, SyntaxError, TypeError):
        # Admite representaciones simples como '0,1,2,3'.
        texto = texto.strip("[](){} ")
        if not texto:
            return []
        return sorted({int(x.strip()) for x in texto.split(",")})


# Leer archivos existentes
auditoria = pd.read_csv(AUDITORIA, dtype=str)
manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")

if "study_id" not in auditoria.columns:
    raise ValueError(
        f"No existe 'study_id' en la auditoría. "
        f"Columnas: {auditoria.columns.tolist()}"
    )

if "valores_etiquetas" not in auditoria.columns:
    raise ValueError(
        f"No existe 'valores_etiquetas'. "
        f"Columnas: {auditoria.columns.tolist()}"
    )

auditoria["etiquetas"] = auditoria[
    "valores_etiquetas"
].apply(interpretar_etiquetas)

# 1. Frecuencia de estudios que contienen cada etiqueta
frecuencias = []
total = len(auditoria)

for etiqueta in [0, 1, 2, 3]:
    cantidad = auditoria["etiquetas"].apply(
        lambda lista: etiqueta in lista
    ).sum()

    frecuencias.append({
        "etiqueta": etiqueta,
        "estudios_con_etiqueta": int(cantidad),
        "porcentaje_estudios": round(
            cantidad / total * 100, 4
        ) if total else 0
    })

resumen_etiquetas = pd.DataFrame(frecuencias)

# 2. Combinaciones de etiquetas por estudio
auditoria["combinacion"] = auditoria["etiquetas"].apply(
    lambda lista: "[" + ", ".join(map(str, lista)) + "]"
)

resumen_combinaciones = (
    auditoria.groupby("combinacion")
    .size()
    .reset_index(name="estudios")
    .sort_values("estudios", ascending=False)
)

resumen_combinaciones["porcentaje_estudios"] = (
    resumen_combinaciones["estudios"] / total * 100
).round(4)

# 3. Añadir partición mediante el identificador del estudio
# Se intenta emparejar con identificadores presentes en el manifest.
columna_id = next(
    (
        columna for columna in
        ["sample_id", "study_eye_visit_key"]
        if columna in manifest.columns
    ),
    None
)

if columna_id is None or "split" not in manifest.columns:
    raise ValueError(
        "El manifest no tiene un identificador compatible "
        "y la columna 'split'. Revisa sus columnas."
    )

mapa_split = manifest[[columna_id, "split"]].copy()
mapa_split = mapa_split.rename(
    columns={columna_id: "study_id"}
)

auditoria["study_id"] = auditoria["study_id"].astype(str)
mapa_split["study_id"] = mapa_split["study_id"].astype(str)

# Validar el emparejamiento antes de interpretar resultados
if mapa_split["study_id"].duplicated().any():
    raise ValueError(
        f"El identificador {columna_id} está duplicado en el manifest."
    )

por_particion = auditoria.merge(
    mapa_split,
    on="study_id",
    how="left",
    validate="one_to_one"
)

sin_particion = por_particion["split"].isna().sum()

if sin_particion:
    raise ValueError(
        f"{sin_particion} estudios no encontraron su partición. "
        "No se generarán resúmenes por partición hasta corregir "
        "la correspondencia de identificadores."
    )

filas = []

for particion, grupo in por_particion.groupby("split"):
    for etiqueta in [0, 1, 2, 3]:
        cantidad = grupo["etiquetas"].apply(
            lambda lista: etiqueta in lista
        ).sum()

        filas.append({
            "particion": particion,
            "etiqueta": etiqueta,
            "estudios_con_etiqueta": int(cantidad),
            "total_estudios_particion": len(grupo),
            "porcentaje_estudios": round(
                cantidad / len(grupo) * 100, 4
            )
        })

resumen_particiones = pd.DataFrame(filas)

# Guardar resultados
resumen_etiquetas.to_csv(
    SALIDA / "resumen_global_frecuencia_etiquetas.csv",
    index=False,
    encoding="utf-8-sig"
)

resumen_combinaciones.to_csv(
    SALIDA / "resumen_global_combinaciones.csv",
    index=False,
    encoding="utf-8-sig"
)

resumen_particiones.to_csv(
    SALIDA / "resumen_etiquetas_por_particion.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 60)
print("RESUMEN GLOBAL DE MÁSCARAS")
print("=" * 60)
print(f"Estudios auditados: {total}")
print("\nESTUDIOS QUE CONTIENEN CADA ETIQUETA")
print(resumen_etiquetas.to_string(index=False))
print("\nCOMBINACIONES DE ETIQUETAS")
print(resumen_combinaciones.to_string(index=False))
print("\nETIQUETAS POR PARTICIÓN")
print(resumen_particiones.to_string(index=False))
print("\nArchivos guardados en:", SALIDA)
print("Resumen finalizado.")
