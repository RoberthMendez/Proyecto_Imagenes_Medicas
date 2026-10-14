from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset

from codigo.segmentacion.cargar_datos import buscar_archivo
from codigo.segmentacion.dataset_2d import Dataset2D
from codigo.segmentacion.modelo_unet import UNet2D


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROYECTO = Path(__file__).resolve().parents[2]
SALIDA = PROYECTO / "resultados" / "segmentacion"
SALIDA.mkdir(parents=True, exist_ok=True)

MODELO_SALIDA = SALIDA / "unet2d_formal.pth"
HISTORIAL_SALIDA = SALIDA / "historial_entrenamiento.csv"
CORTES_SALIDA = SALIDA / "cortes_entrenamiento.csv"

SEMILLA = 42
EPOCAS = 5
BATCH_SIZE = 2
TASA_APRENDIZAJE = 1e-4
NUM_HILOS = 2

# Muestreo por estudio
CORTES_POR_CLASE = 4
CORTES_FONDO = 2

# Ejecutar primero una prueba corta antes de aumentar épocas.
DISPOSITIVO = torch.device("cpu")


# ============================================================
# SELECCIÓN DE CORTES A PARTIR DE LAS MÁSCARAS
# ============================================================

def seleccionar_cortes(dataset, nombre_particion):
    """
    Selecciona cortes de todos los estudios de una partición.
    Lee las máscaras directamente para no cargar las modalidades
    durante la selección.
    """
    seleccion = []
    registros = []

    print(f"\nSeleccionando cortes de {nombre_particion}...")

    for posicion, estudio_id in enumerate(dataset.estudios):
        carpeta = (
            PROYECTO
            / "datos"
            / "BraTS2023-GLI-Dataset"
            / estudio_id
        )
        archivo = buscar_archivo(carpeta, "seg")

        mascara = np.asanyarray(nib.load(str(archivo)).dataobj)

        if mascara.ndim != 3:
            raise ValueError(
                f"Máscara no tridimensional: {estudio_id}"
            )

        indices_estudio = dataset.indices_por_estudio[posicion]

        if len(indices_estudio) != mascara.shape[2]:
            raise ValueError(
                f"Número de cortes incompatible: {estudio_id}"
            )

        candidatos = {1: [], 2: [], 3: []}
        fondo = []

        for z in range(mascara.shape[2]):
            etiquetas = np.unique(mascara[:, :, z]).astype(int)

            if np.array_equal(etiquetas, np.array([0])):
                fondo.append(z)
            else:
                for clase in (1, 2, 3):
                    if clase in etiquetas:
                        candidatos[clase].append(z)

        cortes_z = set()

        for clase, posiciones in candidatos.items():
            if posiciones:
                cantidad = min(CORTES_POR_CLASE, len(posiciones))
                elegidos = np.linspace(
                    0, len(posiciones) - 1,
                    num=cantidad,
                    dtype=int,
                )
                cortes_z.update(posiciones[i] for i in elegidos)

        if fondo:
            cantidad = min(CORTES_FONDO, len(fondo))
            elegidos = np.linspace(
                0, len(fondo) - 1,
                num=cantidad,
                dtype=int,
            )
            cortes_z.update(fondo[i] for i in elegidos)

        # Convertir coordenadas z en índices del Dataset2D.
        indice_por_z = {
            z: indice
            for z, indice in enumerate(indices_estudio)
        }

        indices_seleccionados = sorted(
            indice_por_z[z] for z in cortes_z
        )
        seleccion.extend(indices_seleccionados)

        registros.append({
            "particion": nombre_particion,
            "estudio": estudio_id,
            "cortes_seleccionados": len(indices_seleccionados),
            "cortes_totales": mascara.shape[2],
            "cortes_clase_1": len(candidatos[1]),
            "cortes_clase_2": len(candidatos[2]),
            "cortes_clase_3": len(candidatos[3]),
        })

        if (posicion + 1) % 50 == 0 or posicion + 1 == len(dataset.estudios):
            print(
                f"Estudios revisados: "
                f"{posicion + 1}/{len(dataset.estudios)}"
            )

        del mascara

    return sorted(set(seleccion)), registros


