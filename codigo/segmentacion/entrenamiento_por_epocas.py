
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset

from codigo.segmentacion.dataset_2d import Dataset2D
from codigo.segmentacion.modelo_unet import UNet2D


PROYECTO = Path(__file__).resolve().parents[2]
SALIDA = PROYECTO / "resultados" / "segmentacion"
SALIDA.mkdir(parents=True, exist_ok=True)

MODELO_INICIAL = SALIDA / "unet2d_piloto_v2.pth"
MEJOR_MODELO = SALIDA / "unet2d_ajuste_v2.pth"
HISTORIAL = SALIDA / "historial_ajuste_v2.csv"

SEMILLA = 44
EPOCAS = 5
BATCH_SIZE = 2
TUMOR_POR_CLASE = 4
FONDO_POR_ESTUDIO = 2



def seleccionar_cortes_entrenamiento(dataset):
    """Selecciona cortes tumorales distribuidos por clase y volumen."""
    seleccion = set()

    for posicion, indices in dataset.indices_por_estudio.items():
        cortes_clase = {1: [], 2: [], 3: []}
        cortes_fondo = []

        # Identificar qué clases aparecen en cada corte.
        for indice in indices:
            _, mascara = dataset[indice]
            etiquetas = torch.unique(mascara).tolist()

            if etiquetas == [0]:
                cortes_fondo.append(indice)
            else:
                for clase in (1, 2, 3):
                    if clase in etiquetas:
                        cortes_clase[clase].append(indice)

        # Elegir cortes repartidos a lo largo de la lista.
        for clase, candidatos in cortes_clase.items():
            if not candidatos:
                print(
                    f"Advertencia: clase {clase} no encontrada "
                    f"en estudio {posicion}."
                )
                continue

            cantidad = min(TUMOR_POR_CLASE, len(candidatos))

            posiciones = np.linspace(
                0, len(candidatos) - 1,
                num=cantidad,
                dtype=int,
            )

            seleccion.update(candidatos[p] for p in posiciones)

        # Incorporar algunos cortes de fondo repartidos.
        if cortes_fondo:
            cantidad_fondo = min(
                FONDO_POR_ESTUDIO, len(cortes_fondo)
            )
            posiciones_fondo = np.linspace(
                0, len(cortes_fondo) - 1,
                num=cantidad_fondo,
                dtype=int,
            )
            seleccion.update(
                cortes_fondo[p] for p in posiciones_fondo
            )

    return sorted(seleccion)


def perdida_segmentacion(logits, mascara, pesos):
    """Cross-Entropy ponderada más Dice para las clases tumorales."""
    ce = F.cross_entropy(logits, mascara, weight=pesos)

    probabilidades = torch.softmax(logits, dim=1)
    etiquetas = F.one_hot(mascara, num_classes=4)
    etiquetas = etiquetas.permute(0, 3, 1, 2).float()

    perdidas_dice = []

    for clase in (1, 2, 3):
        real = etiquetas[:, clase]
        pred = probabilidades[:, clase]

        interseccion = (pred * real).sum()
        denominador = pred.sum() + real.sum()

        dice = (2 * interseccion + 1e-6) / (
            denominador + 1e-6
        )

        perdidas_dice.append(1 - dice)

    dice_loss = torch.stack(perdidas_dice).mean()

    return ce + dice_loss


def evaluar(modelo, cargador, dispositivo):
    """Evalúa todos los cortes seleccionados, sin actualizar pesos."""
    modelo.eval()

    conteo_real = np.zeros(4, dtype=np.int64)
    conteo_pred = np.zeros(4, dtype=np.int64)
    interseccion = np.zeros(4, dtype=np.int64)
    perdidas = []

    with torch.no_grad():
        for imagenes, mascaras in cargador:
            imagenes = imagenes.to(dispositivo)
            mascaras = mascaras.to(dispositivo)

            logits = modelo(imagenes)
            predicciones = logits.argmax(dim=1)

            perdidas.append(
                F.cross_entropy(logits, mascaras).item()
            )

            for clase in range(4):
                real = mascaras == clase
                pred = predicciones == clase

                conteo_real[clase] += real.sum().item()
                conteo_pred[clase] += pred.sum().item()
                interseccion[clase] += (real & pred).sum().item()

    dice = {}

    for clase in (1, 2, 3):
        denominador = conteo_real[clase] + conteo_pred[clase]
        dice[clase] = (
            2 * interseccion[clase] / denominador
            if denominador > 0
            else float("nan")
        )

    valores = [v for v in dice.values() if np.isfinite(v)]
    dice_macro = float(np.mean(valores)) if valores else float("nan")

    return {
        "val_loss_ce": float(np.mean(perdidas)),
        "dice_1": dice[1],
        "dice_2": dice[2],
        "dice_3": dice[3],
        "dice_macro": dice_macro,
        "pixeles_reales_1": int(conteo_real[1]),
        "pixeles_predichos_1": int(conteo_pred[1]),
        "pixeles_reales_2": int(conteo_real[2]),
        "pixeles_predichos_2": int(conteo_pred[2]),
        "pixeles_reales_3": int(conteo_real[3]),
        "pixeles_predichos_3": int(conteo_pred[3]),
    }


