
from pathlib import Path
import pandas as pd
import ast
import re

# Rutas del proyecto
RAIZ = Path(__file__).resolve().parents[2]

RUTA_SPLIT = RAIZ / "resultados" / "particion" / "split.csv"
RUTA_MANIFEST = RAIZ / "resultados" / "manifest.csv"
RUTA_AUDITORIA = (
    RAIZ
    / "resultados"
    / "auditoria"
    / "auditoria_calidad_mascaras.csv"
)

# Cargar archivos conservando los identificadores como texto
split = pd.read_csv(RUTA_SPLIT, dtype={"group_key": str})
manifest = pd.read_csv(
    RUTA_MANIFEST,
    dtype={"subject_key": str, "sample_id": str},
)
auditoria = pd.read_csv(
    RUTA_AUDITORIA,
    dtype={"study_id": str},
)

# Comprobar que cada estudio tenga auditoría y etiquetas
cruce = manifest[["subject_key", "sample_id"]].merge(
    auditoria[["study_id", "valores_etiquetas"]],
    left_on="sample_id",
    right_on="study_id",
    how="left",
    validate="one_to_one",
    indicator=True,
)

if not cruce["_merge"].eq("both").all():
    raise ValueError("Hay estudios sin correspondencia en la auditoría.")

if cruce["valores_etiquetas"].isna().any():
    raise ValueError("Hay estudios sin etiquetas registradas.")

# Normalizar el formato de las etiquetas:
# [0, 1, 2, 3] -> [0,1,2,3]
def normalizar_etiquetas(valor):
    etiquetas = ast.literal_eval(valor)
    return "[" + ",".join(str(int(x)) for x in etiquetas) + "]"

cruce["resumen_estudio"] = cruce["valores_etiquetas"].apply(
    normalizar_etiquetas
)

# Mantener el orden de los estudios por identificador
cruce = cruce.sort_values(["subject_key", "sample_id"])

# Una fila por paciente, con las etiquetas de cada estudio separadas
resumen = (
    cruce.groupby("subject_key", sort=False)["resumen_estudio"]
    .agg("; ".join)
    .rename("label_summary")
    .reset_index()
)

# Incorporar el resumen sin modificar las asignaciones de split
actualizado = split.drop(columns=["label_summary"]).merge(
    resumen,
    left_on="group_key",
    right_on="subject_key",
    how="left",
    validate="one_to_one",
)

if actualizado["label_summary"].isna().any():
    raise ValueError("Hay grupos sin resumen de etiquetas.")

actualizado = actualizado[split.columns]

# Guardar copia de seguridad y actualizar el archivo
copia = RUTA_SPLIT.with_name("split_antes_label_summary.csv")
split.to_csv(copia, index=False, encoding="utf-8-sig")
actualizado.to_csv(RUTA_SPLIT, index=False, encoding="utf-8-sig")

print("ACTUALIZACIÓN COMPLETADA")
print("Grupos:", len(actualizado))
print("Columnas:", actualizado.columns.tolist())
print("Copia de seguridad:", copia)
print("\nEjemplos:")
print(
    actualizado[actualizado["n_samples"] == 2]
    .head(10)
    .to_string(index=False)
)
