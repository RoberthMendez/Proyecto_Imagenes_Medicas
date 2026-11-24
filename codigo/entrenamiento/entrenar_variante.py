"""
Variante de la entrega final: igual al piloto (entrenar_piloto.py) salvo el
peso de la clase 1 en la Cross-Entropy.

- No modifica entrenar_piloto.py: reutiliza sus funciones (pérdida Dice,
  evaluación, resumen) para que la evaluación sea idéntica a la de la
  línea base.
- Guarda un checkpoint intermedio cada N lotes y puede reanudar.

Uso (desde la raíz del proyecto):
    python -u -m codigo.entrenamiento.entrenar_variante
"""
import argparse
import json
import platform
import time

import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Sampler

import codigo.entrenamiento.entrenar_piloto as base
from codigo.segmentacion.conjunto_cortes_2d import Dataset2D, LotesPorEstudio
from codigo.segmentacion.red_unet import UNet2D


class DesdeLote(Sampler):
    """Reanuda una época saltando los primeros `inicio` lotes sin cargar
    imágenes. El orden de los lotes es el mismo que sin interrupción."""

    def __init__(self, lotes, inicio=0):
        self.lotes = lotes
        self.inicio = inicio

    def __iter__(self):
        for n, lote in enumerate(iter(self.lotes)):
            if n >= self.inicio:
                yield lote

    def __len__(self):
        return len(self.lotes) - self.inicio


