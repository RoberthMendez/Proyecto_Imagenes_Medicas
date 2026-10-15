# 6. Resultados y evaluación

## Qué significa Dice

Dice mide cuánto se solapan dos regiones: la máscara de referencia y la predicción. Para una clase dada:

```text
Dice = 2 × vóxeles compartidos / (vóxeles de referencia + vóxeles predichos)
```

Un valor 1 indica coincidencia completa; 0 indica que no hubo solapamiento. Un valor alto no garantiza por sí solo que todos los bordes sean clínicamente adecuados.

## Cómo se calculó en este proyecto

El script de entrenamiento recorre todos los cortes de cada estudio de validación, guarda la clase con mayor puntuación por píxel y reconstruye la máscara 3D. Después suma intersecciones y tamaños de las regiones de cada clase a través de todo el volumen. Calcula Dice para las clases tumorales 1, 2 y 3; no incluye la clase fondo en esas métricas.

Si referencia y predicción están vacías para una clase, el denominador es cero y se registra `NaN`. Esa clase se excluye del promedio de ese estudio para no subir la métrica por una clase que no estaba presente. Si la referencia está vacía pero hay vóxeles predichos, el Dice es 0 y sí cuenta.

El **macro por estudio** es la media aritmética de los Dice definidos para las clases 1–3 de ese estudio. El macro general es la media de esos valores por estudio. Así, cada estudio contribuye una vez, y no se agregan primero todos los vóxeles de todos los pacientes. No se calculó Dice global por vóxel ni otras métricas como Hausdorff.

## Valores guardados del piloto

El archivo `resultados/modelo_piloto/resumen_metricas.json` resume **56 estudios de validación** del piloto:

| Clase evaluada | Estudios con Dice definido | Media | Mediana | Desviación estándar entre estudios |
|---|---:|---:|---:|---:|
| 1 | 55 | 0,6214 | 0,7241 | 0,3062 |
| 2 | 56 | 0,7346 | 0,8090 | 0,2096 |
| 3 | 55 | 0,7762 | 0,8636 | 0,2188 |
| Macro por estudio | 56 | 0,7024 | 0,7627 | No se registra |

Entre los estudios evaluados, `BraTS-GLI-00281-000` tuvo el macro más alto (0,9421) y `BraTS-GLI-00675-001` el más bajo (0,0000). En el caso de menor puntuación, las clases 1 y 3 quedaron indefinidas y se omitieron; la clase 2 tuvo Dice 0. Estos extremos describen únicamente esta validación piloto y no permiten concluir cómo se comportaría el modelo con pacientes nuevos o en prueba.

## Historial de entrenamiento

`resultados/modelo_piloto/historial_entrenamiento.csv` tiene una fila por época y estas columnas:

| Columna | Interpretación |
|---|---|
| `epoca` | Número de pasada completa por los cortes de entrenamiento. |
| `perdida_entrenamiento` | Media de la suma de Cross-Entropy y Dice suave para los lotes de esa época. Menor indica menor pérdida según esa función; por sí sola no mide generalización. |
| `lotes_entrenamiento` | Número de lotes procesados en la época. |
| `tiempo_epoca_segundos` | Duración de la época. |
| `tiempo_total_segundos` | Tiempo acumulado desde el inicio del bucle de entrenamiento hasta guardar esa fila. |

El historial registra una pérdida de entrenamiento de 0,7658 en la primera época y 0,6359 en la segunda. No incluye pérdida de validación, y dos puntos no permiten afirmar que el entrenamiento haya convergido. La segunda fila registra 15.209 segundos acumulados hasta terminar la segunda época; el tiempo de evaluación se ejecuta después.

## Archivos y ubicaciones

| Ruta | Contenido |
|---|---|
| `resultados/modelo_piloto/configuracion.json` | Semilla, épocas, lote, tasa de aprendizaje, dispositivo, modalidades, conteos, pérdida y regla de evaluación. |
| `resultados/modelo_piloto/metricas_por_estudio.csv` | Una fila por estudio evaluado, conteos de referencia/predicción por clase, Dice, macro, rutas y `run_id`. |
| `resultados/modelo_piloto/resultados.csv` | Resumen tabular con `sample_id`, paciente (`group_key`), referencia, predicción, métrica y `run_id`. |
| `resultados/modelo_piloto/resumen_metricas.json` | Medias, medianas, desviaciones, número de casos válidos y regla para clases vacías. |
| `resultados/modelo_piloto/ejemplos_validacion/` | Tres PNG con una imagen T1c, máscara real y predicción del mismo corte. |
| `resultados/modelo_piloto/predicciones_30pct/` | Salida `.npz` por estudio; cada archivo guarda el arreglo 3D `prediccion`. Los `.npz` están ignorados por Git. |
| `resultados/modelo_piloto/unet2d_piloto_30pct.pth` | Checkpoint del modelo y optimizador. Los `.pth` están ignorados por Git. |

Las figuras actualmente versionadas contienen cortes MRI y máscaras de estudios identificados por pseudónimo. La posibilidad de redistribuir el dataset o esas figuras no se confirmó; antes de publicar el repositorio hay que revisar las condiciones del proveedor.

## Alcance y limitaciones

- La evaluación cubre 56 estudios de validación seleccionados para el piloto, no los 185 estudios completos de validación.
- Entrenamiento usó 238 pacientes y dos épocas en CPU; no se seleccionó checkpoint con una búsqueda en validación.
- La partición de prueba tiene 170 pacientes y 188 estudios, y no se utilizó.
- Las auditorías validan lectura, geometría y valores esperados, pero no revisan clínicamente los contornos.
- La U-Net procesa cada corte de forma independiente, y la métrica es solapamiento volumétrico por clase; no evalúa todas las propiedades de una segmentación.

Por ello, 0,7024 es el Dice macro promedio guardado para este piloto de validación. No es una puntuación de prueba, una comparación oficial del reto ni evidencia de utilidad clínica.

## Enlaces relacionados

- [Modelo y entrenamiento](05_modelo_y_entrenamiento.md)
- [Preparación de imágenes](04_preparacion_de_imagenes.md)
- [Reproducción completa](08_reproduccion_completa.md)