# ============================================================
# FUNCIÓN DE PÉRDIDA
# ============================================================

def perdida_segmentacion(logits, mascaras, pesos):
    """
    Combina entropía cruzada ponderada y Dice diferenciable.
    """
    ce = F.cross_entropy(
        logits,
        mascaras,
        weight=pesos,
    )

    probabilidades = torch.softmax(logits, dim=1)
    etiquetas = F.one_hot(
        mascaras,
        num_classes=4,
    ).permute(0, 3, 1, 2).float()

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

    return ce + torch.stack(perdidas_dice).mean()


# ============================================================
# EVALUACIÓN
# ============================================================

def evaluar(modelo, cargador):
    modelo.eval()

    intersecciones = np.zeros(4, dtype=np.int64)
    reales = np.zeros(4, dtype=np.int64)
    predichos = np.zeros(4, dtype=np.int64)
    perdidas = []

    with torch.no_grad():
        for imagenes, mascaras in cargador:
            imagenes = imagenes.to(DISPOSITIVO)
            mascaras = mascaras.to(DISPOSITIVO)

            logits = modelo(imagenes)
            predicciones = logits.argmax(dim=1)

            perdidas.append(
                F.cross_entropy(logits, mascaras).item()
            )

            for clase in range(4):
                real = mascaras == clase
                pred = predicciones == clase

                reales[clase] += real.sum().item()
                predichos[clase] += pred.sum().item()
                intersecciones[clase] += (
                    real & pred
                ).sum().item()

    dice = {}

    for clase in (1, 2, 3):
        denominador = reales[clase] + predichos[clase]
        dice[clase] = (
            2 * intersecciones[clase] / denominador
            if denominador > 0
            else float("nan")
        )

    valores = [
        valor for valor in dice.values()
        if np.isfinite(valor)
    ]

    return {
        "val_loss_ce": float(np.mean(perdidas)),
        "dice_clase_1": dice[1],
        "dice_clase_2": dice[2],
        "dice_clase_3": dice[3],
        "dice_macro": (
            float(np.mean(valores)) if valores else float("nan")
        ),
    }


# ============================================================
# ENTRENAMIENTO
# ============================================================

