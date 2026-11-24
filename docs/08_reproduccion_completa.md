# 8. Reproducción completa

Esta guía describe los comandos incluidos en el repositorio y el orden de ejecución. Las auditorías completas y los entrenamientos son costosos; **no se volvieron a ejecutar durante la redacción de la documentación**. Los comandos y argumentos se tomaron del código de cada script, y las cifras citadas, de los archivos de `resultados/`.

## Antes de empezar

1. Prepara Python y las bibliotecas como indica la [guía de inicio](01_guia_de_inicio.md). Para obtener las mismas versiones que los resultados finales, instala `requirements-congelado.txt` con el comando `uv` de la guía de inicio.
2. Desde PowerShell, sitúate en la raíz del repositorio. Los ejemplos usan `python -m codigo...`.
3. Obtén BraTS-GLI desde la fuente autorizada y ubícalo en `datos/BraTS2023-GLI-Dataset/`.
4. Guarda una copia de los CSV/resultados existentes si quieres conservar la evidencia actual. Varias etapas escriben sobre nombres fijos; no hay opción para dirigir todos los outputs a otra carpeta.

## 1. Audita estudios, archivos y máscaras

**Qué y por qué:** comprobar estructura, lectura, geometría, etiquetas, duplicados y tamaños de máscaras antes de usar los datos.

**Necesitas:** el conjunto completo en la ruta esperada. Los tres primeros comandos leen todos los estudios/archivos, no una muestra.

```powershell
python -m codigo.auditoria.auditar_estudios
python -m codigo.auditoria.buscar_duplicados
python -m codigo.auditoria.resumir_volumenes_mascaras
```

**Qué revisar:** `resultados/auditoria/inventario.csv`, `auditoria_calidad_mascaras.csv`, los reportes de duplicados/faltantes, `volumenes_por_estudio.csv` y `resumen_global_volumenes.csv`. El estado registrado aquí fue 1.251 estudios, 6.255 archivos esperados, cero faltantes y cero máscaras marcadas para revisión.

**Si falla:** revisa que cada estudio tenga exactamente los cinco NIfTI y que nibabel pueda abrirlos. Consulta [problemas frecuentes](09_problemas_frecuentes.md).

**Salidas:** estos scripts sobrescriben sus CSV de auditoría con el mismo nombre. Respalda lo que quieras conservar antes de ejecutarlos.

## 2. Crea el manifiesto

**Qué y por qué:** combinar inventario y auditoría de máscara en una tabla por estudio que el flujo pueda utilizar.

**Necesitas:** los dos CSV de auditoría del paso anterior.

```powershell
python -m codigo.auditoria.crear_manifiesto
```

**Qué revisar:** `resultados/manifest.csv`. Debe tener una fila por `sample_id`, estado de calidad y disponibilidad de referencia. En esta copia todas las filas están marcadas como válidas.

**Si falla:** confirma que los CSV existen y que `study_id`/`sample_id` no estén duplicados ni tengan espacios o formato inconsistente.

**Salidas:** el script reemplaza `resultados/manifest.csv` sin pedir confirmación.

## 3. Crea y comprueba la partición

**Qué y por qué:** asignar pacientes completos a entrenamiento, validación o prueba, y comprobar que no haya IDs compartidos.

**Necesitas:** `manifest.csv` y `auditoria_calidad_mascaras.csv` actualizados.

```powershell
python -m codigo.particion.crear_particion
python -m codigo.particion.resumir_particion
python -m codigo.particion.verificar_separacion_pacientes
```

**Qué revisar:** `split.csv`, `manifest_con_split.csv`, `resumen_conteos_particion.csv`, `resumen_etiquetas_particion.csv` y los dos reportes de intersección. El resultado guardado tiene 793/170/170 pacientes y 878/185/188 estudios en train/validation/test, con cero intersecciones.

**Protección de salidas:** `crear_particion` no sobrescribe si ya existe `split.csv`, `manifest_con_split.csv` o `split_antes_label_summary.csv`; en la copia actual existen dos de esas salidas y el comando se detendrá. Para rehacer toda la etapa, conserva esos resultados y sácalos de las rutas esperadas en una copia de trabajo separada. Los comandos de resumen y verificación sí vuelven a escribir sus reportes.

