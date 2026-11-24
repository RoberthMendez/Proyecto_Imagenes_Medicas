"""
Métricas 3D a partir de predicciones guardadas (.npz) y referencias (.nii.gz).

Por estudio calcula, en 3D:
  - Tumor completo (unión de etiquetas 1, 2 y 3): Dice y HD95 (mm).
  - Cada clase 1, 2, 3: Dice y HD95 (mm).
Además recalcula el Dice por clase y lo compara con el CSV original como
verificación. Genera una tabla por estudio, otra por paciente (media de sus
estudios) y un resumen JSON.

Reglas:
  - Ambas máscaras vacías  -> Dice NaN, HD95 NaN (se excluye de las medias).
  - Solo una vacía         -> Dice 0, HD95 NaN (indefinido).
  - HD95: superficie = voxeles de la máscara menos su erosión (conectividad
    6); distancias euclídeas en mm con el espaciado del NIfTI.
    modo "agrupado": percentil 95 de las distancias de ambas direcciones
    juntas. modo "maximo": máximo de los dos percentiles 95.

Uso (desde la raíz del proyecto):
    python -u -m codigo.evaluacion.calcular_metricas_3d \
        --metricas resultados/prueba_linea_base/metricas_por_estudio.csv \
        --salida resultados/prueba_linea_base/metricas_3d \
        --modo-hd95 agrupado
"""
import argparse
import json
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy import ndimage as ndi

RAIZ = Path(__file__).resolve().parents[2]
CLASES = (1, 2, 3)
ESTRUCTURA = ndi.generate_binary_structure(3, 1)


def dice(a, b):
    sa, sb = int(a.sum()), int(b.sum())
    if sa == 0 and sb == 0:
        return float("nan")
    if sa == 0 or sb == 0:
        return 0.0
    return 2.0 * int(np.logical_and(a, b).sum()) / (sa + sb)


def superficie(m):
    return m & ~ndi.binary_erosion(m, structure=ESTRUCTURA, border_value=0)


def hd95(a, b, espaciado, modo):
    if not a.any() or not b.any():
        return float("nan")
    sa, sb = superficie(a), superficie(b)
    d_a = ndi.distance_transform_edt(~sa, sampling=espaciado)[sb]
    d_b = ndi.distance_transform_edt(~sb, sampling=espaciado)[sa]
    if modo == "agrupado":
        return float(np.percentile(np.concatenate([d_a, d_b]), 95))
    return float(max(np.percentile(d_a, 95), np.percentile(d_b, 95)))


def ruta(texto):
    return RAIZ / str(texto).replace("\\", "/")


def estadisticas(serie):
    x = pd.to_numeric(serie, errors="coerce").dropna()
    if len(x) == 0:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "media": float(x.mean()),
        "mediana": float(x.median()),
        "desviacion_estandar": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
        "minimo": float(x.min()),
        "maximo": float(x.max()),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metricas", required=True,
                   help="metricas_por_estudio.csv con columnas "
                        "sample_id, group_key, referencia, prediccion.")
    p.add_argument("--salida", required=True)
    p.add_argument("--modo-hd95", default="agrupado",
                   choices=["agrupado", "maximo"])
    p.add_argument("--max-estudios", type=int, default=None)
    a = p.parse_args()

    tabla = pd.read_csv(ruta(a.metricas), dtype={"sample_id": str,
                                                  "group_key": str})
    if a.max_estudios:
        tabla = tabla.head(a.max_estudios)
    salida = ruta(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    filas = []
    dif_max = 0.0
    inicio = time.time()
    for i, fila in enumerate(tabla.itertuples(index=False), 1):
        img = nib.load(ruta(fila.referencia))
        ref = np.rint(np.asarray(img.dataobj)).astype(np.int16)
        pred = np.load(ruta(fila.prediccion))["prediccion"].astype(np.int16)
        if ref.shape != pred.shape:
            raise ValueError(
                f"{fila.sample_id}: forma {ref.shape} (ref) distinta de "
                f"{pred.shape} (pred)"
            )
        esp = tuple(float(z) for z in img.header.get_zooms()[:3])

        reg = {"sample_id": fila.sample_id, "group_key": fila.group_key}
        r_t, p_t = ref > 0, pred > 0
        reg["dice_tumor_completo"] = dice(r_t, p_t)
        reg["hd95_tumor_completo_mm"] = hd95(r_t, p_t, esp, a.modo_hd95)
        for k in CLASES:
            r_k, p_k = ref == k, pred == k
            d = dice(r_k, p_k)
            reg[f"dice_clase_{k}"] = d
            reg[f"hd95_clase_{k}_mm"] = hd95(r_k, p_k, esp, a.modo_hd95)
            previo = getattr(fila, f"dice_clase_{k}")
            if not (np.isnan(d) and pd.isna(previo)):
                dif_max = max(dif_max, abs(d - previo))
        filas.append(reg)
        if i % 10 == 0 or i == len(tabla):
            print(f"{i}/{len(tabla)} | {fila.sample_id} | "
                  f"Dice tumor completo={reg['dice_tumor_completo']:.4f} | "
                  f"{(time.time() - inicio) / 60:.1f} min", flush=True)

    por_estudio = pd.DataFrame(filas)
    por_estudio.to_csv(salida / "metricas_3d_por_estudio.csv", index=False)

    por_paciente = por_estudio.drop(columns=["sample_id"]).groupby(
        "group_key", as_index=False).mean(numeric_only=True)
    por_paciente.to_csv(salida / "metricas_3d_por_paciente.csv", index=False)

    columnas = [c for c in por_estudio.columns
                if c.startswith(("dice_", "hd95_"))]
    resumen = {
        "modo_hd95": a.modo_hd95,
        "n_estudios": int(len(por_estudio)),
        "n_pacientes": int(len(por_paciente)),
        "verificacion_dice_max_dif_vs_csv_original": dif_max,
        "por_estudio": {c: estadisticas(por_estudio[c]) for c in columnas},
        "por_paciente": {c: estadisticas(por_paciente[c]) for c in columnas},
    }
    (salida / "resumen_metricas_3d.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nMÉTRICAS 3D TERMINADAS")
    print(f"Diferencia máxima de Dice vs CSV original: {dif_max:.2e}")
    for c in columnas:
        s = resumen["por_estudio"][c]
        if s["n"]:
            print(f"{c}: n={s['n']} media={s['media']:.4f} "
                  f"mediana={s['mediana']:.4f} máx={s['maximo']:.4f}")


if __name__ == "__main__":
    main()