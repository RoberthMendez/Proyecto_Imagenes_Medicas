from pathlib import Path
import ast
import random

import pandas as pd


RAIZ = Path(__file__).resolve().parents[2]
RUTA_MANIFEST = RAIZ / "resultados" / "manifest.csv"
RUTA_AUDITORIA = (
    RAIZ
    / "resultados"
    / "auditoria"
    / "auditoria_calidad_mascaras.csv"
)
CARPETA_PARTICION = RAIZ / "resultados" / "particion"
RUTA_SPLIT = CARPETA_PARTICION / "split.csv"
RUTA_COPIA_PREVIA = (
    CARPETA_PARTICION / "split_antes_label_summary.csv"
)
RUTA_MANIFEST_CON_SPLIT = (
    CARPETA_PARTICION / "manifest_con_split.csv"
)

SEMILLA = 42
PORCENTAJES = {
    "train": 0.70,
    "validation": 0.15,
    "test": 0.15,
}
PARTICIONES = ("train", "validation", "test")


def crear_split_provisional(manifest):
    columnas_requeridas = [
        "subject_key",
        "sample_id",
        "qc_status",
        "reference_available",
        "exclusion_reason",
        "label",
    ]
    faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in manifest.columns
    ]

    if faltantes:
        raise ValueError(f"Faltan columnas en manifest.csv: {faltantes}")

    if manifest["subject_key"].str.strip().eq("").any():
        raise ValueError(
            "Hay estudios sin subject_key. No se puede garantizar "
            "la separación por paciente."
        )

    if manifest["sample_id"].duplicated().any():
        raise ValueError("Hay sample_id repetidos en el manifiesto.")

    manifest["qc_status"] = manifest["qc_status"].str.strip().str.lower()
    manifest["exclusion_reason"] = manifest["exclusion_reason"].str.strip()
    manifest["reference_available"] = (
        manifest["reference_available"].str.strip().str.lower()
    )
    manifest["subject_key"] = manifest["subject_key"].str.strip()

    estudios_validos = manifest[
        (manifest["qc_status"] == "válido")
        & (manifest["exclusion_reason"] == "")
    ].copy()

    if estudios_validos.empty:
        raise ValueError("No hay estudios válidos para realizar la partición.")

    if not estudios_validos["reference_available"].eq("true").all():
        raise ValueError(
            "Hay estudios sin máscara de referencia disponible. "
            "Revísalos antes de continuar."
        )

    pacientes = sorted(estudios_validos["subject_key"].unique().tolist())
    total_pacientes = len(pacientes)

    if total_pacientes < 3:
        raise ValueError(
            "Se necesitan al menos tres pacientes para crear "
            "las tres particiones."
        )

    n_train = round(total_pacientes * PORCENTAJES["train"])
    n_validation = round(
        total_pacientes * PORCENTAJES["validation"]
    )
    n_test = total_pacientes - n_train - n_validation

    if min(n_train, n_validation, n_test) < 1:
        raise ValueError("Una de las particiones quedó vacía.")

    generador = random.Random(SEMILLA)
    generador.shuffle(pacientes)

    train_ids = pacientes[:n_train]
    validation_ids = pacientes[n_train:n_train + n_validation]
    test_ids = pacientes[n_train + n_validation:]

    asignacion = {}
    for paciente in train_ids:
        asignacion[paciente] = "train"
    for paciente in validation_ids:
        asignacion[paciente] = "validation"
    for paciente in test_ids:
        asignacion[paciente] = "test"

    registros = []
    for paciente in sorted(pacientes):
        estudios_paciente = estudios_validos[
            estudios_validos["subject_key"] == paciente
        ]
        etiquetas = sorted(
            estudios_paciente["label"].unique().tolist()
        )
        registros.append({
            "group_key": paciente,
            "split": asignacion[paciente],
            "n_samples": len(estudios_paciente),
            "label_summary": ";".join(etiquetas),
            "evidence_level": "ID_verificado",
        })

    split_provisional = pd.DataFrame(
        registros,
        columns=[
            "group_key",
            "split",
            "n_samples",
            "label_summary",
            "evidence_level",
        ],
    )

    conjuntos = {
        nombre: set(
            split_provisional.loc[
                split_provisional["split"] == nombre, "group_key"
            ]
        )
        for nombre in PARTICIONES
    }
    for nombre, a, b in (
        ("train_validation", "train", "validation"),
        ("train_test", "train", "test"),
        ("validation_test", "validation", "test"),
    ):
        interseccion = conjuntos[a] & conjuntos[b]
        print(f"Intersección {nombre}: {len(interseccion)}")
        if interseccion:
            raise RuntimeError(
                f"Se encontraron pacientes compartidos en {nombre}."
            )

    if len(split_provisional) != total_pacientes:
        raise RuntimeError(
            "El número de grupos no coincide con el total de pacientes."
        )

    manifest_con_split = manifest.copy()
    manifest_con_split["split"] = manifest_con_split[
        "subject_key"
    ].map(asignacion)

    return split_provisional, manifest_con_split, total_pacientes


