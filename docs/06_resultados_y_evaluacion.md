# 6. Resultados y evaluación

## Qué significa Dice

Dice mide cuánto se solapan dos regiones: la máscara de referencia y la predicción. Para una clase dada:

```text
Dice = 2 × vóxeles compartidos / (vóxeles de referencia + vóxeles predichos)
```

Un valor 1 indica coincidencia completa; 0 indica que no hubo solapamiento. Un valor alto no garantiza por sí solo que todos los bordes sean clínicamente adecuados.

## Qué significa HD95

El **HD95** (distancia de Hausdorff al percentil 95) mide qué tan lejos quedan los bordes de la predicción de los bordes de la referencia, en milímetros. Menor es mejor; 0 indicaría bordes coincidentes.

En este proyecto, la superficie de cada máscara son sus vóxeles que desaparecen al erosionarla una vez (conectividad 6). Para cada vóxel de superficie de una máscara se mide la distancia euclídea al borde más cercano de la otra, usando el espaciado del NIfTI. Se juntan las distancias de ambas direcciones (predicción → referencia y referencia → predicción) y se toma su percentil 95. Es el modo `agrupado` de `calcular_metricas_3d.py` y reproduce los valores del E2 para la validación de la línea base. El script también ofrece el modo `maximo` (el mayor de los dos percentiles 95 direccionales), que no se usó en los resultados de este documento.

Dice y HD95 se complementan: Dice resume el volumen compartido, y HD95 es sensible a regiones predichas lejos del tumor, aunque sean pequeñas.

## Cómo se calculó en este proyecto

El script de entrenamiento recorre todos los cortes de cada estudio de validación, guarda la clase con mayor puntuación por píxel y reconstruye la máscara 3D. Después suma intersecciones y tamaños de las regiones de cada clase a través de todo el volumen. Calcula Dice para las clases tumorales 1, 2 y 3; no incluye la clase fondo en esas métricas. `inferir_particion.py` reutiliza esa misma evaluación para la partición de prueba.

Si referencia y predicción están vacías para una clase, el denominador es cero y se registra `NaN`. Esa clase se excluye del promedio de ese estudio para no subir la métrica por una clase que no estaba presente. Si la referencia está vacía pero hay vóxeles predichos, el Dice es 0 y sí cuenta.

El **macro por estudio** es la media aritmética de los Dice definidos para las clases 1–3 de ese estudio. El macro general es la media de esos valores por estudio. Así, cada estudio contribuye una vez, y no se agregan primero todos los vóxeles de todos los pacientes. No se calculó Dice global por vóxel.

### Métricas 3D: tumor completo, clases y HD95

`codigo/evaluacion/calcular_metricas_3d.py` lee las predicciones `.npz` guardadas y las máscaras de referencia, y calcula por estudio, en 3D:

- **Tumor completo:** la unión de las etiquetas 1, 2 y 3. Un vóxel es tumor si su etiqueta es mayor que 0, tanto en la referencia como en la predicción. No importa si la clase dentro del tumor es correcta.
- **Cada clase 1, 2 y 3** por separado.

Para cada región calcula Dice y HD95 con estas reglas:

| Situación | Dice | HD95 |
|---|---|---|
| Referencia y predicción con vóxeles | Definido | Definido |
| Solo una de las dos vacía | 0 | Indefinido (`NaN`) |
| Ambas vacías | Indefinido (`NaN`) | Indefinido (`NaN`) |

Los valores indefinidos se excluyen de medias y medianas. El script también recalcula el Dice por clase y lo compara con el CSV original; la diferencia máxima registrada es del orden de 10⁻¹⁶, es decir, coinciden.

Además de la tabla por estudio, el script genera una tabla **por paciente**: la media de los estudios de cada paciente. Así, un paciente con varios estudios cuenta una sola vez.

### Qué significa cada n

Los n de las tablas cambian por métrica porque cuentan solo los valores definidos:

