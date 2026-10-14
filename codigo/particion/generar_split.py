
from pathlib import Path
import random
import pandas as pd


# ============================================================
# 1. RUTAS Y CONFIGURACIÓN
# ============================================================


# ============================================================
# 1. RUTAS Y CONFIGURACIÓN
# ============================================================

from pathlib import Path
import random
import pandas as pd

PROYECTO = Path(__file__).resolve().parents[2]

# El manifiesto original se conserva en resultados/
MANIFEST = PROYECTO / "resultados" / "manifest.csv"

# Todos los resultados de la partición van aquí.
CARPETA_PARTICION = PROYECTO / "resultados" / "particion"

SALIDA_SPLIT = CARPETA_PARTICION / "split.csv"
SALIDA_MANIFEST = CARPETA_PARTICION / "manifest_con_split.csv"

SEMILLA = 42

PORCENTAJES = {
    "train": 0.70,
    "validation": 0.15,
    "test": 0.15,
}



# ============================================================
# 2. CARGAR Y VALIDAR EL MANIFIESTO
# ============================================================

if not MANIFEST.exists():
    raise FileNotFoundError(
        f"No se encontró el manifiesto: {MANIFEST}"
    )

df = pd.read_csv(MANIFEST, dtype=str).fillna("")

columnas_requeridas = [
    "subject_key",
    "sample_id",
    "qc_status",
    "reference_available",
    "exclusion_reason",
    "label",
]

faltantes = [
    c for c in columnas_requeridas
    if c not in df.columns
]

if faltantes:
    raise ValueError(
        f"Faltan columnas en manifest.csv: {faltantes}"
    )

if df["subject_key"].str.strip().eq("").any():
    raise ValueError(
        "Hay estudios sin subject_key. No se puede "
        "garantizar la separación por paciente."
    )

if df["sample_id"].duplicated().any():
    raise ValueError(
        "Hay sample_id repetidos en el manifiesto."
    )

# Usar únicamente estudios válidos y sin exclusión registrada.
df["qc_status"] = df["qc_status"].str.strip().str.lower()
df["exclusion_reason"] = df["exclusion_reason"].str.strip()

df["reference_available"] = (
    df["reference_available"].str.strip().str.lower()
)

df["subject_key"] = df["subject_key"].str.strip()

estudios_validos = df[
    (df["qc_status"] == "válido")
    & (df["exclusion_reason"] == "")
].copy()

if estudios_validos.empty:
    raise ValueError(
        "No hay estudios válidos para realizar la partición."
    )

if not estudios_validos["reference_available"].eq("true").all():
    raise ValueError(
        "Hay estudios sin máscara de referencia disponible. "
        "Revísalos antes de continuar."
    )


# ============================================================
# 3. AGRUPAR LOS ESTUDIOS POR PACIENTE
# ============================================================

# Cada paciente aparece una sola vez en la lista de grupos.
pacientes = sorted(
    estudios_validos["subject_key"].unique().tolist()
)

total_pacientes = len(pacientes)

if total_pacientes < 3:
    raise ValueError(
        "Se necesitan al menos tres pacientes para crear "
        "las tres particiones."
    )


# ============================================================
# 4. ASIGNAR PACIENTES A LAS PARTICIONES
# ============================================================

# Redondear los tamaños y asegurar que sumen exactamente
# el número de pacientes disponibles.
n_train = round(total_pacientes * PORCENTAJES["train"])
n_validation = round(
    total_pacientes * PORCENTAJES["validation"]
)
n_test = total_pacientes - n_train - n_validation

if min(n_train, n_validation, n_test) < 1:
    raise ValueError(
        "Una de las particiones quedó vacía."
    )

# Aleatorización reproducible.
rng = random.Random(SEMILLA)
rng.shuffle(pacientes)

train_ids = pacientes[:n_train]
validation_ids = pacientes[
    n_train:n_train + n_validation
]
test_ids = pacientes[n_train + n_validation:]

asignacion = {}

for paciente in train_ids:
    asignacion[paciente] = "train"

for paciente in validation_ids:
    asignacion[paciente] = "validation"

for paciente in test_ids:
    asignacion[paciente] = "test"


# ============================================================
# 5. CONSTRUIR SPLIT.CSV: UNA FILA POR PACIENTE
# ============================================================

registros_split = []

for paciente in sorted(pacientes):
    estudios_paciente = estudios_validos[
        estudios_validos["subject_key"] == paciente
    ]

    etiquetas = sorted(
        estudios_paciente["label"].unique().tolist()
    )

    registros_split.append({
        "group_key": paciente,
        "split": asignacion[paciente],
        "n_samples": len(estudios_paciente),
        "label_summary": ";".join(etiquetas),
        "evidence_level": "ID_verificado",
    })

split = pd.DataFrame(registros_split)

split = split[
    [
        "group_key",
        "split",
        "n_samples",
        "label_summary",
        "evidence_level",
    ]
]


# ============================================================
# 6. COMPROBAR QUE NO HAYA PACIENTES COMPARTIDOS
# ============================================================

conjuntos = {
    nombre: set(
        split.loc[split["split"] == nombre, "group_key"]
    )
    for nombre in ["train", "validation", "test"]
}

intersecciones = {
    "train_validation": (
        conjuntos["train"] & conjuntos["validation"]
    ),
    "train_test": (
        conjuntos["train"] & conjuntos["test"]
    ),
    "validation_test": (
        conjuntos["validation"] & conjuntos["test"]
    ),
}

for nombre, interseccion in intersecciones.items():
    print(f"Intersección {nombre}: {len(interseccion)}")

    if interseccion:
        raise RuntimeError(
            f"Se encontraron pacientes compartidos en {nombre}."
        )

if len(split) != total_pacientes:
    raise RuntimeError(
        "El número de grupos no coincide con el total de pacientes."
    )


# ============================================================
# 7. CREAR MANIFIESTO CON LA PARTICIÓN ASIGNADA
# ============================================================

df_con_split = df.copy()

df_con_split["split"] = df_con_split["subject_key"].map(
    asignacion
)

# Los estudios no incluidos en la partición quedan sin asignación.
# No se les asigna un conjunto por defecto.


# ============================================================
# 8. GUARDAR RESULTADOS
# ============================================================

SALIDA_SPLIT.parent.mkdir(parents=True, exist_ok=True)

split.to_csv(
    SALIDA_SPLIT,
    index=False,
    encoding="utf-8-sig"
)

df_con_split.to_csv(
    SALIDA_MANIFEST,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 9. MOSTRAR RESUMEN
# ============================================================

print("\nPARTICIÓN GENERADA")
print(f"Semilla: {SEMILLA}")
print(f"Pacientes incluidos: {total_pacientes}")
print(f"Estudios incluidos: {len(estudios_validos)}")

print("\nResumen por partición:")

for nombre in ["train", "validation", "test"]:
    grupos = split[split["split"] == nombre]
    ids = set(grupos["group_key"])

    n_estudios = int(grupos["n_samples"].sum())

    print(
        f"{nombre}: "
        f"{len(ids)} pacientes, "
        f"{n_estudios} estudios, "
        f"{len(ids) / total_pacientes:.2%} de pacientes"
    )

print("\nComprobación de fuga por paciente:")
print("Correcta: todas las intersecciones son cero.")

print(f"\nArchivo de partición: {SALIDA_SPLIT}")
print(f"Manifiesto con partición: {SALIDA_MANIFEST}")