def agregar_resumen_etiquetas(split, manifest, auditoria):
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

    def normalizar_etiquetas(valor):
        etiquetas = ast.literal_eval(valor)
        return "[" + ",".join(str(int(x)) for x in etiquetas) + "]"

    cruce["resumen_estudio"] = cruce["valores_etiquetas"].apply(
        normalizar_etiquetas
    )
    cruce = cruce.sort_values(["subject_key", "sample_id"])

    resumen = (
        cruce.groupby("subject_key", sort=False)["resumen_estudio"]
        .agg("; ".join)
        .rename("label_summary")
        .reset_index()
    )

    actualizado = split.drop(columns=["label_summary"]).merge(
        resumen,
        left_on="group_key",
        right_on="subject_key",
        how="left",
        validate="one_to_one",
    )

    if actualizado["label_summary"].isna().any():
        raise ValueError("Hay grupos sin resumen de etiquetas.")

    return actualizado[split.columns]


def guardar_copia_provisional(split):
    """Crea la evidencia intermedia sin sobrescribir una copia previa."""
    try:
        with RUTA_COPIA_PREVIA.open(
            "x", newline="", encoding="utf-8-sig"
        ) as archivo:
            split.to_csv(archivo, index=False)
    except FileExistsError as error:
        raise FileExistsError(
            f"Ya existe la evidencia y no se sobrescribirá: "
            f"{RUTA_COPIA_PREVIA}. Revísala o consérvala fuera antes "
            "de volver a crear la partición."
        ) from error


def comprobar_salidas_libres():
    existentes = [
        ruta
        for ruta in (
            RUTA_SPLIT,
            RUTA_MANIFEST_CON_SPLIT,
            RUTA_COPIA_PREVIA,
        )
        if ruta.exists()
    ]
    if existentes:
        rutas = "\n".join(str(ruta) for ruta in existentes)
        raise FileExistsError(
            "No se sobrescribirán archivos de partición existentes. "
            "Consérvalos fuera de esta carpeta antes de regenerar:\n"
            + rutas
        )


def main():
    if not RUTA_MANIFEST.is_file():
        raise FileNotFoundError(f"No se encontró el manifiesto: {RUTA_MANIFEST}")
    if not RUTA_AUDITORIA.is_file():
        raise FileNotFoundError(f"No se encontró la auditoría: {RUTA_AUDITORIA}")
    comprobar_salidas_libres()

    manifest = pd.read_csv(RUTA_MANIFEST, dtype=str).fillna("")
    manifest_para_etiquetas = pd.read_csv(
        RUTA_MANIFEST,
        dtype={"subject_key": str, "sample_id": str},
    )
    auditoria = pd.read_csv(
        RUTA_AUDITORIA,
        dtype={"study_id": str},
    )

    split_provisional, manifest_con_split, total_pacientes = (
        crear_split_provisional(manifest)
    )
    split_final = agregar_resumen_etiquetas(
        split_provisional, manifest_para_etiquetas, auditoria
    )

    CARPETA_PARTICION.mkdir(parents=True, exist_ok=True)
    guardar_copia_provisional(split_provisional)
    split_final.to_csv(RUTA_SPLIT, index=False, encoding="utf-8-sig")
    manifest_con_split.to_csv(
        RUTA_MANIFEST_CON_SPLIT,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nPARTICIÓN GENERADA")
    print(f"Semilla: {SEMILLA}")
    print(f"Pacientes incluidos: {total_pacientes}")
    print("\nResumen por partición:")

    for nombre in PARTICIONES:
        grupos = split_final[split_final["split"] == nombre]
        pacientes_split = set(grupos["group_key"])
        estudios = int(grupos["n_samples"].sum())
        print(
            f"{nombre}: {len(pacientes_split)} pacientes, "
            f"{estudios} estudios, "
            f"{len(pacientes_split) / total_pacientes:.2%} de pacientes"
        )

    print("\nResumen de etiquetas calculado desde la auditoría de máscaras.")
    print(f"Copia del split provisional: {RUTA_COPIA_PREVIA}")
    print(f"Archivo de partición: {RUTA_SPLIT}")
    print(f"Manifiesto con partición: {RUTA_MANIFEST_CON_SPLIT}")


if __name__ == "__main__":
    main()