- **n de estudios del Dice:** estudios en los que la clase aparece en la referencia o en la predicción. Por ejemplo, en prueba la clase 1 tiene n = 186 de 188 porque en 2 estudios ni la referencia ni la predicción la contienen.
- **n de estudios del HD95:** estudios en los que la clase aparece en **ambas** máscaras. Siempre es menor o igual que el n del Dice. En prueba, la clase 1 tiene n = 179: a los 2 estudios anteriores se suman 7 en los que solo una de las dos máscaras tenía la clase (Dice 0, HD95 indefinido). La clase 3 tiene n = 182 por 6 estudios de ese tipo.
- **n de pacientes:** pacientes con al menos un estudio en el que la métrica está definida.

Un Dice 0 por máscara vacía sí baja la media del Dice, pero ese mismo estudio no aparece en el HD95. Conviene leer ambas métricas juntas.

## Valores guardados de la línea base en validación

El archivo `resultados/modelo_piloto/resumen_metricas.json` resume **56 estudios de validación** de la línea base (`piloto_30pct_2epocas`):

| Clase evaluada | Estudios con Dice definido | Media | Mediana | Desviación estándar entre estudios |
|---|---:|---:|---:|---:|
| 1 | 55 | 0,6214 | 0,7241 | 0,3062 |
| 2 | 56 | 0,7346 | 0,8090 | 0,2096 |
| 3 | 55 | 0,7762 | 0,8636 | 0,2188 |
| Macro por estudio | 56 | 0,7024 | 0,7627 | No se registra |

Entre los estudios evaluados, `BraTS-GLI-00281-000` tuvo el macro más alto (0,9421) y `BraTS-GLI-00675-001` el más bajo (0,0000). En el caso de menor puntuación, las clases 1 y 3 quedaron indefinidas y se omitieron; la clase 2 tuvo Dice 0. Estos extremos describen únicamente esta validación y no permiten concluir cómo se comportaría el modelo con pacientes nuevos.

## Validación: línea base y variante con métricas 3D

Las dos versiones se evaluaron en los mismos 56 estudios (51 pacientes). Valores por estudio, tomados de `metricas_3d_validacion/resumen_metricas_3d.json` de cada carpeta:

| Región | Medida | Línea base: media (mediana), n | Variante: media (mediana), n |
|---|---|---|---|
| Tumor completo | Dice | 0,8346 (0,8734), 56 | 0,8432 (0,8990), 56 |
| Tumor completo | HD95 (mm) | 14,21 (5,56), 56 | 15,37 (5,00), 56 |
| Clase 1 | Dice | 0,6214 (0,7241), 55 | 0,5935 (0,6639), 56 |
| Clase 1 | HD95 (mm) | 14,31 (5,96), 52 | 13,72 (10,77), 53 |
| Clase 2 | Dice | 0,7346 (0,8090), 56 | 0,7403 (0,8181), 56 |
| Clase 2 | HD95 (mm) | 9,49 (4,58), 56 | 12,18 (4,58), 56 |
| Clase 3 | Dice | 0,7762 (0,8636), 55 | 0,7330 (0,8162), 56 |
| Clase 3 | HD95 (mm) | 9,79 (3,61), 55 | 12,71 (4,47), 55 |
| Macro por estudio | Dice | 0,7024 (0,7627), 56 | 0,6890 (0,7255), 56 |

El macro de la variante proviene de `resultados/modelo_variante_peso3/resumen_metricas.json`. Las medias de cada columna se calculan sobre conjuntos de estudios que pueden no coincidir (por ejemplo, 55 frente a 56 en la clase 1), así que la comparación entre versiones se hace con pares, como se describe a continuación.

## Comparación apareada: línea base frente a variante

**Pregunta:** ¿el peso 3 en la clase 1 mejoró la segmentación respecto a la línea base?