**Si falla:** si los conteos no coinciden, confirma que el manifiesto use las columnas esperadas y que todos los estudios incluidos tengan máscara disponible. Si el reporte detecta intersección, no entrenes hasta aclararla.

## 4. Comprueba carga, preparación y arquitectura con una muestra

**Qué y por qué:** comprobar un estudio antes de entrenar para detectar rutas, geometría, etiquetas o formas inesperadas.

**Necesitas:** `BraTS-GLI-00000-000` en el dataset local y sus cinco archivos.

```powershell
python -m codigo.segmentacion.cargar_imagenes
python -m codigo.segmentacion.preparar_imagenes
python -m codigo.segmentacion.red_unet
```

Los dos primeros usan el estudio fijo en el código; el tercero comprueba la red con una entrada sintética y no necesita datos. El código de preparación espera que cada corte tenga forma `240 × 240`.

**Qué revisar:** mensajes con formas de volúmenes/cortes y, en la prueba de red, entrada y salida `(2, 4, 240, 240)`. `preparar_imagenes` también contiene aserciones de forma y finitud.

**Si falla:** revisa la carpeta esperada, nombres de sufijo y geometría de los NIfTI. Si el estudio no existe en tu descarga, el ejemplo fijo no funcionará; este módulo no acepta un ID de estudio desde la consola.

## 5. Ejecuta los reportes de preparación (opcionales)

```powershell
python -m codigo.segmentacion.revisar_normalizacion
python -m codigo.segmentacion.contar_voxeles_por_clase
```

El primero lee 2 estudios iniciales de train y 5 de validation; el segundo lee hasta 50 estudios iniciales de train. Generan `auditoria_normalizacion.csv`, `conteos_por_estudio_train.csv` y `frecuencias_clases_train.csv`. No son requisitos previos del entrenamiento. Vuelven a escribir esos archivos si ya existen.

## 6. Selecciona el subconjunto piloto

**Qué y por qué:** reducir tiempo de procesamiento conservando una muestra de pacientes, no de estudios aislados.

**Necesitas:** `manifest_con_split.csv` y una ruta de salida libre.

```powershell
python -m codigo.entrenamiento.seleccionar_pacientes_piloto
```

El comando crea `resultados/modelo_piloto/manifest_piloto_30.csv`, con 30 % de pacientes de train y 30 % de validation por separado. Puede usarse `--salida RUTA` para crear el manifiesto en otra ruta; el entrenamiento posterior busca específicamente la ruta predeterminada.

**Qué revisar:** el resumen impreso: 238 pacientes/270 estudios de entrenamiento y 51 pacientes/56 estudios de validación en la ejecución registrada. No debe aparecer `test`.

**Protección de salidas:** el selector se detiene si `manifest_piloto_30.csv` ya existe. En esta copia existe. Para reproducir el piloto completo, guarda y mueve el directorio de resultados del piloto en una copia de trabajo, y permite que el selector vuelva a crear el manifiesto predeterminado.

## 7. Entrena y evalúa el piloto

**Qué y por qué:** optimizar la U-Net durante dos épocas y calcular Dice al final sobre los estudios seleccionados de validación.

**Necesitas:** manifiesto del piloto en su ruta predeterminada, NIfTI para train/validation y suficiente tiempo y memoria. La prueba no forma parte de este paso.

```powershell
python -m codigo.entrenamiento.entrenar_piloto
```

El script no tiene argumentos CLI. Usa CPU, lote 2, tasa `0.0001`, semilla 42, 14 hilos y base 16. La ejecución registrada tardó cerca de 4,36 horas según el contexto del proyecto; el historial muestra 4 h 13 min hasta el fin de la segunda época, antes de completar la evaluación. El tiempo varía por equipo.

**Qué revisar:** checkpoint, historial, configuración, métricas por estudio, resumen JSON, archivos de predicción y figuras en `resultados/modelo_piloto/`. El Dice macro medio guardado es 0,7024 en 56 estudios.

