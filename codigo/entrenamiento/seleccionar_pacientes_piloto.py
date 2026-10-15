import argparse
from pathlib import Path

import pandas as pd


SEMILLA = 42
FRACCION = 0.30


PROYECTO = Path(__file__).resolve().parents[2]
MANIFEST = PROYECTO / "resultados" / "particion" / "manifest_con_split.csv"
SALIDA = PROYECTO / "resultados" / "modelo_piloto" / "manifest_piloto_30.csv"


def obtener_ruta_salida():
    parser = argparse.ArgumentParser(
        description="Selecciona pacientes para el piloto de segmentación."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=SALIDA,
        metavar="RUTA",
        help=(
            "Ruta del manifiesto de salida. Las rutas relativas se "
            "interpretan desde la raíz del proyecto."
        ),
    )
    argumentos = parser.parse_args()

    ruta = argumentos.salida
    if not ruta.is_absolute():
        ruta = PROYECTO / ruta
    return ruta.resolve()


def escribir_sin_sobrescribir(piloto, ruta_salida):
    try:
        with ruta_salida.open(
            "x", newline="", encoding="utf-8"
        ) as archivo:
            piloto.to_csv(archivo, index=False)
    except FileExistsError as error:
        raise FileExistsError(
            "El archivo de salida ya existe y no se sobrescribirá: "
            f"{ruta_salida}. Indica otra ruta con --salida."
        ) from error


def main():
    ruta_salida = obtener_ruta_salida()

    if ruta_salida.exists():
        raise FileExistsError(
            "El archivo de salida ya existe y no se sobrescribirá: "
            f"{ruta_salida}. Indica otra ruta con --salida."
        )

    df = pd.read_csv(
        MANIFEST,
        dtype={"sample_id": str, "study_eye_visit_key": str},
    )

    if df["subject_key"].isna().any():
        raise ValueError("Hay pacientes sin identificador.")

    if df["sample_id"].duplicated().any():
        raise ValueError("Hay estudios duplicados en el manifiesto.")

    if not set(df["split"].unique()).issubset(
        {"train", "validation", "test"}
    ):
        raise ValueError("Hay particiones desconocidas.")

    pacientes_por_split = {
        split: set(df.loc[df["split"] == split, "subject_key"])
        for split in ("train", "validation", "test")
    }

    for a, b in (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    ):
        interseccion = pacientes_por_split[a] & pacientes_por_split[b]
        if interseccion:
            raise ValueError(
                f"Fuga de pacientes entre {a} y {b}: {len(interseccion)}"
            )

    seleccionados = []

    for split in ("train", "validation"):
        parte = df[df["split"] == split].copy()
        pacientes = sorted(parte["subject_key"].unique().tolist())

        n = round(len(pacientes) * FRACCION)
        elegidos = set(
            pd.Series(pacientes)
            .sample(n=n, random_state=SEMILLA)
            .tolist()
        )

        seleccionados.append(
            parte[parte["subject_key"].isin(elegidos)].copy()
        )

    piloto = pd.concat(seleccionados, ignore_index=True)

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    escribir_sin_sobrescribir(piloto, ruta_salida)

    print("\nSelección del piloto creada:", ruta_salida)
    print("\nPacientes seleccionados por partición:")
    print(piloto.groupby("split")["subject_key"].nunique().to_string())

    print("\nEstudios seleccionados por partición:")
    print(piloto.groupby("split")["sample_id"].nunique().to_string())

    print("\nTotal de estudios:", piloto["sample_id"].nunique())
    print("Total de pacientes:", piloto["subject_key"].nunique())
    print("Incluye conjunto test:", (piloto["split"] == "test").any())

    assert set(piloto["split"].unique()) == {"train", "validation"}
    assert not piloto["sample_id"].duplicated().any()
    assert not (piloto["split"] == "test").any()

    print("\nVerificación de selección superada.")


if __name__ == "__main__":
    main()