**Método:** para cada medida, se emparejaron los estudios por `sample_id` y se calculó la diferencia variante − línea base en cada estudio. Solo entran los pares en los que la medida está definida en ambas versiones. Las diferencias se analizaron con la prueba de Wilcoxon de rangos con signo (`scipy.stats.wilcoxon` con sus opciones por defecto; las diferencias exactamente 0 se descartan). Como se hicieron 8 comparaciones, se usó la corrección de Bonferroni: una diferencia se considera significativa si p < 0,05 / 8 = 0,00625.

**Cómo leer el signo:** en el Dice, una diferencia positiva significa que la variante mejora. En el HD95, una diferencia **positiva significa que la variante empeora** (bordes más lejanos). Las columnas «mejora» y «empeora» ya tienen en cuenta ese sentido.

| Medida | n de pares | Diferencia media | Estudios en que la variante mejora | Estudios en que empeora | Empates | p |
|---|---:|---:|---:|---:|---:|---:|
| Dice tumor completo | 56 | +0,0087 | 32 | 24 | 0 | 0,084 |
| Dice clase 1 | 55 | −0,0171 | 24 | 29 | 2 | 0,278 |
| Dice clase 2 | 56 | +0,0057 | 22 | 34 | 0 | 0,870 |
| Dice clase 3 | 55 | −0,0298 | 17 | 38 | 0 | **0,003** |
| HD95 tumor completo (mm) | 56 | +1,16 | 24 | 25 | 7 | 0,658 |
| HD95 clase 1 (mm) | 52 | −1,25 | 16 | 31 | 5 | 0,057 |
| HD95 clase 2 (mm) | 56 | +2,69 | 19 | 33 | 4 | 0,367 |
| HD95 clase 3 (mm) | 55 | +2,91 | 12 | 32 | 11 | **0,0008** |

Calculado con `resultados/modelo_piloto/metricas_3d_validacion/metricas_3d_por_estudio.csv` y `resultados/modelo_variante_peso3/metricas_3d_validacion/metricas_3d_por_estudio.csv`. En negrita, las diferencias significativas tras la corrección.

**Resultado:**

- **Clase 1, objetivo del cambio:** la variante no la mejoró. El Dice bajó 0,017 de media (p = 0,278), una diferencia que no se distingue del azar. En el HD95 de la clase 1 la variante empeora en más estudios de los que mejora (31 frente a 16), aunque la media baja; p = 0,057 sin corregir, que no es significativo.
- **Clase 3:** la variante empeoró. El Dice bajó 0,030 (p = 0,003) y el HD95 aumentó 2,9 mm (p = 0,0008). Ambas diferencias siguen siendo significativas tras la corrección por 8 comparaciones.
- **Tumor completo y clase 2:** no hay diferencias distinguibles del azar.

**Decisión:** se congeló la línea base. La decisión se tomó solo con validación, antes de mirar la prueba.

**Hipótesis, no comprobada,** sobre por qué empeora la clase 3: con más peso en la clase 1, la red podría asignar a la clase 1 parte de los vóxeles que en la referencia son clase 3. Estas dos clases suelen estar próximas dentro del tumor, de modo que confundirlas bajaría el Dice de la clase 3 sin cambiar el tumor completo, lo que es compatible con lo observado. No se midió la matriz de confusión entre clases para confirmarlo, y con una sola ejecución por versión tampoco se puede descartar que parte de la diferencia se deba a la variabilidad del entrenamiento.

### Limitaciones de esta comparación

- **Una sola ejecución por versión.** No se repitió el entrenamiento con otras semillas, así que no se sabe cuánto cambian las métricas entre ejecuciones de una misma configuración.
- **Equipos distintos.** La línea base se entrenó en un PC (Python 3.13.2, 14 hilos) y la variante en una máquina virtual (Python 3.13.18, 4 hilos). Aunque la semilla y la configuración coinciden, el orden de las operaciones en coma flotante puede cambiar con el equipo y el número de hilos, por lo que parte de la diferencia podría no deberse al peso de la clase.
- **Estudios no independientes.** La prueba de Wilcoxon supone pares independientes, pero los 56 estudios de validación pertenecen a 51 pacientes; los estudios del mismo paciente no son estrictamente independientes. Los valores p deben leerse como aproximados.
- **Validación parcial.** Se usaron 56 de los 185 estudios de validación.

