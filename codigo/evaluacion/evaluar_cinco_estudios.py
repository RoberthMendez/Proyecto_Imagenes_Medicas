
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Subset

from segmentacion.dataset_2d import Dataset2D
from segmentacion.modelo_unet import UNet2D


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_RESULTADOS = PROYECTO / "resultados" / "segmentacion"

RUTA_MODELO = CARPETA_RESULTADOS / "unet2d_ajuste_v2.pth"
RUTA_CSV = CARPETA_RESULTADOS / "evaluacion_cinco_estudios.csv"

NUM_ESTUDIOS = 5
BATCH_SIZE = 2
DISPOSITIVO = torch.device("cpu")


# ============================================================
# CARGAR MODELO
# ============================================================

def cargar_modelo():
    if not RUTA_MODELO.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo: {RUTA_MODELO}"
        )

    checkpoint = torch.load(
        RUTA_MODELO,
        map_location=DISPOSITIVO,
        weights_only=True,
    )

    config = checkpoint["configuracion"]

    modelo = UNet2D(
        canales_entrada=config["canales_entrada"],
        clases_salida=config["clases_salida"],
        base=config["base"],
    )

    modelo.load_state_dict(checkpoint["modelo"])
    modelo.to(DISPOSITIVO)
    modelo.eval()

    print("Modelo:", RUTA_MODELO.name)
    print("Época del modelo:", checkpoint.get("epoca", "No disponible"))

    return modelo


# ============================================================
# EVALUAR UN ESTUDIO
# ============================================================

def evaluar_estudio(modelo, dataset, indices):
    conteo_real = np.zeros(4, dtype=np.int64)
    conteo_predicho = np.zeros(4, dtype=np.int64)
    interseccion = np.zeros(4, dtype=np.int64)

    cargador = DataLoader(
        Subset(dataset, indices),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    with torch.no_grad():
        for imagenes, mascaras in cargador:
            imagenes = imagenes.to(DISPOSITIVO)
            mascaras = mascaras.to(DISPOSITIVO)

            logits = modelo(imagenes)
            predicciones = torch.argmax(logits, dim=1)

            for clase in range(4):
                reales = mascaras == clase
                predichos = predicciones == clase

                conteo_real[clase] += reales.sum().item()
                conteo_predicho[clase] += predichos.sum().item()
                interseccion[clase] += (
                    reales & predichos
                ).sum().item()

    dice = {}

    for clase in (1, 2, 3):
        denominador = (
            conteo_real[clase] + conteo_predicho[clase]
        )

        dice[clase] = (
            2.0 * interseccion[clase] / denominador
            if denominador > 0
            else float("nan")
        )

    valores_dice = [
        valor for valor in dice.values()
        if np.isfinite(valor)
    ]

    dice_macro = (
        float(np.mean(valores_dice))
        if valores_dice
        else float("nan")
    )

    fila = {
        "estudio": dataset.estudios[
            dataset.indice_cortes[indices[0]][0]
        ],
        "numero_cortes": len(indices),
        "pixeles_totales": int(conteo_real.sum()),
        "dice_clase_1": dice[1],
        "dice_clase_2": dice[2],
        "dice_clase_3": dice[3],
        "dice_macro_tumoral": dice_macro,
    }

    for clase in range(4):
        fila[f"reales_clase_{clase}"] = int(conteo_real[clase])
        fila[f"predichos_clase_{clase}"] = int(
            conteo_predicho[clase]
        )
        fila[f"interseccion_clase_{clase}"] = int(
            interseccion[clase]
        )

    return fila


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    torch.set_num_threads(2)

    modelo = cargar_modelo()

    dataset = Dataset2D(
        "validation",
        max_estudios=NUM_ESTUDIOS,
    )

    print("\nEstudios cargados:", len(dataset.estudios))
    print("Cortes indexados:", len(dataset))

    resultados = []

    for posicion, indices in dataset.indices_por_estudio.items():
        estudio_id = dataset.estudios[posicion]

        print(f"\nEvaluando {estudio_id}...")

        fila = evaluar_estudio(modelo, dataset, indices)
        resultados.append(fila)

        print(f"Cortes: {fila['numero_cortes']}")
        print(f"Dice clase 1: {fila['dice_clase_1']:.4f}")
        print(f"Dice clase 2: {fila['dice_clase_2']:.4f}")
        print(f"Dice clase 3: {fila['dice_clase_3']:.4f}")
        print(
            "Dice macro tumoral:",
            f"{fila['dice_macro_tumoral']:.4f}",
        )

    df = pd.DataFrame(resultados)
    df.to_csv(RUTA_CSV, index=False)

    print("\nRESUMEN DE LOS ESTUDIOS")
    columnas = [
        "estudio",
        "dice_clase_1",
        "dice_clase_2",
        "dice_clase_3",
        "dice_macro_tumoral",
    ]
    print(df[columnas].to_string(index=False))

    print("\nPromedio del Dice por estudio:")
    for columna in (
        "dice_clase_1",
        "dice_clase_2",
        "dice_clase_3",
        "dice_macro_tumoral",
    ):
        print(f"{columna}: {df[columna].mean():.4f}")

    print("\nReporte guardado en:", RUTA_CSV)


if __name__ == "__main__":
    main()