def main():
    torch.manual_seed(SEMILLA)
    np.random.seed(SEMILLA)
    torch.set_num_threads(NUM_HILOS)

    print("Dispositivo:", DISPOSITIVO)
    print("Semilla:", SEMILLA)

    # No sobrescribir resultados de ejecuciones anteriores.
    if MODELO_SALIDA.exists() or HISTORIAL_SALIDA.exists():
        raise FileExistsError(
            "Ya existe una salida del entrenamiento formal. "
            "Cambia los nombres de salida antes de iniciar otro "
            "experimento para no sobrescribir resultados."
        )

    train = Dataset2D("train")
    validation = Dataset2D("validation")

    print("\nEstudios train:", len(train.estudios))
    print("Estudios validation:", len(validation.estudios))

    indices_train, filas_train = seleccionar_cortes(
        train, "train"
    )
    indices_val, filas_val = seleccionar_cortes(
        validation, "validation"
    )

    if not indices_train or not indices_val:
        raise RuntimeError(
            "No se seleccionaron cortes suficientes."
        )

    pd.DataFrame(
        filas_train + filas_val
    ).to_csv(CORTES_SALIDA, index=False, encoding="utf-8-sig")

    print("\nCortes seleccionados para train:", len(indices_train))
    print("Cortes seleccionados para validation:", len(indices_val))
    print("Registro de muestreo:", CORTES_SALIDA)

    # Orden secuencial para aprovechar la caché de un estudio.
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

    # Modelo NUEVO: no carga pesos del piloto.
    modelo = UNet2D(
        canales_entrada=4,
        clases_salida=4,
        base=16,
    ).to(DISPOSITIVO)

    parametros = sum(
        p.numel()
        for p in modelo.parameters()
        if p.requires_grad
    )
    print("Parámetros entrenables:", f"{parametros:,}")

    # Pesos de clase previamente estimados en la muestra de train.
    # La clase de fondo recibe menor peso.
    pesos = torch.tensor(
        [0.0157429661, 1.7873053901,
         0.7469318520, 1.4027908936],
        dtype=torch.float32,
        device=DISPOSITIVO,
    )

    optimizador = torch.optim.Adam(
        modelo.parameters(),
        lr=TASA_APRENDIZAJE,
    )

    historial = []
    mejor_dice = -float("inf")

    for epoca in range(1, EPOCAS + 1):
        modelo.train()
        perdidas_train = []

        print(f"\nÉPOCA {epoca}/{EPOCAS}")

        for paso, (imagenes, mascaras) in enumerate(
            train_loader, start=1
        ):
            imagenes = imagenes.to(DISPOSITIVO)
            mascaras = mascaras.to(DISPOSITIVO)

            optimizador.zero_grad(set_to_none=True)
            logits = modelo(imagenes)

            perdida = perdida_segmentacion(
                logits, mascaras, pesos
            )

            if not torch.isfinite(perdida):
                raise RuntimeError(
                    f"Pérdida no finita en época {epoca}, "
                    f"paso {paso}."
                )

            perdida.backward()
            torch.nn.utils.clip_grad_norm_(
                modelo.parameters(), max_norm=1.0
            )
            optimizador.step()
            perdidas_train.append(perdida.item())

            if paso % 100 == 0:
                print(
                    f"Paso {paso}/{len(train_loader)} | "
                    f"Pérdida: {perdida.item():.4f}"
                )

        metricas = evaluar(modelo, val_loader)

        registro = {
            "epoca": epoca,
            "train_loss": float(np.mean(perdidas_train)),
            **metricas,
        }
        historial.append(registro)

        pd.DataFrame(historial).to_csv(
            HISTORIAL_SALIDA,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Pérdida train: {registro['train_loss']:.4f}")
        print(f"Pérdida validation: {metricas['val_loss_ce']:.4f}")
        print(f"Dice clase 1: {metricas['dice_clase_1']:.4f}")
        print(f"Dice clase 2: {metricas['dice_clase_2']:.4f}")
        print(f"Dice clase 3: {metricas['dice_clase_3']:.4f}")
        print(f"Dice macro: {metricas['dice_macro']:.4f}")

        puntuacion = metricas["dice_macro"]

        if np.isfinite(puntuacion) and puntuacion > mejor_dice:
            mejor_dice = puntuacion

            torch.save(
                {
                    "modelo": modelo.state_dict(),
                    "configuracion": {
                        "canales_entrada": 4,
                        "clases_salida": 4,
                        "base": 16,
                    },
                    "pesos_clase": pesos.cpu(),
                    "epoca": epoca,
                    "metricas_validacion": metricas,
                    "semilla": SEMILLA,
                    "tasa_aprendizaje": TASA_APRENDIZAJE,
                    "batch_size": BATCH_SIZE,
                    "cortes_por_clase": CORTES_POR_CLASE,
                    "cortes_fondo": CORTES_FONDO,
                    "estudios_train": train.estudios,
                    "estudios_validation": validation.estudios,
                },
                MODELO_SALIDA,
            )
            print("Mejor checkpoint guardado.")

    print("\nEntrenamiento finalizado.")
    print("Mejor Dice macro de validación:", mejor_dice)
    print("Modelo:", MODELO_SALIDA)
    print("Historial:", HISTORIAL_SALIDA)
    print("Muestreo:", CORTES_SALIDA)


if __name__ == "__main__":
    main()
