from pathlib import Path
import json
import random
import time

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

from codigo.segmentacion.conjunto_cortes_2d import Dataset2D, LotesPorEstudio
from codigo.segmentacion.red_unet import UNet2D
from codigo.segmentacion.cargar_imagenes import DATASET, buscar_archivo


# ------------------------------------------------------------
# CONFIGURACIÓN REPRODUCIBLE
# ------------------------------------------------------------
SEMILLA = 42
EPOCAS = 2
BATCH_SIZE = 2
TASA_APRENDIZAJE = 1e-4
NUM_HILOS = 14
BASE = 16

PROYECTO = Path(__file__).resolve().parents[2]
MANIFEST = (
    PROYECTO / "resultados" / "modelo_piloto" / "manifest_piloto_30.csv"
)
SALIDA = PROYECTO / "resultados" / "modelo_piloto"
PREDICCIONES = SALIDA / "predicciones_30pct"
FIGURAS = SALIDA / "ejemplos_validacion"

CHECKPOINT = SALIDA / "unet2d_piloto_30pct.pth"
HISTORIAL = SALIDA / "historial_entrenamiento.csv"
METRICAS_CASO = SALIDA / "metricas_por_estudio.csv"
RESULTADOS = SALIDA / "resultados.csv"
CONFIGURACION = SALIDA / "configuracion.json"
RESUMEN = SALIDA / "resumen_metricas.json"

MODALIDADES = ("t1n", "t1c", "t2w", "t2f")
RUN_ID = "piloto_30pct_2epocas"


def fijar_semilla(semilla):
    random.seed(semilla)
    np.random.seed(semilla)
    torch.manual_seed(semilla)


def guardar_csv(registros, ruta):
    pd.DataFrame(registros).to_csv(ruta, index=False)


def calcular_dice(interseccion, denominador):
    """
    Si referencia y predicción están ambas vacías, devuelve NaN.
    Así no se infla artificialmente el promedio de Dice.
    """
    if denominador == 0:
        return float("nan")
    return float(2.0 * interseccion / denominador)


def perdida_dice(logits, mascaras):
    """
    Dice suave para las clases tumorales 1, 2 y 3.
    La clase de fondo (0) se excluye de esta parte de la pérdida.
    """
    probabilidades = torch.softmax(logits, dim=1)
    objetivos = torch.nn.functional.one_hot(
        mascaras, num_classes=4
    ).permute(0, 3, 1, 2).float()

    probabilidades = probabilidades[:, 1:]
    objetivos = objetivos[:, 1:]

    interseccion = (probabilidades * objetivos).sum(
        dim=(0, 2, 3)
    )
    denominador = (
        probabilidades.sum(dim=(0, 2, 3))
        + objetivos.sum(dim=(0, 2, 3))
    )

    dice = (2.0 * interseccion + 1e-6) / (
        denominador + 1e-6
    )
    return 1.0 - dice.mean()


def comprobar_salidas_libres():
    archivos = [
        CHECKPOINT,
        HISTORIAL,
        METRICAS_CASO,
        RESULTADOS,
        CONFIGURACION,
        RESUMEN,
    ]

    existentes = [str(p) for p in archivos if p.exists()]

    for carpeta in (PREDICCIONES, FIGURAS):
        if carpeta.exists() and any(carpeta.iterdir()):
            existentes.append(f"{carpeta} (contiene archivos)")

    if existentes:
        detalle = "\n".join(existentes)
        raise FileExistsError(
            "Se encontraron salidas anteriores. No se sobrescribirán:\n"
            + detalle
            + "\nArchiva o renombra esos resultados antes de ejecutar."
        )


def guardar_checkpoint(modelo, optimizador, epoca, configuracion,
                       perdida_entrenamiento):
    temporal = CHECKPOINT.with_suffix(".tmp")

    torch.save(
        {
            "epoca": epoca,
            "modelo_state_dict": modelo.state_dict(),
            "optimizador_state_dict": optimizador.state_dict(),
            "configuracion": configuracion,
            "perdida_entrenamiento": float(perdida_entrenamiento),
            "semilla": SEMILLA,
        },
        temporal,
    )
    temporal.replace(CHECKPOINT)


