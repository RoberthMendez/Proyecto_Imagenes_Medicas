# 4. Preparación de imágenes

La preparación convierte los cinco archivos de un estudio en una entrada numérica consistente para la red. Las cuatro modalidades MRI se normalizan y se apilan como canales; la máscara se mantiene aparte como respuesta correcta.

## 1. Carga de los volúmenes

`codigo/segmentacion/cargar_imagenes.py` busca exactamente un archivo para cada sufijo `t1n`, `t1c`, `t2w`, `t2f` y `seg` dentro de la carpeta del estudio. Usa `nibabel` para abrir cada NIfTI y comprueba que:

- todos sean volúmenes tridimensionales;
- tengan la misma forma;
- sus matrices `affine` sean compatibles;
- no haya valores NaN o infinitos;
- la máscara solo contenga las etiquetas enteras `0`, `1`, `2` y `3`.

Las modalidades se convierten a `float32` y la máscara a `uint8`. El cargador devuelve también la forma y la geometría espacial de referencia. Si falta un archivo, hay más de uno con el mismo sufijo o las formas/geometrías no coinciden, detiene la carga con un error.

La auditoría de estudios usa una tolerancia de `1e-3` al comparar matrices espaciales. El cargador reutilizable que se emplea para preparar los datos compara con `rtol=1e-5` y `atol=1e-5`; esa segunda comprobación es más estricta.

## 2. Normalización de intensidades

Las intensidades son números que indican la señal registrada por el escáner. **Normalizar** significa reescalarlas para que magnitudes distintas entre modalidades o estudios sean más comparables para la red. No transforma la máscara.

Para cada modalidad y estudio, `normalizar_modalidad`:

1. identifica los vóxeles cuyo valor no es cero;
2. calcula la media y la desviación estándar de esos vóxeles;
3. resta la media y divide por la desviación estándar;
4. mantiene en cero las posiciones que ya eran cero.

Si no hay vóxeles no nulos, devuelve una matriz de ceros. Si la desviación estándar es casi cero (`<= 1e-8`), resta la media sin dividir. La operación usa los vóxeles no nulos del volumen completo, no calcula estadísticas por corte ni usa estadísticas de validación para transformar entrenamiento.

Ejemplo conceptual: si una MRI tiene fondo codificado como cero y valores cerebrales de media 100 y desviación 20, un valor cerebral 120 se transforma en `(120 - 100) / 20 = 1`; los ceros de fondo permanecen en cero.

## 3. Cortes axiales y canales

El conjunto `Dataset2D` indexa cada corte sobre el tercer eje y selecciona `volumen[:, :, z]`. A ese plano lo trata como corte axial. No reorienta los volúmenes ni adapta el orden de ejes según `affine`, así que el flujo depende de la orientación guardada por el dataset.

La red usa 2D para reducir el coste de memoria y cómputo respecto a procesar el volumen completo en 3D. La contrapartida es que la U-Net procesa cada plano por separado y no recibe contexto directo de los cortes vecinos.

Para un corte, las modalidades se apilan en este orden:

```text
canal 0: t1n
canal 1: t1c
canal 2: t2w
canal 3: t2f
```

Si el volumen tiene forma `(240, 240, 155)`, cada entrada tiene forma `(4, 240, 240)` y su máscara `(240, 240)`. Al agrupar dos cortes, las formas que recibe la red son:

```text
MRI:     (2, 4, 240, 240)   # lote, canales, alto, ancho
máscara: (2, 240, 240)     # lote, alto, ancho; valores 0–3
```

La red devuelve logits con forma `(2, 4, 240, 240)`: cuatro puntuaciones por píxel. Durante la evaluación, `argmax` convierte esas puntuaciones en una etiqueta de clase. Los volúmenes se reconstruyen guardando la predicción de cada índice `z` en su posición correspondiente.

## 4. Cómo pasa un estudio al modelo

Imagina las cuatro MRI como cuatro láminas transparentes alineadas. El cargador comprueba que coincidan; la normalización ajusta sus intensidades sin mover los vóxeles; el conjunto toma una lámina de cada modalidad en el mismo índice `z` y las apila como cuatro canales. La máscara aporta la etiqueta correcta de cada píxel. El modelo compara sus cuatro salidas por píxel con esa máscara durante el entrenamiento.

El conjunto conserva en memoria el estudio que está utilizando y agrupa lotes de cortes por estudio. Esto evita volver a cargar el volumen en cada corte consecutivo, aunque un estudio completo aún ocupa memoria.

## Código relacionado y comprobaciones

- `cargar_imagenes.py`: carga y valida los cinco volúmenes.
- `preparar_imagenes.py`: normaliza las cuatro modalidades y conserva las etiquetas de referencia.
- `conjunto_cortes_2d.py`: crea índices de cortes, tensores y lotes por estudio.
- `revisar_normalizacion.py`: genera estadísticas para 2 estudios de entrenamiento y 5 de validación.

Comprobación de un estudio:

```powershell
python -m codigo.segmentacion.cargar_imagenes
python -m codigo.segmentacion.preparar_imagenes
```

Los informes y las condiciones de sobrescritura están descritos en [resultados y evaluación](06_resultados_y_evaluacion.md) y [reproducción completa](08_reproduccion_completa.md).
