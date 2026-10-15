# 9. Problemas frecuentes

## PowerShell no reconoce `python`

Comprueba el lanzador de Python y las instalaciones disponibles:

```powershell
py --version
py -0p
```

Si existe una versión adecuada, crea el entorno con `py -3.13 -m venv .venv` y actívalo. Si ni `python` ni `py` aparecen, instala Python y abre una nueva terminal. La versión 3.13.2 encontrada en este repositorio describe su entorno local, no una versión fijada por el proyecto.

## El entorno virtual no se activa

En PowerShell, el comando de activación es:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

El cambio se limita a la sesión abierta. Si prefieres no cambiar la política, ejecuta el intérprete directamente con `\.venv\Scripts\python.exe -m codigo.segmentacion.red_unet`.

## Falta una biblioteca

Activa `.venv` y ejecuta:

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` reúne las dependencias directas, pero no fija versiones. Si el error se refiere a PyTorch/CUDA, instala la combinación adecuada desde el selector oficial de PyTorch. Para confirmar qué Python y pip se están usando: `python --version` y `python -m pip --version`.

## No se encuentra el dataset o un estudio

Los scripts esperan `datos/BraTS2023-GLI-Dataset/<estudio>/` con nombres que terminen en `-t1n.nii.gz`, `-t1c.nii.gz`, `-t2w.nii.gz`, `-t2f.nii.gz` y `-seg.nii.gz`. Si el ZIP extrajo una carpeta intermedia, coloca las carpetas `BraTS-GLI-...` directamente bajo `BraTS2023-GLI-Dataset`.

`cargar_imagenes.py` y `preparar_imagenes.py` usan el ejemplo fijo `BraTS-GLI-00000-000`; si esa carpeta no está en tu copia local, fallará aunque existan otros estudios. Esos módulos no reciben un ID de estudio por consola.

## Nibabel no puede cargar un NIfTI

Comprueba que el `.nii.gz` terminó de descargarse, que no está dañado y que el nombre/sufijo es correcto. El cargador requiere exactamente un archivo por modalidad, tres dimensiones, valores finitos, formas compatibles y matrices `affine` compatibles. La máscara debe tener etiquetas dentro de `{0,1,2,3}`. El error normalmente indica el estudio y archivo que no pasó la condición.

## No se encuentra un CSV

Ejecuta las etapas en orden: primero auditorías, después manifiesto, luego partición y finalmente selección piloto. Confirma que PowerShell esté en la raíz del repositorio; los comandos recomendados son `python -m codigo...`. Los scripts no ofrecen opciones generales para cambiar las rutas de entrada.

## La memoria se agota

El conjunto conserva en caché un estudio con sus cuatro volúmenes normalizados y máscara; además, el entrenamiento procesa lotes de dos cortes y tiene 14 hilos CPU configurados. Cierra programas que consuman memoria y prueba primero las comprobaciones de un solo estudio. El entrenamiento no permite reducir lote, hilos o épocas mediante CLI; esa limitación requiere un cambio de configuración en el código, no un argumento que ya exista.

## El entrenamiento en CPU tarda muchas horas

Es coherente con la ejecución registrada: cerca de 4,36 horas para el piloto completo. No se trata de una demora durante una única carga. El modelo procesa decenas de miles de cortes; el historial muestra 21.060 lotes por época. Si no dispones de ese tiempo, no inicies el entrenamiento; revisa primero los CSV del piloto que ya están guardados.

## Los resultados no son idénticos en otro computador

La semilla es 42 y se fija en `random`, NumPy y PyTorch, pero las versiones de bibliotecas, diferencias de hardware, cálculo numérico y orden de ejecución pueden cambiar el resultado. El repositorio no contiene un lockfile ni fija versiones. Registra el entorno, confirma la misma partición y no uses los resultados del piloto como garantía de una repetición exacta.

## Un comando dice que la salida ya existe

Es el comportamiento esperado de algunas protecciones:

- `crear_particion` no reemplaza sus archivos `split` existentes.
- `seleccionar_pacientes_piloto` no reemplaza el manifiesto de salida.
- `entrenar_piloto` no reemplaza resultados de una corrida anterior.

Conserva una copia de los resultados y usa una copia de trabajo antes de mover las salidas de sus rutas esperadas. Los scripts de auditoría y los resúmenes sí escriben sobre algunos CSV existentes, así que respáldalos si son evidencia que necesitas conservar.

## No sé cómo cargar el checkpoint

El archivo `.pth` contiene un diccionario con la clave `modelo_state_dict`. No existe un módulo de inferencia independiente. La forma general de cargarlo es construir la misma U-Net y después cargar sus pesos:

```python
import torch
from codigo.segmentacion.red_unet import UNet2D

modelo = UNet2D(canales_entrada=4, clases_salida=4, base=16)
checkpoint = torch.load(
    "resultados/modelo_piloto/unet2d_piloto_30pct.pth",
    map_location="cpu",
)
modelo.load_state_dict(checkpoint["modelo_state_dict"])
modelo.eval()
```

La carga de pesos no crea por sí misma una predicción: hay que preparar el estudio con el mismo orden de canales y la misma normalización. La configuración real está en `configuracion.json`.

## Un identificador de paciente perdió ceros iniciales

El manifiesto canónico guarda `subject_key` como texto con ceros iniciales, por ejemplo `00008`. Al seleccionar el piloto, pandas puede inferir esa columna como número; por eso algunos CSV de piloto muestran `8`. Usa `sample_id` para identificar estudios o normaliza explícitamente el formato antes de cruzar los archivos. No cambies identificadores a mano en los resultados ya existentes.

## Enlaces relacionados

- [Guía de inicio](01_guia_de_inicio.md)
- [Guía del código](07_guia_del_codigo.md)
- [Reproducción completa](08_reproduccion_completa.md)