def main():
    torch.manual_seed(SEMILLA)
    np.random.seed(SEMILLA)
    torch.set_num_threads(2)

    dispositivo = torch.device("cpu")
    print("Dispositivo:", dispositivo)

    if not MODELO_INICIAL.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo inicial: {MODELO_INICIAL}"
        )

    checkpoint = torch.load(
        MODELO_INICIAL,
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

    pesos = torch.tensor(
      [0.0157429661, 1.7873053901, 0.7469318520, 1.4027908936],
      dtype=torch.float32,
      device=dispositivo
    )

    # Dos estudios para entrenamiento y uno para validación.
    train = Dataset2D("train", max_estudios=10)
    validation = Dataset2D("validation", max_estudios=5)

    indices_train = seleccionar_cortes_entrenamiento(train)
    indices_val = list(range(len(validation)))

    if not indices_train:
        raise RuntimeError("No hay cortes de entrenamiento.")

    print("Cortes de entrenamiento seleccionados:", len(indices_train))
    print("Cortes de validación:", len(indices_val))
    print("Pesos de clases:", pesos.tolist())

    # El orden secuencial evita recargar el mismo volumen
    # innecesariamente en cada lote.
    train_loader = DataLoader(
        Subset(train, indices_train),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    val_loader = DataLoader(
        Subset(validation, indices_val),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    optimizador = torch.optim.Adam(
        modelo.parameters(),
        lr=5e-5,
    )

    historial = []
    mejor_dice = -float("inf")

    for epoca in range(1, EPOCAS + 1):
        modelo.train()
        perdidas_train = []

        for paso, (imagenes, mascaras) in enumerate(
            train_loader, start=1
        ):
            imagenes = imagenes.to(dispositivo)
            mascaras = mascaras.to(dispositivo)

            optimizador.zero_grad()
            logits = modelo(imagenes)

            perdida = perdida_segmentacion(
                logits, mascaras, pesos
            )

            if not torch.isfinite(perdida):
                raise RuntimeError(
                    f"Pérdida no finita en época {epoca}, paso {paso}"
                )

            perdida.backward()
            torch.nn.utils.clip_grad_norm_(
                modelo.parameters(), max_norm=1.0
            )
            optimizador.step()
            perdidas_train.append(perdida.item())

        metricas = evaluar(modelo, val_loader, dispositivo)

        registro = {
            "epoca": epoca,
            "train_loss": float(np.mean(perdidas_train)),
            **metricas,
        }
        historial.append(registro)

        print(
            f"\nÉpoca {epoca}/{EPOCAS} | "
            f"Train loss: {registro['train_loss']:.4f} | "
            f"Val CE: {metricas['val_loss_ce']:.4f}"
        )
        print(
            f"Dice clase 1: {metricas['dice_1']:.4f} | "
            f"clase 2: {metricas['dice_2']:.4f} | "
            f"clase 3: {metricas['dice_3']:.4f} | "
            f"macro: {metricas['dice_macro']:.4f}"
        )

        puntuacion = metricas["dice_macro"]

        if np.isfinite(puntuacion) and puntuacion > mejor_dice:
            mejor_dice = puntuacion

            torch.save(
                {
                    "modelo": modelo.state_dict(),
                    "configuracion": config,
                    "pesos_clase": pesos.cpu(),
                    "epoca": epoca,
                    "metricas_validacion": {
                                            clave: float(valor)
                                            if isinstance(valor, (int, float, np.integer, np.floating))
                                            else valor
                                            for clave, valor in metricas.items()
                                           }, 
                    "estudios_train": train.estudios,
                    "estudios_validation": validation.estudios,
                    "semilla": SEMILLA,
                },
                MEJOR_MODELO,
            )
            print("Nuevo mejor modelo guardado.")

        pd.DataFrame(historial).to_csv(HISTORIAL, index=False)

    print("\nEntrenamiento piloto terminado.")
    print("Mejor Dice macro:", mejor_dice)
    print("Historial:", HISTORIAL)
    print("Mejor modelo:", MEJOR_MODELO)


if __name__ == "__main__":
    main()