def guardar_figura_ejemplo(estudio_id, imagen, referencia, prediccion):
    """
    Genera una figura con T1c, máscara real y predicción
    en el mismo corte axial.
    """
    FIGURAS.mkdir(parents=True, exist_ok=True)

    fig, ejes = plt.subplots(1, 3, figsize=(12, 4))

    ejes[0].imshow(imagen, cmap="gray")
    ejes[0].set_title("T1c")
    ejes[1].imshow(referencia, vmin=0, vmax=3, interpolation="nearest")
    ejes[1].set_title("Máscara real")
    ejes[2].imshow(prediccion, vmin=0, vmax=3, interpolation="nearest")
    ejes[2].set_title("Predicción")

    for eje in ejes:
        eje.axis("off")

    fig.suptitle(f"{estudio_id} — corte axial representativo")
    fig.tight_layout()
    fig.savefig(
        FIGURAS / f"{estudio_id}.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def evaluar(modelo, dataset, dispositivo, mapa_pacientes):
    """
    Evalúa todos los cortes axiales de cada estudio de validación.
    Acumula intersecciones y volúmenes antes de calcular Dice 3D.
    """
    modelo.eval()
    registros = []
    resultados_obligatorios = []
    ejemplos_guardados = 0

    PREDICCIONES.mkdir(parents=True, exist_ok=True)

    with torch.no_grad():
        for posicion, estudio_id in enumerate(dataset.estudios):
            indices = dataset.indices_por_estudio[posicion]
            n_cortes = len(indices)

            intersecciones = np.zeros(4, dtype=np.int64)
            denominadores = np.zeros(4, dtype=np.int64)
            conteos_referencia = np.zeros(4, dtype=np.int64)
            conteos_prediccion = np.zeros(4, dtype=np.int64)

            prediccion_3d = None
            mejor_ejemplo = None
            max_voxeles_tumor = -1

            for inicio in range(0, n_cortes, BATCH_SIZE):
                indices_lote = indices[inicio:inicio + BATCH_SIZE]
                muestras = [dataset[i] for i in indices_lote]

                x = torch.stack([m[0] for m in muestras]).to(dispositivo)
                y = torch.stack([m[1] for m in muestras]).to(dispositivo)

                logits = modelo(x)
                pred = logits.argmax(dim=1)

                if prediccion_3d is None:
                    prediccion_3d = np.zeros(
                        (y.shape[1], y.shape[2], n_cortes),
                        dtype=np.uint8,
                    )

                for j in range(len(indices_lote)):
                    z = inicio + j
                    real_np = y[j].cpu().numpy().astype(np.uint8)
                    pred_np = pred[j].cpu().numpy().astype(np.uint8)

                    prediccion_3d[:, :, z] = pred_np

                    for clase in range(4):
                        real_clase = real_np == clase
                        pred_clase = pred_np == clase
                        conteos_referencia[clase] += int(real_clase.sum())
                        conteos_prediccion[clase] += int(pred_clase.sum())

                        intersecciones[clase] += int(
                            np.logical_and(
                                real_clase, pred_clase
                            ).sum()
                        )
                        denominadores[clase] += int(
                            real_clase.sum() + pred_clase.sum()
                        )

                    voxeles_tumor = int((real_np > 0).sum())
                    if voxeles_tumor > max_voxeles_tumor:
                        max_voxeles_tumor = voxeles_tumor
                        mejor_ejemplo = (
                            x[j, 1].cpu().numpy().copy(),
                            real_np.copy(),
                            pred_np.copy(),
                            z,
                        )

            dice_por_clase = {}
            dice_presentes = []

            for clase in range(1, 4):
                dice = calcular_dice(
                    intersecciones[clase],
                    denominadores[clase],
                )
                dice_por_clase[clase] = dice

                if np.isfinite(dice):
                    dice_presentes.append(dice)

            dice_macro = (
                float(np.mean(dice_presentes))
                if dice_presentes else float("nan")
            )

            archivo_prediccion = PREDICCIONES / f"{estudio_id}.npz"
            np.savez_compressed(
                archivo_prediccion,
                prediccion=prediccion_3d,
            )

            carpeta_estudio = DATASET / estudio_id
            archivo_referencia = buscar_archivo(carpeta_estudio, "seg")
            referencia_relativa = str(
                archivo_referencia.relative_to(PROYECTO)
            )
            prediccion_relativa = str(
                archivo_prediccion.relative_to(PROYECTO)
            )

            group_key = mapa_pacientes.get(estudio_id, "")

            registro = {
                "sample_id": estudio_id,
                "group_key": group_key,
                "n_cortes": n_cortes,
                "voxeles_referencia_clase_1": int(conteos_referencia[1]),
                "voxeles_referencia_clase_2": int(conteos_referencia[2]),
                "voxeles_referencia_clase_3": int(conteos_referencia[3]),
                "voxeles_prediccion_clase_1": int(conteos_prediccion[1]),
                "voxeles_prediccion_clase_2": int(conteos_prediccion[2]),
                "voxeles_prediccion_clase_3": int(conteos_prediccion[3]),
                "dice_clase_1": dice_por_clase[1],
                "dice_clase_2": dice_por_clase[2],
                "dice_clase_3": dice_por_clase[3],
                "dice_macro_clases_presentes": dice_macro,
                "referencia": referencia_relativa,
                "prediccion": prediccion_relativa,
                "run_id": RUN_ID,
            }
            registros.append(registro)

            resultados_obligatorios.append({
                "sample_id": estudio_id,
                "group_key": group_key,
                "referencia": referencia_relativa,
                "prediccion": prediccion_relativa,
                "score_o_metrica": (
                    f"dice_macro_clases_presentes={dice_macro:.6f}"
                    if np.isfinite(dice_macro)
                    else "dice_macro_clases_presentes=NaN"
                ),
                "run_id": RUN_ID,
            })

            if (
                ejemplos_guardados < 3
                and mejor_ejemplo is not None
                and max_voxeles_tumor > 0
            ):
                imagen, real, prediccion, z = mejor_ejemplo
                guardar_figura_ejemplo(
                    estudio_id, imagen, real, prediccion
                )
                ejemplos_guardados += 1
                print(
                    f"Figura guardada: {estudio_id}, corte z={z}",
                    flush=True,
                )

            print(
                f"Validación {posicion + 1}/{len(dataset.estudios)}: "
                f"{estudio_id} | "
                f"Dice C1={dice_por_clase[1]:.4f} "
                f"C2={dice_por_clase[2]:.4f} "
                f"C3={dice_por_clase[3]:.4f}",
                flush=True,
            )

    guardar_csv(registros, METRICAS_CASO)
    guardar_csv(resultados_obligatorios, RESULTADOS)

    return registros, ejemplos_guardados


def crear_resumen(registros, ejemplos_guardados):
    resumen = {
        "run_id": RUN_ID,
        "n_estudios_validacion": len(registros),
        "regla_dice": (
            "Dice calculado por estudio en 3D, acumulando todos los cortes. "
            "Si referencia y predicción están vacías para una clase, se "
            "registra NaN y se excluye de la media."
        ),
        "ejemplos_visuales_guardados": ejemplos_guardados,
        "clases": {},
    }

    for clase in range(1, 4):
        columna = f"dice_clase_{clase}"
        valores = np.array(
            [r[columna] for r in registros], dtype=float
        )
        validos = valores[np.isfinite(valores)]

        resumen["clases"][str(clase)] = {
            "n_estudios_con_dice_definido": int(len(validos)),
            "media_dice": (
                float(np.mean(validos)) if len(validos) else None
            ),
            "mediana_dice": (
                float(np.median(validos)) if len(validos) else None
            ),
            "desviacion_estandar_dice": (
                float(np.std(validos, ddof=1))
                if len(validos) > 1 else None
            ),
        }

    macros = np.array(
        [r["dice_macro_clases_presentes"] for r in registros],
        dtype=float,
    )
    macros = macros[np.isfinite(macros)]

    resumen["macro_por_estudio"] = {
        "n_estudios_con_dice_definido": int(len(macros)),
        "media": float(np.mean(macros)) if len(macros) else None,
        "mediana": float(np.median(macros)) if len(macros) else None,
    }

    RESUMEN.write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    fijar_semilla(SEMILLA)
    torch.set_num_threads(NUM_HILOS)

    if not MANIFEST.exists():
        raise FileNotFoundError(f"No existe el manifiesto: {MANIFEST}")

    comprobar_salidas_libres()
    SALIDA.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(
        MANIFEST,
        dtype={"sample_id": str, "subject_key": str},
    )
    if (manifest["split"] == "test").any():
        raise ValueError(
            "El manifiesto del piloto contiene test. Se cancela la ejecución."
        )

    mapa_pacientes = dict(
        zip(manifest["sample_id"], manifest["subject_key"])
    )

    dispositivo = torch.device("cpu")

    train = Dataset2D("train", manifest_path=MANIFEST)
    validation = Dataset2D("validation", manifest_path=MANIFEST)

    configuracion = {
        "run_id": RUN_ID,
        "semilla": SEMILLA,
        "epocas": EPOCAS,
        "batch_size": BATCH_SIZE,
        "tasa_aprendizaje": TASA_APRENDIZAJE,
        "hilos_cpu": NUM_HILOS,
        "dispositivo": str(dispositivo),
        "modalidades": list(MODALIDADES),
        "fraccion_pacientes": 0.30,
        "pacientes_entrenamiento": int(
            manifest.loc[manifest["split"] == "train", "subject_key"].nunique()
        ),
        "pacientes_validacion": int(
            manifest.loc[
                manifest["split"] == "validation", "subject_key"
            ].nunique()
        ),
        "estudios_entrenamiento": len(train.estudios),
        "estudios_validacion": len(validation.estudios),
        "cortes_entrenamiento": len(train),
        "cortes_validacion": len(validation),
        "modelo": "UNet2D",
        "base": BASE,
        "perdida": "CrossEntropy + Dice suave para clases 1, 2 y 3",
        "normalizacion": (
            "Por modalidad y estudio: media y desviación estándar "
            "de vóxeles no nulos; ceros preservados."
        ),
        "evaluacion": (
            "Dice por clase y estudio completo, acumulando cortes axiales."
        ),
        "test": "Reservado; no utilizado.",
    }

    CONFIGURACION.write_text(
        json.dumps(configuracion, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    modelo = UNet2D(
        canales_entrada=4,
        clases_salida=4,
        base=BASE,
    ).to(dispositivo)

    optimizador = torch.optim.Adam(
        modelo.parameters(),
        lr=TASA_APRENDIZAJE,
    )
    perdida_ce = nn.CrossEntropyLoss()

    lotes = LotesPorEstudio(
        train,
        batch_size=BATCH_SIZE,
        shuffle=True,
        seed=SEMILLA,
    )
    cargador = DataLoader(
        train,
        batch_sampler=lotes,
        num_workers=0,
    )

    historial = []
    inicio_total = time.time()

    print("\nINICIO DEL PILOTO", flush=True)
    print(json.dumps(configuracion, indent=2, ensure_ascii=False), flush=True)
    print(f"Lotes de entrenamiento por época: {len(cargador)}", flush=True)

    for epoca in range(1, EPOCAS + 1):
        modelo.train()
        suma_perdida = 0.0
        numero_lotes = 0
        inicio_epoca = time.time()

        for numero, (x, y) in enumerate(cargador, start=1):
            x = x.to(dispositivo)
            y = y.to(dispositivo)

            optimizador.zero_grad(set_to_none=True)
            logits = modelo(x)
            perdida = perdida_ce(logits, y) + perdida_dice(logits, y)
            perdida.backward()
            optimizador.step()

            suma_perdida += float(perdida.item())
            numero_lotes += 1

            if numero % 100 == 0:
                print(
                    f"Época {epoca}/{EPOCAS} | "
                    f"Lote {numero}/{len(cargador)} | "
                    f"Pérdida media: {suma_perdida / numero_lotes:.5f} | "
                    f"Tiempo de época: "
                    f"{(time.time() - inicio_epoca) / 60:.1f} min",
                    flush=True,
                )

        perdida_media = suma_perdida / max(numero_lotes, 1)
        tiempo_epoca = time.time() - inicio_epoca

        guardar_checkpoint(
            modelo,
            optimizador,
            epoca,
            configuracion,
            perdida_media,
        )

        historial.append({
            "epoca": epoca,
            "perdida_entrenamiento": perdida_media,
            "lotes_entrenamiento": numero_lotes,
            "tiempo_epoca_segundos": tiempo_epoca,
            "tiempo_total_segundos": time.time() - inicio_total,
        })
        guardar_csv(historial, HISTORIAL)

        print(
            f"Época {epoca}/{EPOCAS} completada | "
            f"Pérdida={perdida_media:.5f} | "
            f"Tiempo={tiempo_epoca / 60:.1f} min | "
            f"Checkpoint guardado.",
            flush=True,
        )

    print("\nINICIANDO EVALUACIÓN FINAL", flush=True)
    registros, ejemplos_guardados = evaluar(
        modelo, validation, dispositivo, mapa_pacientes
    )
    crear_resumen(registros, ejemplos_guardados)

    print("\nPILOTO TERMINADO", flush=True)
    print("Checkpoint:", CHECKPOINT)
    print("Historial:", HISTORIAL)
    print("Métricas por estudio:", METRICAS_CASO)
    print("Resultados requeridos:", RESULTADOS)
    print("Configuración:", CONFIGURACION)
    print("Resumen:", RESUMEN)
    print("Figuras:", FIGURAS)
    print(f"Tiempo total: {(time.time() - inicio_total) / 3600:.2f} horas")


if __name__ == "__main__":
    main()
