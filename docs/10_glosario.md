# 10. Glosario

| Término | En palabras sencillas |
|---|---|
| **Affine** | Matriz que relaciona índices de la imagen con posiciones y orientación en el espacio. El cargador la compara para confirmar que modalidades y máscara estén alineadas. |
| **BatchNorm** | Operación dentro de la red que estabiliza las activaciones entre lotes durante el aprendizaje. |
| **BraTS-GLI** | Datos del reto BraTS para segmentación de gliomas adultos. El proyecto usa la edición 2023 Adult Glioma. |
| **Canal** | Una imagen de entrada apilada junto a otras. En este proyecto los cuatro canales son `t1n`, `t1c`, `t2w` y `t2f`. |
| **Checkpoint** | Archivo `.pth` que guarda pesos del modelo y estado del optimizador para recuperar la corrida. |
| **Clase/etiqueta** | Número asignado a cada vóxel de la máscara: fondo 0 y regiones tumorales 1, 2 y 3 según BraTS 2023 Adult Glioma. |
| **Corte axial** | Plano 2D transversal del volumen. El código lo toma en índices `[:,:,z]` del tercer eje. |
| **Cross-Entropy** | Parte de la pérdida que penaliza que el modelo asigne baja probabilidad a la clase correcta. |
| **Dataset** | Colección de ejemplos que se usa para entrenar o evaluar un modelo. |
| **Desviación estándar** | Medida de qué tan dispersos están los valores respecto a su media. Se usa en la normalización y se reporta entre estudios para Dice. |
| **Dice** | Medida entre 0 y 1 del solapamiento entre predicción y referencia. 1 significa coincidencia y 0, ausencia de solapamiento. |
| **ED** | Abreviatura de la etiqueta 2 en BraTS 2023 Adult Glioma: tejido peritumoral edematoso o infiltrado. |
| **Época** | Una pasada de entrenamiento por todos los cortes indexados de la parte de entrenamiento. |
| **ET** | Abreviatura de la etiqueta 3 en BraTS 2023 Adult Glioma: tumor con realce de gadolinio. |
| **FLAIR** | Secuencia MRI que reduce la señal del líquido cefalorraquídeo y ayuda a ver señal anormal alrededor del tumor. En el nombre del archivo aparece como `t2f`. |
| **Fondo** | Vóxeles etiquetados como 0, fuera de las regiones tumorales de la máscara. |
| **Inferencia** | Uso de un modelo ya entrenado para producir una predicción sobre datos nuevos. El repositorio no tiene un flujo general independiente de inferencia. |
| **Lote (batch)** | Grupo pequeño de cortes que la red procesa antes de actualizar sus pesos. El piloto usa 2 cortes por lote. |
| **Máscara de referencia** | Volumen `seg` con las etiquetas esperadas, usado para enseñar y evaluar el modelo. |
| **Manifiesto** | Tabla con una fila por estudio y sus metadatos de disponibilidad/calidad y partición. |
| **Media** | Promedio aritmético. La normalización resta la media de los vóxeles no nulos de cada modalidad y estudio. |
| **Modalidad** | Tipo de adquisición MRI que muestra distintos contrastes de tejido, como T1, T1 con contraste, T2 y FLAIR. |
| **NCR** | Abreviatura de la etiqueta 1 en la descripción BraTS 2023 Adult Glioma: núcleo tumoral necrótico. |
| **NIfTI** | Formato de archivo que guarda un volumen médico y su información espacial; aquí se usa comprimido como `.nii.gz`. |
| **Normalización** | Reescalado de intensidades. Aquí cada modalidad y estudio se centra y escala con media/desviación de vóxeles no nulos; los ceros quedan en cero. |
| **Paciente / `subject_key`** | Unidad usada para que estudios de una misma persona no se separen entre train, validation y test. El código usa el identificador del nombre de carpeta; no lo valida clínicamente. |
| **Pérdida** | Número que resume el error durante entrenamiento y orienta cómo ajustar los pesos. El piloto suma Cross-Entropy y Dice suave. |
| **Píxel** | Unidad de una imagen 2D. En un corte, cada píxel corresponde a un vóxel del volumen. |
| **Partición / split** | Asignación de pacientes/estudios a train, validation o test. |
| **ReLU** | Función de activación que deja pasar valores positivos y reemplaza los negativos por cero. |
| **Semilla** | Número que inicializa generadores aleatorios para que ciertas selecciones y mezclas puedan repetirse. El valor del piloto es 42. |
| **Estudio (`sample_id`)** | Conjunto de las cuatro modalidades MRI y una máscara de un examen. Puede haber más de un estudio por paciente. |
| **Tasa de aprendizaje** | Tamaño de los ajustes de pesos en cada actualización. En el piloto es 0,0001. |
| **U-Net** | Arquitectura de red con un recorrido que reduce la imagen y otro que recupera su resolución, conectados para combinar contexto y detalle. |
| **Validación** | Datos separados que permiten observar el comportamiento durante desarrollo. El piloto evalúa 56 estudios de esta partición. |
| **Vóxel** | Unidad tridimensional de un volumen, equivalente 3D del píxel. Guarda una intensidad o etiqueta. |
| **WT / TC** | Regiones compuestas usadas en ciertos reportes BraTS: tumor completo (WT) y núcleo tumoral (TC). Los scripts de este proyecto reportan las etiquetas 1–3 por separado y no calculan esas regiones compuestas. |
| **Conjunto de prueba (`test`)** | Pacientes reservados para una evaluación final. En este proyecto no se usaron en el piloto. |

## Enlaces relacionados

- [Datos y auditorías](02_datos_y_auditorias.md)
- [Preparación de imágenes](04_preparacion_de_imagenes.md)
- [Modelo y entrenamiento](05_modelo_y_entrenamiento.md)
- [Resultados y evaluación](06_resultados_y_evaluacion.md)
