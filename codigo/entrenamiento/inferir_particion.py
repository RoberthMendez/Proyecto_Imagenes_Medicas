"""
Inferencia con una versión CONGELADA sobre una partición (validación o test).

- Reutiliza la evaluación del piloto (entrenar_piloto.evaluar) sin
  modificarla: reconstruye la máscara 3D de cada estudio apilando los
  cortes axiales en su orden original, guarda la predicción (.npz) y calcula
  Dice por clase y estudio.
- No entrena ni ajusta nada. Solo carga el checkpoint indicado.
- El Dice 3D de tumor completo y el HD95 se calculan aparte, a partir de las
  predicciones guardadas.

Uso (desde la raíz del proyecto), por ejemplo para test:
    python -u -m codigo.entrenamiento.inferir_particion \
        --checkpoint resultados/modelo_piloto/unet2d_piloto_30pct.pth \
        --run-id prueba_piloto_30pct_2epocas \
        --salida resultados/prueba_linea_base \
        --particion test --confirmo-version-congelada
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import pandas as pd
import torch

import codigo.entrenamiento.entrenar_piloto as base
from codigo.segmentacion.conjunto_cortes_2d import Dataset2D, MANIFEST
from codigo.segmentacion.red_unet import UNet2D


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--particion", default="test",
                   choices=["validation", "test"])
    p.add_argument("--hilos", type=int, default=4)
    p.add_argument("--max-estudios", type=int, default=None,
                   help="Solo para pruebas rápidas.")
    p.add_argument("--manifest", default=None,
                   help="Manifiesto para el dataset (por defecto, el "
                        "completo). Solo para reproducir la línea base "
                        "en validación.")
    p.add_argument("--confirmo-version-congelada", action="store_true",
                   help="Obligatorio para test: confirma que la versión "
                        "se eligió con validación y no se reajustará.")
    a = p.parse_args()

    if a.particion == "test" and not a.confirmo_version_congelada:
        raise SystemExit(
            "Para evaluar en TEST hay que confirmar que la versión ya está "
            "congelada (elegida con validación): añade "
            "--confirmo-version-congelada."
        )

    checkpoint = Path(a.checkpoint)
    if not checkpoint.is_absolute():
        checkpoint = base.PROYECTO / checkpoint
    if not checkpoint.exists():
        raise FileNotFoundError(f"No existe el checkpoint: {checkpoint}")

    # Redirige las salidas de la evaluación del piloto.
    salida = base.PROYECTO / a.salida
    base.SALIDA = salida
    base.PREDICCIONES = salida / "predicciones"
    base.FIGURAS = salida / "ejemplos"
    base.CHECKPOINT = salida / "_no_usado.pth"
    base.HISTORIAL = salida / "_no_usado.csv"
    base.METRICAS_CASO = salida / "metricas_por_estudio.csv"
    base.RESULTADOS = salida / "resultados.csv"
    base.CONFIGURACION = salida / "configuracion.json"
    base.RESUMEN = salida / "resumen_metricas.json"
    base.RUN_ID = a.run_id

    base.comprobar_salidas_libres()
    salida.mkdir(parents=True, exist_ok=True)

    torch.set_num_threads(a.hilos)
    dispositivo = torch.device("cpu")

    # El mapa estudio -> paciente siempre sale del manifiesto completo.
    manifest = pd.read_csv(
        MANIFEST, dtype={"sample_id": str, "subject_key": str}
    )
    mapa_pacientes = dict(zip(manifest["sample_id"], manifest["subject_key"]))

    manifest_dataset = (base.PROYECTO / a.manifest) if a.manifest else MANIFEST
    dataset = Dataset2D(a.particion, manifest_path=manifest_dataset,
                        max_estudios=a.max_estudios)

    estado = torch.load(checkpoint, map_location="cpu", weights_only=False)
    pesos = estado.get("modelo_state_dict", estado.get("modelo"))
    modelo = UNet2D(
        canales_entrada=4, clases_salida=4, base=base.BASE
    ).to(dispositivo)
    modelo.load_state_dict(pesos)

    configuracion = {
        "run_id": a.run_id,
        "particion": a.particion,
        "manifest": str(manifest_dataset.relative_to(base.PROYECTO))
        if Path(manifest_dataset).is_relative_to(base.PROYECTO)
        else str(manifest_dataset),
        "checkpoint": str(checkpoint.relative_to(base.PROYECTO))
        if checkpoint.is_relative_to(base.PROYECTO) else str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoca": estado.get("epoca"),
        "checkpoint_run_id": (estado.get("configuracion") or {}).get("run_id"),
        "estudios_evaluados": len(dataset.estudios),
        "pacientes_evaluados": len({mapa_pacientes.get(e)
                                    for e in dataset.estudios}),
        "cortes_evaluados": len(dataset),
        "modalidades": list(base.MODALIDADES),
        "batch_size": base.BATCH_SIZE,
        "hilos_cpu": a.hilos,
        "dispositivo": str(dispositivo),
        "version_python": platform.python_version(),
        "version_torch": torch.__version__,
        "nota": ("Inferencia con parámetros congelados; no se entrena ni se "
                 "ajusta nada con estos resultados."),
    }
    base.CONFIGURACION.write_text(
        json.dumps(configuracion, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(configuracion, indent=2, ensure_ascii=False),
          flush=True)

    inicio = time.time()
    registros, ejemplos = base.evaluar(
        modelo, dataset, dispositivo, mapa_pacientes
    )
    base.crear_resumen(registros, ejemplos)

    # El resumen del piloto habla de "validación"; se corrige la etiqueta.
    resumen = json.loads(base.RESUMEN.read_text(encoding="utf-8"))
    resumen["n_estudios_evaluados"] = resumen.pop("n_estudios_validacion")
    resumen["particion"] = a.particion
    base.RESUMEN.write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\nINFERENCIA TERMINADA", flush=True)
    print("Predicciones:", base.PREDICCIONES)
    print("Métricas por estudio:", base.METRICAS_CASO)
    print("Resumen:", base.RESUMEN)
    print(f"Tiempo: {(time.time() - inicio) / 60:.1f} min")


if __name__ == "__main__":
    main()