## Resultados finales en prueba

La línea base congelada se evaluó **una sola vez** en el conjunto de prueba completo: 188 estudios de 170 pacientes, 29.140 cortes. El checkpoint evaluado es `resultados/modelo_piloto/unet2d_piloto_30pct.pth`, con SHA-256 `1cd6de46fda9e5e2c60cff276c1dc294b567e846526fff9a7c5d8a227f0a9972`, registrado en `resultados/prueba_linea_base/configuracion.json`. No se entrenó ni se ajustó nada con estos resultados, y la variante no se evaluó en prueba.

### Por estudio

Tomado de `resultados/prueba_linea_base/metricas_3d/resumen_metricas_3d.json`, salvo el macro, que viene de `resultados/prueba_linea_base/resumen_metricas.json`:

| Región | Medida | Media | Mediana | Desviación estándar | n |
|---|---|---:|---:|---:|---:|
| Tumor completo | Dice | 0,8571 | 0,9026 | 0,1388 | 188 |
| Tumor completo | HD95 (mm) | 11,07 | 5,30 | 14,93 | 188 |
| Clase 1 | Dice | 0,6192 | 0,7595 | 0,3226 | 186 |
| Clase 1 | HD95 (mm) | 13,86 | 7,24 | 18,43 | 179 |
| Clase 2 | Dice | 0,7495 | 0,7986 | 0,1784 | 188 |
| Clase 2 | HD95 (mm) | 8,20 | 5,10 | 10,17 | 188 |
| Clase 3 | Dice | 0,7663 | 0,8546 | 0,2378 | 188 |
| Clase 3 | HD95 (mm) | 9,69 | 2,31 | 18,78 | 182 |
| Macro por estudio (clases 1–3) | Dice | 0,7113 | 0,7789 | No se registra | 188 |

El Dice del tumor completo va de 0,1870 a 0,9754 entre estudios, y su HD95, de 1,00 a 75,75 mm.

### Por paciente

Media de los estudios de cada paciente:

| Región | Medida | Media | Mediana | n de pacientes |
|---|---|---:|---:|---:|
| Tumor completo | Dice | 0,8595 | 0,9005 | 170 |
| Tumor completo | HD95 (mm) | 11,13 | 5,22 | 170 |
| Clase 1 | Dice | 0,6191 | 0,7570 | 169 |
| Clase 1 | HD95 (mm) | 13,83 | 7,26 | 164 |
| Clase 2 | Dice | 0,7491 | 0,7986 | 170 |
| Clase 2 | HD95 (mm) | 8,21 | 5,07 | 170 |
| Clase 3 | Dice | 0,7640 | 0,8501 | 170 |
| Clase 3 | HD95 (mm) | 9,64 | 2,91 | 164 |

Los valores por paciente son muy parecidos a los valores por estudio, de modo que los 18 estudios adicionales de pacientes repetidos no cambian el resumen de forma apreciable.

### Lectura de los resultados

- El tumor completo es la región mejor segmentada. La clase 1 es la más difícil: tiene el Dice medio más bajo y la mayor dispersión.
- En todas las regiones el HD95 medio es bastante mayor que el mediano. Esto indica que en la mayoría de los estudios los bordes quedan a pocos milímetros, pero unos pocos estudios tienen distancias grandes que suben la media.
- Los valores de prueba están en el mismo rango que los de validación de la línea base (por ejemplo, Dice del tumor completo 0,8571 en prueba frente a 0,8346 en validación). Son conjuntos distintos y de tamaño distinto, así que no conviene interpretar esa diferencia.

