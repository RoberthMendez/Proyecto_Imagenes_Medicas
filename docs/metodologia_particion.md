
# Metodología de partición del conjunto BraTS-GLI

## 1. Objetivo

Separar los estudios en conjuntos de entrenamiento, validación
y prueba, manteniendo todos los estudios asociados a un mismo
identificador de paciente dentro de una única partición.

## 2. Fuente de datos

Se utilizó el manifiesto consolidado:

[`resultados/manifest.csv`](../resultados/manifest.csv)

Se incluyeron los estudios que cumplían simultáneamente:

- `qc_status = válido`
- `exclusion_reason` vacío
- `reference_available = true`

## 3. Agrupación

La agrupación se realizó mediante `subject_key`, correspondiente
al código de paciente utilizado en la estructura del conjunto
de datos.

Los estudios asociados al mismo código se asignaron a una
misma partición.

No se dispone de documentación externa adicional para verificar
independientemente la identidad clínica asociada a estos códigos.

## 4. Regla de asignación

Se utilizó una aleatorización reproducible con semilla 42.

Los pacientes se ordenaron inicialmente por identificador,
se mezclaron con la semilla fijada y se distribuyeron mediante
los siguientes tamaños objetivo:

- Entrenamiento: 70 %
- Validación: 15 %
- Prueba: pacientes restantes

Los tamaños se calcularon mediante redondeo a números enteros.
Por esta razón, los porcentajes finales pueden presentar
pequeñas diferencias respecto a los porcentajes objetivo.

## 5. Resultados

| Partición       | Pacientes | Estudios | Porcentaje de pacientes |
| ---------------- | --------: | -------: | ----------------------: |
| Entrenamiento    |       793 |      878 |                 69,99 % |
| Validación      |       170 |      185 |                 15,00 % |
| Prueba reservada |       170 |      188 |                 15,00 % |
| Total            |     1.133 |    1.251 |                   100 % |

## 6. Verificación de solapamiento

Se comprobaron las intersecciones entre los identificadores
de las tres parejas de particiones:

- Entrenamiento–validación: 0 grupos compartidos.
- Entrenamiento–prueba: 0 grupos compartidos.
- Validación–prueba: 0 grupos compartidos.

La verificación confirma que no hay identificadores compartidos
entre las particiones registradas.

Esta comprobación no demuestra por sí sola que los identificadores
representen identidades clínicas verificadas de forma independiente.

## 7. Archivos de evidencia

- [`split.csv`](../resultados/particion/split.csv): asignación de grupos.
- [`manifest_con_split.csv`](../resultados/particion/manifest_con_split.csv): manifiesto con partición asignada.
- [`resumen_conteos_particion.csv`](../resultados/particion/resumen_conteos_particion.csv): conteos de archivos y estudios.
- [`resumen_etiquetas_particion.csv`](../resultados/particion/resumen_etiquetas_particion.csv): combinaciones de etiquetas.
- [`reporte_intersecciones_particiones.csv`](../resultados/particion/reporte_intersecciones_particiones.csv): intersecciones por pareja.
- [`reporte_verificacion_no_solapamiento.csv`](../resultados/particion/reporte_verificacion_no_solapamiento.csv): resultado global.

## 8. Protección del conjunto de prueba

El conjunto de prueba se mantiene reservado para la evaluación
final. Los resultados de la segunda entrega deben obtenerse
sobre el conjunto de validación, sin utilizar la prueba para
ajustar parámetros o seleccionar el método.
