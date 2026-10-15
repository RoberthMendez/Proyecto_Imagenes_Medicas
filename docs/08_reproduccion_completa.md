# 8. Reproducción completa

Esta guía describe los comandos incluidos en el repositorio y el orden de ejecución. Las auditorías completas y el entrenamiento son costosos; **no se ejecutaron durante la redacción de la documentación**. La verificación de comandos fue estática, leyendo rutas y argumentos del código.

## Antes de empezar

1. Prepara Python y las bibliotecas como indica la [guía de inicio](01_guia_de_inicio.md).
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

## 8. No evaluar prueba durante la reproducción del piloto

La evaluación implementada recibe validation y el manifiesto del piloto impide que incluya test. El conjunto de prueba permanece reservado. No se debe convertir una evaluación de prueba en una iteración para ajustar el modelo.

## Qué se verificó de forma estática

Los nombres de módulos y comandos anteriores coinciden con los scripts disponibles; las únicas opciones de consola encontradas son `--salida` del selector. No se ejecutaron auditorías completas, resúmenes grandes, entrenamiento ni las pruebas puntuales de módulos durante esta tarea.

## Enlaces relacionados

- [Manifiesto y partición](03_manifiesto_y_particion.md)
- [Modelo y entrenamiento](05_modelo_y_entrenamiento.md)
- [Guía del código](07_guia_del_codigo.md)
- [Problemas frecuentes](09_problemas_frecuentes.md)