**Protección de salidas:** el entrenamiento se cancela si encuentra salidas previas. Para preservar los datos originales, trabaja en una copia separada y archiva allí el directorio existente `resultados/modelo_piloto/` antes de regenerar selección y entrenamiento. La ejecución sobrescribe el checkpoint entre épocas dentro de esa nueva corrida, pero su comprobación impide reemplazar un checkpoint previo al iniciar.

**Si falla:** confirma que el manifiesto del piloto no incluya `test`, que las rutas estén presentes y que el equipo tenga memoria libre. En CPU, el tiempo largo es esperado. No hay parámetros CLI para reducir el lote o las épocas.

## 8. Entrena la variante (opcional)

**Qué y por qué:** entrenar la versión alternativa (peso 3 para la clase 1 en la Cross-Entropy) para compararla con la línea base en validación. Solo hace falta si quieres repetir la comparación; sus resultados ya están en `resultados/modelo_variante_peso3/`.

**Necesitas:** el manifiesto del piloto (`resultados/modelo_piloto/manifest_piloto_30.csv`), los NIfTI de train y validation y mucho tiempo: la ejecución registrada, con 4 hilos en una máquina virtual, acumuló 40.111 segundos (unas 11 h) hasta terminar la segunda época.

```powershell
python -u -m codigo.entrenamiento.entrenar_variante --peso-clase-1 3.0 --run-id variante_peso3_30pct_2epocas --salida resultados/modelo_variante_peso3 --hilos 4
```

Los valores del ejemplo son los predeterminados. Otros argumentos: `--cada-lotes` (por defecto 1000) y `--epocas` (por defecto 2); `--max-estudios N` solo sirve para pruebas rápidas.

**Qué revisar:** `configuracion.json` debe registrar `pesos_cross_entropy` `[1.0, 3.0, 1.0, 1.0]`; además, historial, métricas por estudio, resumen y figuras.

**Protección de salidas y reanudación:** cada 1.000 lotes guarda `checkpoint_intermedio.pt`. Si la ejecución se interrumpe, vuelve a lanzar el mismo comando y reanudará desde ese punto. Si no hay checkpoint intermedio y la carpeta ya contiene resultados, el script se detiene. Para no mezclar resultados, usa otra `--salida` o archiva la carpeta existente en una copia de trabajo.

## 9. Evalúa la versión congelada en prueba

**Qué y por qué:** medir una sola vez el desempeño de la versión elegida con validación (la línea base) en pacientes que no se usaron para entrenar ni para decidir. La prueba no debe convertirse en una iteración para ajustar el modelo: si después de verla se cambia algo, el resultado deja de ser una evaluación independiente.

**Necesitas:** el checkpoint congelado `resultados/modelo_piloto/unet2d_piloto_30pct.pth`, `resultados/particion/manifest_con_split.csv` y los NIfTI de los 188 estudios de prueba.

Primero comprueba que el checkpoint es exactamente el evaluado. Su SHA-256 debe ser `1cd6de46fda9e5e2c60cff276c1dc294b567e846526fff9a7c5d8a227f0a9972`:

```powershell
Get-FileHash resultados/modelo_piloto/unet2d_piloto_30pct.pth -Algorithm SHA256
```

En Linux o macOS: `sha256sum resultados/modelo_piloto/unet2d_piloto_30pct.pth`.

Después ejecuta la inferencia:

```powershell
python -u -m codigo.entrenamiento.inferir_particion --checkpoint resultados/modelo_piloto/unet2d_piloto_30pct.pth --run-id prueba_piloto_30pct_2epocas --salida resultados/prueba_linea_base --particion test --confirmo-version-congelada
```

`--confirmo-version-congelada` es obligatorio con `--particion test`; sin él el script se niega a evaluar prueba. `--hilos` vale 4 por defecto. La ejecución registrada tardó 34,4 minutos con 4 hilos.

**Qué revisar:** en `resultados/prueba_linea_base/configuracion.json`, `checkpoint_sha256` debe coincidir con el hash anterior, `particion` debe ser `test`, y deben aparecer 188 estudios, 170 pacientes y 29.140 cortes. El resumen guardado en `resumen_metricas.json` tiene un Dice macro medio de 0,7113.

