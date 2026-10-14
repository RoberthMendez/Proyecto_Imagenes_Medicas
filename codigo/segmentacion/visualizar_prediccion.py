
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from codigo.segmentacion.dataset_2d import Dataset2D
from codigo.segmentacion.modelo_unet import UNet2D


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROYECTO = Path(__file__).resolve().parents[2]

CARPETA_SALIDA = (
    PROYECTO / "resultados" / "segmentacion"
)
CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

RUTA_MODELO = (
    CARPETA_SALIDA / "unet2d_formal.pth"
)

RUTA_FIGURA = (
    CARPETA_SALIDA / "prediccion_modelo_formal.png"
)

DISPOSITIVO = torch.device("cpu")


# ============================================================
# CARGA DEL MODELO
# ============================================================

def cargar_modelo():
    if not RUTA_MODELO.exists():
        raise FileNotFoundError(
            f"No existe el modelo: {RUTA_MODELO}"
        )

    checkpoint = torch.load(
        RUTA_MODELO,
        map_location=DISPOSITIVO,
        weights_only=False,
    )

    configuracion = checkpoint["configuracion"]

    modelo = UNet2D(
        canales_entrada=configuracion["canales_entrada"],
        clases_salida=configuracion["clases_salida"],
        base=configuracion["base"],
    )

    modelo.load_state_dict(checkpoint["modelo"])
    modelo.to(DISPOSITIVO)
    modelo.eval()

    epoca = checkpoint.get("epoca", "No disponible")
    metricas = checkpoint.get("metricas_validacion", {})

    print("Modelo cargado:", RUTA_MODELO.name)
    print("Época guardada:", epoca)

    if "dice_macro" in metricas:
        print(
            "Dice macro registrado:",
            f"{metricas['dice_macro']:.4f}",
        )

    return modelo


# ============================================================
# SELECCIÓN DEL CORTE
# ============================================================

def seleccionar_corte(dataset):
    """
    Selecciona, entre los estudios cargados, el corte con más
    píxeles no pertenecientes al fondo en la máscara real.
    """

    indice_elegido = None
    imagen_elegida = None
    mascara_elegida = None
    max_pixeles_tumorales = 0

    for indice in range(len(dataset)):
        imagen, mascara = dataset[indice]

        pixeles_tumorales = int(
            (mascara > 0).sum().item()
        )

        if pixeles_tumorales > max_pixeles_tumorales:
            max_pixeles_tumorales = pixeles_tumorales
            indice_elegido = indice
            imagen_elegida = imagen
            mascara_elegida = mascara

    if indice_elegido is None:
        raise RuntimeError(
            "No se encontró ningún corte con etiquetas tumorales "
            "en los estudios revisados."
        )

    return (
        indice_elegido,
        imagen_elegida,
        mascara_elegida,
        max_pixeles_tumorales,
    )


# ============================================================
# PREDICCIÓN
# ============================================================

def predecir(modelo, imagen):
    entrada = imagen.unsqueeze(0).to(DISPOSITIVO)

    with torch.no_grad():
        logits = modelo(entrada)
        prediccion = torch.argmax(logits, dim=1)[0]

    return prediccion.cpu().numpy()


# ============================================================
# VISUALIZACIÓN
# ============================================================

def visualizar(imagen, mascara_real, prediccion):
    # Canal 1 del tensor: T1c.
    imagen_t1c = imagen[1]

    print("Etiquetas reales:", np.unique(mascara_real).tolist())
    print("Etiquetas predichas:", np.unique(prediccion).tolist())

    print("\nDistribución por clase en el corte:")
    for clase in range(4):
        reales = int(np.sum(mascara_real == clase))
        predichos = int(np.sum(prediccion == clase))

        print(
            f"Clase {clase}: "
            f"reales={reales:,} | predichos={predichos:,}"
        )

    fig, ejes = plt.subplots(
        1, 4,
        figsize=(18, 5),
    )

    ejes[0].imshow(imagen_t1c, cmap="gray")
    ejes[0].set_title("Imagen T1c")

    ejes[1].imshow(
        mascara_real,
        vmin=0,
        vmax=3,
        cmap="viridis",
        interpolation="nearest",
    )
    ejes[1].set_title("Máscara real")

    ejes[2].imshow(
        prediccion,
        vmin=0,
        vmax=3,
        cmap="viridis",
        interpolation="nearest",
    )
    ejes[2].set_title("Máscara predicha")

    ejes[3].imshow(imagen_t1c, cmap="gray")

    # Superponer las etiquetas reales.
    mascara_superpuesta = np.ma.masked_where(
        mascara_real == 0,
        mascara_real,
    )

    ejes[3].imshow(
        mascara_superpuesta,
        vmin=1,
        vmax=3,
        cmap="autumn",
        alpha=0.60,
        interpolation="nearest",
    )

    # Contornos de la predicción para comparar su extensión.
    for clase, color in (
        (1, "cyan"),
        (2, "lime"),
        (3, "magenta"),
    ):
        mascara_clase = (prediccion == clase).astype(float)

        if mascara_clase.min() != mascara_clase.max():
            ejes[3].contour(
                mascara_clase,
                levels=[0.5],
                colors=[color],
                linewidths=0.9,
            )

    ejes[3].set_title(
        "Referencia y contornos predichos"
    )

    for eje in ejes:
        eje.axis("off")

    fig.suptitle(
        "U-Net 2D: inspección visual del mejor modelo del piloto",
        fontsize=13,
    )

    fig.tight_layout()
    fig.savefig(
        RUTA_FIGURA,
        dpi=160,
        bbox_inches="tight",
    )

    print("\nFigura guardada en:", RUTA_FIGURA)

    plt.show()


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    torch.set_num_threads(2)

    modelo = cargar_modelo()

    # Se mantienen dos estudios de entrenamiento para inspección.
    dataset = Dataset2D("validation")

    (
        indice,
        imagen,
        mascara,
        cantidad_pixeles,
    ) = seleccionar_corte(dataset)

    posicion_estudio, indice_corte = (
        dataset.indice_cortes[indice]
    )

    estudio_id = dataset.estudios[posicion_estudio]

    print("\nInformación del corte seleccionado")
    print("Estudio:", estudio_id)
    print("Índice del corte:", indice_corte)
    print("Píxeles tumorales reales:", f"{cantidad_pixeles:,}")

    imagen_np = imagen.cpu().numpy()
    mascara_real = mascara.cpu().numpy()

    prediccion = predecir(modelo, imagen)

    visualizar(
        imagen_np,
        mascara_real,
        prediccion,
    )


if __name__ == "__main__":
    main()
