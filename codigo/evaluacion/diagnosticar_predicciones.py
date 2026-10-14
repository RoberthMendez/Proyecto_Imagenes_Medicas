
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from segmentacion.dataset_2d import Dataset2D
from segmentacion.modelo_unet import UNet2D


PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_MODELOS = PROYECTO / "resultados" / "segmentacion"

RUTA_MODELO = CARPETA_MODELOS / "unet2d_ajuste_v2.pth"
RUTA_SALIDA = (
    PROYECTO
    / "resultados"
    / "segmentacion"
    / "diagnostico_mejor_epocas.csv"
)

def contar_clases(mascara):
    return torch.bincount(
        mascara.reshape(-1).to(torch.int64),
        minlength=4,
    )[:4]


def main():
    torch.set_num_threads(2)
    dispositivo = torch.device("cpu")

    checkpoint = torch.load(
        RUTA_MODELO,
        map_location=dispositivo,
        weights_only=True,
    )

    config = checkpoint["configuracion"]

    modelo = UNet2D(
        canales_entrada=config["canales_entrada"],
        clases_salida=config["clases_salida"],
        base=config["base"],
    )

    modelo.load_state_dict(checkpoint["modelo"])
    modelo.to(dispositivo)
    modelo.eval()

    # Mismo estudio usado en la evaluación inicial.
    dataset = Dataset2D("validation", max_estudios=1)

    cargador = DataLoader(
        dataset,
        batch_size=2,
        shuffle=False,
        num_workers=0,
    )

    conteo_real = np.zeros(4, dtype=np.int64)
    conteo_predicho = np.zeros(4, dtype=np.int64)
    conteo_interseccion = np.zeros(4, dtype=np.int64)
    total_pixeles = 0

    with torch.no_grad():
        for imagenes, mascaras in cargador:
            logits = modelo(imagenes.to(dispositivo))
            predicciones = logits.argmax(dim=1).cpu()

            for clase in range(4):
                real_clase = mascaras == clase
                pred_clase = predicciones == clase

                conteo_real[clase] += real_clase.sum().item()
                conteo_predicho[clase] += pred_clase.sum().item()
                conteo_interseccion[clase] += (
                    real_clase & pred_clase
                ).sum().item()

            total_pixeles += mascaras.numel()

    filas = []

    print("\nDistribución de clases en validación")
    print("Estudios evaluados:", len(dataset.estudios))
    print(f"Píxeles totales: {total_pixeles:,}\n")

    for clase in range(4):
        dice = (
            2 * conteo_interseccion[clase]
            / (conteo_real[clase] + conteo_predicho[clase])
            if conteo_real[clase] + conteo_predicho[clase] > 0
            else float("nan")
        )

        porcentaje_real = 100 * conteo_real[clase] / total_pixeles
        porcentaje_predicho = (
            100 * conteo_predicho[clase] / total_pixeles
        )

        fila = {
            "clase": clase,
            "pixeles_reales": int(conteo_real[clase]),
            "porcentaje_real": porcentaje_real,
            "pixeles_predichos": int(conteo_predicho[clase]),
            "porcentaje_predicho": porcentaje_predicho,
            "interseccion": int(conteo_interseccion[clase]),
            "dice": dice,
        }
        filas.append(fila)

        print(f"Clase {clase}")
        print(f"  Reales: {conteo_real[clase]:,} ({porcentaje_real:.4f}%)")
        print(
            f"  Predichos: {conteo_predicho[clase]:,} "
            f"({porcentaje_predicho:.4f}%)"
        )
        print(f"  Intersección: {conteo_interseccion[clase]:,}")
        print(f"  Dice: {dice:.6f}\n")

    assert conteo_real.sum() == total_pixeles
    assert conteo_predicho.sum() == total_pixeles

    df = pd.DataFrame(filas)
    df.to_csv(RUTA_SALIDA, index=False)

    print("Comprobación de etiquetas: correcta.")
    print("La suma de píxeles reales y predichos coincide con el total.")
    print("Reporte guardado en:", RUTA_SALIDA)


if __name__ == "__main__":
    main()