### Ejemplo: Dice alto con HD95 alto (`BraTS-GLI-01663-000`)

En este estudio de prueba el tumor completo tiene **Dice 0,901** y **HD95 75,8 mm**, el HD95 más alto de la prueba. Al separar la predicción del tumor completo en componentes conectados se observa:

- Un componente principal de 62.309 vóxeles que se superpone con el tumor de la referencia.
- Otros 22 componentes sueltos, con 5.749 vóxeles en total (alrededor del 8 % de lo predicho), que no tocan la referencia. Los nueve más grandes quedan a entre 38 y 73 mm del tumor de la referencia.

Como el HD95 toma el percentil 95 de las distancias entre superficies, esos fragmentos lejanos bastan para elevarlo, aunque apenas afecten al Dice. Si se conserva solo el componente principal, el HD95 de este estudio baja a 1,7 mm (y el Dice sube a 0,944). Este cálculo se hizo solo para entender el caso: **no** forma parte de la evaluación ni se aplicó posprocesamiento a los resultados.

Por qué la red predice esas regiones sueltas no se ha comprobado. Una hipótesis es que la U-Net 2D clasifica cada corte sin contexto de los cortes vecinos, y zonas hiperintensas aisladas en algún corte pueden parecerle tumor.

### Ejemplos cualitativos

Dos figuras versionadas muestran casos concretos, generadas con `codigo/evaluacion/figura_comparacion.py`:

- `resultados/figuras_informe/test_casos.png`: cuatro estudios de **prueba** con la línea base (`BraTS-GLI-01480-000`, `BraTS-GLI-00134-000`, `BraTS-GLI-01663-000` y `BraTS-GLI-00714-001`). Incluye el estudio con menor Dice del tumor completo de la prueba (0,187), el de mayor Dice (0,975) y el caso anterior.
- `resultados/figuras_informe/validacion_casos.png`: tres estudios de **validación** con la línea base y la variante lado a lado.

Cada fila muestra la FLAIR, la referencia y la predicción (o predicciones) en el mismo corte axial: el que tiene más área de tumor en la referencia. El Dice del título es el **Dice 3D del tumor completo en el estudio entero**, no el del corte mostrado; por eso un corte puede verse mejor o peor de lo que sugiere el número. Los casos se eligieron para ilustrar aciertos y errores; no son una muestra representativa.

## Historial de entrenamiento

`resultados/modelo_piloto/historial_entrenamiento.csv` tiene una fila por época y estas columnas:

| Columna | Interpretación |
|---|---|
| `epoca` | Número de pasada completa por los cortes de entrenamiento. |
| `perdida_entrenamiento` | Media de la suma de Cross-Entropy y Dice suave para los lotes de esa época. Menor indica menor pérdida según esa función; por sí sola no mide generalización. |
| `lotes_entrenamiento` | Número de lotes procesados en la época. |
| `tiempo_epoca_segundos` | Duración de la época. |
| `tiempo_total_segundos` | Tiempo acumulado desde el inicio del bucle de entrenamiento hasta guardar esa fila. |

El historial de la línea base registra una pérdida de entrenamiento de 0,7658 en la primera época y 0,6359 en la segunda. No incluye pérdida de validación, y dos puntos no permiten afirmar que el entrenamiento haya convergido. La segunda fila registra 15.209 segundos acumulados hasta terminar la segunda época; el tiempo de evaluación se ejecuta después.

El historial de la variante (`resultados/modelo_variante_peso3/historial_entrenamiento.csv`) registra 0,7682 y 0,6381, y 40.111 segundos acumulados. Sus pérdidas no son directamente comparables con las de la línea base, porque la Cross-Entropy de la variante incluye el peso de la clase 1.

## Archivos y ubicaciones

