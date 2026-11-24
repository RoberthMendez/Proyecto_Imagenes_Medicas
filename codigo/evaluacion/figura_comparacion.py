"""
Figura de comparación: FLAIR | referencia | predicción (y opcionalmente una
segunda predicción) en el mismo corte axial, para varios estudios.

El corte se elige automáticamente: el axial con más voxeles de tumor en la
referencia. Todas las columnas de una fila usan el mismo corte y la misma
orientación.

Uso (desde la raíz del proyecto):
    python -u -m codigo.evaluacion.figura_comparacion \
        --metricas resultados/prueba_linea_base/metricas_por_estudio.csv \
        --ids BraTS-GLI-01480-000 BraTS-GLI-00134-000 \
        --salida resultados/figuras_informe/test_casos.png

Para comparar dos versiones en validación añade:
        --metricas-b resultados/modelo_variante_peso3/metricas_por_estudio.csv \
        --etiqueta-a "Línea base" --etiqueta-b "Variante (peso 3)"
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

RAIZ = Path(__file__).resolve().parents[2]
COLORES = ["#D55E00", "#009E73", "#F0E442"]  # clases 1, 2, 3
NOMBRES = ["1 NCR/NET", "2 Edema", "3 Realzante"]
CMAP = ListedColormap(["none"] + COLORES)


def ruta(texto):
    return RAIZ / str(texto).replace("\\", "/")


def dice(a, b):
    sa, sb = int(a.sum()), int(b.sum())
    if sa == 0 and sb == 0:
        return float("nan")
    if sa == 0 or sb == 0:
        return 0.0
    return 2.0 * int(np.logical_and(a, b).sum()) / (sa + sb)


def orientar(corte):
    return np.rot90(corte)


def panel(ax, fondo, mascara, titulo):
    ax.imshow(orientar(fondo), cmap="gray", vmin=0, vmax=1)
    if mascara is not None:
        m = orientar(mascara).astype(float)
        ax.imshow(np.ma.masked_equal(m, 0), cmap=CMAP, vmin=0, vmax=3,
                  interpolation="nearest", alpha=0.75)
    ax.set_title(titulo, fontsize=8)
    ax.axis("off")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metricas", required=True)
    p.add_argument("--ids", nargs="+", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--metricas-b", default=None)
    p.add_argument("--etiqueta-a", default="Predicción")
    p.add_argument("--etiqueta-b", default="Predicción B")
    a = p.parse_args()

    ta = pd.read_csv(ruta(a.metricas), dtype={"sample_id": str}
                     ).set_index("sample_id")
    tb = None
    if a.metricas_b:
        tb = pd.read_csv(ruta(a.metricas_b), dtype={"sample_id": str}
                         ).set_index("sample_id")

    columnas = 4 if tb is not None else 3
    fig, ejes = plt.subplots(len(a.ids), columnas,
                             figsize=(3.1 * columnas, 3.3 * len(a.ids)),
                             squeeze=False)

    for i, sid in enumerate(a.ids):
        fila = ta.loc[sid]
        seg = nib.load(ruta(fila["referencia"]))
        ref = np.rint(np.asarray(seg.dataobj)).astype(np.int16)
        flair_ruta = str(fila["referencia"]).replace("-seg.nii.gz",
                                                     "-t2f.nii.gz")
        flair = np.asarray(nib.load(ruta(flair_ruta)).dataobj, dtype=float)
        pred_a = np.load(ruta(fila["prediccion"]))["prediccion"]
        pred_b = None
        if tb is not None:
            pred_b = np.load(ruta(tb.loc[sid]["prediccion"]))["prediccion"]

        z = int(np.argmax((ref > 0).sum(axis=(0, 1))))
        cerebro = np.argwhere(flair[:, :, z] > 0)
        (x0, y0), (x1, y1) = cerebro.min(0), cerebro.max(0)
        x0, y0 = max(x0 - 4, 0), max(y0 - 4, 0)
        sl = (slice(x0, x1 + 5), slice(y0, y1 + 5))

        valores = flair[:, :, z][flair[:, :, z] > 0]
        lo, hi = np.percentile(valores, [1, 99])
        fondo = np.clip((flair[:, :, z] - lo) / max(hi - lo, 1e-6), 0, 1)

        def recorte(m):
            return m[:, :, z][sl]

        def titulo(nombre, pred):
            dt = dice(ref > 0, pred > 0)
            return f"{nombre}\nDice tumor completo {dt:.3f}"

        panel(ejes[i][0], fondo[sl], None, f"{sid}  (corte z={z})\nFLAIR")
        panel(ejes[i][1], fondo[sl], recorte(ref), "Referencia")
        panel(ejes[i][2], fondo[sl], recorte(pred_a),
              titulo(a.etiqueta_a, pred_a))
        if tb is not None:
            panel(ejes[i][3], fondo[sl], recorte(pred_b),
                  titulo(a.etiqueta_b, pred_b))

    fig.legend(handles=[Patch(color=c, label=n)
                        for c, n in zip(COLORES, NOMBRES)],
               loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    salida = ruta(a.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    print("Figura guardada:", salida)


if __name__ == "__main__":
    main()