def guardar_intermedio(ruta, modelo, optimizador, epoca, lote, suma,
                       historial, tiempo_total, tiempo_epoca):
    temporal = ruta.with_suffix(".tmp")
    torch.save(
        {
            "modelo": modelo.state_dict(),
            "optimizador": optimizador.state_dict(),
            "epoca": epoca,
            "lote": lote,
            "suma_perdida": suma,
            "historial": historial,
            "tiempo_total": tiempo_total,
            "tiempo_epoca": tiempo_epoca,
        },
        temporal,
    )
    temporal.replace(ruta)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--peso-clase-1", type=float, default=3.0)
    p.add_argument("--run-id", default="variante_peso3_30pct_2epocas")
    p.add_argument("--salida", default="resultados/modelo_variante_peso3")
    p.add_argument("--cada-lotes", type=int, default=1000)
    p.add_argument("--epocas", type=int, default=base.EPOCAS)
    p.add_argument("--hilos", type=int, default=4)
    p.add_argument("--max-estudios", type=int, default=None,
                   help="Solo para pruebas rápidas.")
    a = p.parse_args()

    # Redirige las salidas del piloto a la carpeta de la variante.
    salida = base.PROYECTO / a.salida
    base.SALIDA = salida
    base.PREDICCIONES = salida / "predicciones_30pct"
    base.FIGURAS = salida / "ejemplos_validacion"
    base.CHECKPOINT = salida / "unet2d_variante_30pct.pth"
    base.HISTORIAL = salida / "historial_entrenamiento.csv"
    base.METRICAS_CASO = salida / "metricas_por_estudio.csv"
    base.RESULTADOS = salida / "resultados.csv"
    base.CONFIGURACION = salida / "configuracion.json"
    base.RESUMEN = salida / "resumen_metricas.json"
    base.RUN_ID = a.run_id

    intermedio = salida / "checkpoint_intermedio.pt"
    reanudando = intermedio.exists()
    if not reanudando:
        base.comprobar_salidas_libres()
    salida.mkdir(parents=True, exist_ok=True)

    base.fijar_semilla(base.SEMILLA)
    torch.set_num_threads(a.hilos)

    manifest = pd.read_csv(
        base.MANIFEST, dtype={"sample_id": str, "subject_key": str}
    )
    if (manifest["split"] == "test").any():
        raise ValueError("El manifiesto contiene test. Se cancela.")
    mapa_pacientes = dict(zip(manifest["sample_id"], manifest["subject_key"]))

    dispositivo = torch.device("cpu")
    train = Dataset2D("train", manifest_path=base.MANIFEST,
                      max_estudios=a.max_estudios)
    validation = Dataset2D("validation", manifest_path=base.MANIFEST,
                           max_estudios=a.max_estudios)

    pesos_ce = [1.0, a.peso_clase_1, 1.0, 1.0]
    configuracion = {
        "run_id": a.run_id,
        "linea_base": "piloto_30pct_2epocas",
        "cambio_principal": "peso de la clase 1 en la Cross-Entropy",
        "peso_clase_1": a.peso_clase_1,
        "pesos_cross_entropy": pesos_ce,
        "semilla": base.SEMILLA,
        "epocas": a.epocas,
        "batch_size": base.BATCH_SIZE,
        "tasa_aprendizaje": base.TASA_APRENDIZAJE,
        "hilos_cpu": a.hilos,
        "dispositivo": str(dispositivo),
        "modalidades": list(base.MODALIDADES),
        "fraccion_pacientes": 0.30,
        "estudios_entrenamiento": len(train.estudios),
        "estudios_validacion": len(validation.estudios),
        "cortes_entrenamiento": len(train),
        "cortes_validacion": len(validation),
        "modelo": "UNet2D",
        "base": base.BASE,
        "perdida": ("CrossEntropy con peso en la clase 1 + "
                    "Dice suave para clases 1, 2 y 3"),
        "normalizacion": (
            "Por modalidad y estudio: media y desviación estándar "
            "de vóxeles no nulos; ceros preservados."
        ),
        "evaluacion": (
            "Dice por clase y estudio completo, acumulando cortes axiales."
        ),
        "test": "Reservado; no utilizado.",
        "checkpoint_cada_lotes": a.cada_lotes,
        "version_python": platform.python_version(),
        "version_torch": torch.__version__,
    }
    if not base.CONFIGURACION.exists():
        base.CONFIGURACION.write_text(
            json.dumps(configuracion, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    modelo = UNet2D(
        canales_entrada=4, clases_salida=4, base=base.BASE
    ).to(dispositivo)
    optimizador = torch.optim.Adam(
        modelo.parameters(), lr=base.TASA_APRENDIZAJE
    )
    perdida_ce = nn.CrossEntropyLoss(weight=torch.tensor(pesos_ce))
    lotes = LotesPorEstudio(
        train, batch_size=base.BATCH_SIZE, shuffle=True, seed=base.SEMILLA
    )

    epoca_ini, lote_ini, suma_ini = 1, 0, 0.0
    historial, tiempo_previo, tiempo_epoca_previo = [], 0.0, 0.0
    if reanudando:
        estado = torch.load(intermedio, map_location="cpu",
                            weights_only=False)
        modelo.load_state_dict(estado["modelo"])
        optimizador.load_state_dict(estado["optimizador"])
        epoca_ini = estado["epoca"]
        lote_ini = estado["lote"]
        suma_ini = estado["suma_perdida"]
        historial = estado["historial"]
        tiempo_previo = estado["tiempo_total"]
        tiempo_epoca_previo = estado["tiempo_epoca"]
        print(f"REANUDANDO desde época {epoca_ini}, lote {lote_ini}",
              flush=True)

    print("\nINICIO DE LA VARIANTE", flush=True)
    print(json.dumps(configuracion, indent=2, ensure_ascii=False), flush=True)

    inicio_total = time.time() - tiempo_previo
    for epoca in range(epoca_ini, a.epocas + 1):
        modelo.train()
        primera = reanudando and epoca == epoca_ini
        suma = suma_ini if primera else 0.0
        hechos = lote_ini if primera else 0
        previo_epoca = tiempo_epoca_previo if primera else 0.0

        # La época e usa el orden de lotes de semilla + (e - 1), igual
        # que el piloto.
        lotes.epoca = epoca - 1
        cargador = DataLoader(
            train, batch_sampler=DesdeLote(lotes, hechos), num_workers=0
        )
        total_lotes = len(lotes)
        inicio_epoca = time.time()
        hechos_ini = hechos

        for x, y in cargador:
            x = x.to(dispositivo)
            y = y.to(dispositivo)

            optimizador.zero_grad(set_to_none=True)
            logits = modelo(x)
            perdida = perdida_ce(logits, y) + base.perdida_dice(logits, y)
            perdida.backward()
            optimizador.step()

            suma += float(perdida.item())
            hechos += 1

            if hechos % 100 == 0:
                ritmo = (time.time() - inicio_epoca) / (hechos - hechos_ini)
                restante_h = ((total_lotes - hechos)
                              + (a.epocas - epoca) * total_lotes) * ritmo / 3600
                print(
                    f"Época {epoca}/{a.epocas} | Lote {hechos}/{total_lotes} "
                    f"| Pérdida media: {suma / hechos:.5f} | "
                    f"{ritmo:.2f} s/lote | Faltan ~{restante_h:.1f} h",
                    flush=True,
                )

            if hechos % a.cada_lotes == 0:
                guardar_intermedio(
                    intermedio, modelo, optimizador, epoca, hechos, suma,
                    historial, time.time() - inicio_total,
                    previo_epoca + time.time() - inicio_epoca,
                )

        perdida_media = suma / max(hechos, 1)
        tiempo_epoca = previo_epoca + time.time() - inicio_epoca

        base.guardar_checkpoint(
            modelo, optimizador, epoca, configuracion, perdida_media
        )
        historial.append({
            "epoca": epoca,
            "perdida_entrenamiento": perdida_media,
            "lotes_entrenamiento": hechos,
            "tiempo_epoca_segundos": tiempo_epoca,
            "tiempo_total_segundos": time.time() - inicio_total,
        })
        base.guardar_csv(historial, base.HISTORIAL)
        # Marca el inicio de la siguiente época (o el fin del entrenamiento).
        guardar_intermedio(
            intermedio, modelo, optimizador, epoca + 1, 0, 0.0, historial,
            time.time() - inicio_total, 0.0,
        )
        print(
            f"Época {epoca}/{a.epocas} completada | "
            f"Pérdida={perdida_media:.5f} | Tiempo={tiempo_epoca / 60:.1f} "
            "min | Checkpoint guardado.",
            flush=True,
        )

    print("\nINICIANDO EVALUACIÓN EN VALIDACIÓN", flush=True)
    registros, ejemplos = base.evaluar(
        modelo, validation, dispositivo, mapa_pacientes
    )
    base.crear_resumen(registros, ejemplos)

    print("\nVARIANTE TERMINADA", flush=True)
    print("Checkpoint:", base.CHECKPOINT)
    print("Métricas por estudio:", base.METRICAS_CASO)
    print("Resumen:", base.RESUMEN)
    print(f"Tiempo total: {(time.time() - inicio_total) / 3600:.2f} horas")


if __name__ == "__main__":
    main()