| Ruta | Contenido |
|---|---|
| `resultados/modelo_piloto/configuracion.json` | Línea base: semilla, épocas, lote, tasa de aprendizaje, dispositivo, modalidades, conteos, pérdida y regla de evaluación. |
| `resultados/modelo_piloto/metricas_por_estudio.csv` | Una fila por estudio de validación, conteos de referencia/predicción por clase, Dice, macro, rutas y `run_id`. |
| `resultados/modelo_piloto/resultados.csv` | Resumen tabular con `sample_id`, paciente (`group_key`), referencia, predicción, métrica y `run_id`. |
| `resultados/modelo_piloto/resumen_metricas.json` | Medias, medianas, desviaciones, número de casos válidos y regla para clases vacías. |
| `resultados/modelo_piloto/metricas_3d_validacion/` | Dice y HD95 3D de la línea base en validación: por estudio, por paciente y resumen JSON. |
| `resultados/modelo_piloto/ejemplos_validacion/` | Tres PNG con una imagen T1c, máscara real y predicción del mismo corte. |
| `resultados/modelo_piloto/predicciones_30pct/` | Salida `.npz` por estudio; cada archivo guarda el arreglo 3D `prediccion`. Los `.npz` están ignorados por Git. |
| `resultados/modelo_piloto/unet2d_piloto_30pct.pth` | Checkpoint de la línea base congelada (modelo y optimizador). Está versionado a propósito; el resto de `.pth` se ignoran. |
| `resultados/modelo_variante_peso3/` | Variante: la misma estructura que la línea base, con `metricas_3d_validacion/`. Su checkpoint no está versionado. |
| `resultados/prueba_linea_base/configuracion.json` | Evaluación en prueba: checkpoint, SHA-256, partición, estudios, pacientes, cortes y versiones de Python y PyTorch. |
| `resultados/prueba_linea_base/metricas_por_estudio.csv`, `resultados.csv`, `resumen_metricas.json` | Dice por clase y macro en prueba, con la misma estructura que en validación. |
| `resultados/prueba_linea_base/metricas_3d/` | Dice y HD95 3D en prueba: por estudio, por paciente y resumen JSON. |
| `resultados/prueba_linea_base/ejemplos/` | Tres PNG de ejemplo generados durante la inferencia en prueba. |
| `resultados/prueba_linea_base_log.txt` | Registro de consola de la inferencia en prueba (34,4 min). Termina con un segundo intento que el script rechazó porque las salidas ya existían; ese intento no produjo resultados. |
| `resultados/figuras_informe/` | Figuras cualitativas `test_casos.png` y `validacion_casos.png`. |

Las figuras versionadas contienen cortes MRI y máscaras de estudios identificados por pseudónimo. La posibilidad de redistribuir el dataset o esas figuras no se confirmó; antes de publicar el repositorio hay que revisar las condiciones del proveedor.

## Alcance y limitaciones

- Las dos versiones se entrenaron con 238 pacientes y dos épocas en CPU; no se seleccionó checkpoint con una búsqueda en validación.
- La selección entre línea base y variante usó 56 de los 185 estudios de validación, con las limitaciones descritas en la [comparación apareada](#limitaciones-de-esta-comparación).
- La prueba se usó una sola vez, con la versión ya congelada. Sus resultados describen esta partición de BraTS-GLI; no son una comparación oficial con el reto.
- Las auditorías validan lectura, geometría y valores esperados, pero no revisan clínicamente los contornos.
- La U-Net procesa cada corte de forma independiente y no se aplica posprocesamiento; Dice y HD95 no evalúan todas las propiedades de una segmentación.
- Las explicaciones de los errores del modelo de este documento son hipótesis, no hechos comprobados.

Por ello, estos resultados no son evidencia de utilidad clínica.

## Enlaces relacionados

- [Modelo y entrenamiento](05_modelo_y_entrenamiento.md)
- [Preparación de imágenes](04_preparacion_de_imagenes.md)
- [Guía del código](07_guia_del_codigo.md)
- [Reproducción completa](08_reproduccion_completa.md)