**Protección de salidas:** el script se detiene si la carpeta de salida ya contiene resultados. En esta copia existen, y así lo muestra el final de `resultados/prueba_linea_base_log.txt`. Para repetir el paso sin tocar la evidencia, usa otra `--salida` en una copia de trabajo.

## 10. Calcula las métricas 3D

**Qué y por qué:** calcular Dice y HD95 en 3D del tumor completo y de cada clase, por estudio y por paciente, a partir de las predicciones `.npz` ya guardadas. No vuelve a ejecutar el modelo.

**Necesitas:** el `metricas_por_estudio.csv` de la evaluación, las predicciones `.npz` a las que apunta y las máscaras de referencia del dataset.

```powershell
# Prueba (línea base congelada)
python -u -m codigo.evaluacion.calcular_metricas_3d --metricas resultados/prueba_linea_base/metricas_por_estudio.csv --salida resultados/prueba_linea_base/metricas_3d --modo-hd95 agrupado

# Validación (línea base y variante), para la comparación apareada
python -u -m codigo.evaluacion.calcular_metricas_3d --metricas resultados/modelo_piloto/metricas_por_estudio.csv --salida resultados/modelo_piloto/metricas_3d_validacion --modo-hd95 agrupado
python -u -m codigo.evaluacion.calcular_metricas_3d --metricas resultados/modelo_variante_peso3/metricas_por_estudio.csv --salida resultados/modelo_variante_peso3/metricas_3d_validacion --modo-hd95 agrupado
```

`--max-estudios N` procesa solo los primeros N estudios, para una prueba rápida.

**Qué revisar:** `resumen_metricas_3d.json` debe registrar `modo_hd95` `agrupado` y una `verificacion_dice_max_dif_vs_csv_original` del orden de 10⁻¹⁶; un valor grande indicaría que las predicciones no corresponden al CSV. En prueba: 188 estudios, 170 pacientes y Dice medio del tumor completo 0,8571.

**Salidas:** este script **sobrescribe** `metricas_3d_por_estudio.csv`, `metricas_3d_por_paciente.csv` y `resumen_metricas_3d.json` sin pedir confirmación. Respáldalos o usa otra `--salida`.

**Si falla:** las rutas del CSV pueden usar `\` (Windows); el script las convierte. Si no encuentra un `.npz`, comprueba que las predicciones existan: no están versionadas y hay que regenerarlas con el paso 7, 8 o 9.

## 11. Genera las figuras de comparación (opcional)

**Qué y por qué:** crear figuras cualitativas con la FLAIR, la referencia y la predicción en el corte axial con más tumor en la referencia.

**Necesitas:** las predicciones `.npz` y los NIfTI de los estudios elegidos.

```powershell
# Prueba: línea base
python -u -m codigo.evaluacion.figura_comparacion --metricas resultados/prueba_linea_base/metricas_por_estudio.csv --ids BraTS-GLI-01480-000 BraTS-GLI-00134-000 BraTS-GLI-01663-000 BraTS-GLI-00714-001 --salida resultados/figuras_informe/test_casos.png

# Validación: línea base y variante lado a lado
python -u -m codigo.evaluacion.figura_comparacion --metricas resultados/modelo_piloto/metricas_por_estudio.csv --metricas-b resultados/modelo_variante_peso3/metricas_por_estudio.csv --etiqueta-a "Línea base" --etiqueta-b "Variante (peso 3)" --ids BraTS-GLI-00675-001 BraTS-GLI-00021-000 BraTS-GLI-00682-001 --salida resultados/figuras_informe/validacion_casos.png
```

Los `--ids` son los de las figuras versionadas. El script sobrescribe el PNG de `--salida` si ya existe.

**Qué revisar:** el Dice del título de cada panel es el Dice 3D del tumor completo del estudio entero; debe coincidir con `dice_tumor_completo` de `metricas_3d_por_estudio.csv`.

## Enlaces relacionados

- [Manifiesto y partición](03_manifiesto_y_particion.md)
- [Modelo y entrenamiento](05_modelo_y_entrenamiento.md)
- [Guía del código](07_guia_del_codigo.md)
- [Problemas frecuentes](09_problemas_frecuentes.md)
