
from pathlib import Path
import random

import nibabel as nib
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, Sampler

from codigo.segmentacion.cargar_imagenes import DATASET, buscar_archivo
from codigo.segmentacion.preparar_imagenes import preparar_estudio


PROYECTO = Path(__file__).resolve().parents[2]
MANIFEST = PROYECTO / "resultados" / "particion" / "manifest_con_split.csv"
MODALIDADES = ("t1n", "t1c", "t2w", "t2f")


class Dataset2D(Dataset):
    """
    Dataset de cortes axiales 2D.
    Mantiene en memoria solamente el estudio que se está utilizando.
    """

    def __init__(self, split, manifest_path=MANIFEST, max_estudios=None):
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"Partición no válida: {split}")

        self.split = split
        self.manifest = pd.read_csv(
            manifest_path,
            dtype={"sample_id": str, "study_eye_visit_key": str},
        )

        self.manifest = self.manifest[
            self.manifest["split"] == split
        ].copy()

        if self.manifest.empty:
            raise ValueError(f"No hay estudios para la partición {split}")

        # Permite hacer pruebas pequeñas sin cargar todo el conjunto.
        if max_estudios is not None:
            self.manifest = self.manifest.head(max_estudios).copy()

        self.estudios = []
        self.indices_por_estudio = {}
        self.indice_cortes = []
        self.estudio_en_cache = None
        self.datos_en_cache = None

        for _, fila in self.manifest.iterrows():
            estudio_id = fila["sample_id"]
            carpeta = DATASET / estudio_id

            if not carpeta.is_dir():
                raise FileNotFoundError(
                    f"No se encontró la carpeta: {carpeta}"
                )

            archivo_mascara = buscar_archivo(carpeta, "seg")
            forma = nib.load(str(archivo_mascara)).shape

            if len(forma) != 3:
                raise ValueError(
                    f"La máscara de {estudio_id} no es tridimensional"
                )

            n_cortes = forma[2]
            posicion_estudio = len(self.estudios)

            self.estudios.append(estudio_id)
            indices = []

            for z in range(n_cortes):
                indice = len(self.indice_cortes)
                self.indice_cortes.append((posicion_estudio, z))
                indices.append(indice)

            self.indices_por_estudio[posicion_estudio] = indices

        print(
            f"Dataset {split}: {len(self.estudios)} estudios, "
            f"{len(self.indice_cortes)} cortes indexados."
        )

    def __len__(self):
        return len(self.indice_cortes)

    def _cargar_estudio_si_necesario(self, estudio_id):
        if self.estudio_en_cache != estudio_id:
            self.datos_en_cache = preparar_estudio(estudio_id)
            self.estudio_en_cache = estudio_id

        return self.datos_en_cache

    def __getitem__(self, indice):
        posicion_estudio, z = self.indice_cortes[indice]
        estudio_id = self.estudios[posicion_estudio]

        datos = self._cargar_estudio_si_necesario(estudio_id)

        # Cuatro canales: modalidad x altura x anchura.
        imagen = np.stack(
            [
                datos["imagenes"][modalidad][:, :, z]
                for modalidad in MODALIDADES
            ],
            axis=0,
        ).astype(np.float32, copy=False)

        # La máscara conserva etiquetas enteras: 0, 1, 2 y 3.
        mascara = datos["mascara"][:, :, z].astype(
            np.int64, copy=False
        )

        imagen = np.ascontiguousarray(imagen)
        mascara = np.ascontiguousarray(mascara)

        return torch.from_numpy(imagen), torch.from_numpy(mascara)


class LotesPorEstudio(Sampler):
    """
    Agrupa cortes del mismo estudio para evitar cargar repetidamente
    volúmenes cuando se trabaja con lotes pequeños.
    """

    def __init__(self, dataset, batch_size=2, shuffle=True, seed=42):
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.seed = seed
        self.epoca = 0

    def __iter__(self):
        generador = random.Random(self.seed + self.epoca)
        self.epoca += 1

        estudios = list(self.dataset.indices_por_estudio.keys())

        if self.shuffle:
            generador.shuffle(estudios)

        for posicion in estudios:
            indices = list(
                self.dataset.indices_por_estudio[posicion]
            )

            if self.shuffle:
                generador.shuffle(indices)

            for inicio in range(0, len(indices), self.batch_size):
                yield indices[inicio:inicio + self.batch_size]

    def __len__(self):
        return sum(
            (
                len(indices) + self.batch_size - 1
            ) // self.batch_size
            for indices in self.dataset.indices_por_estudio.values()
        )



if __name__ == "__main__":
    torch.manual_seed(42)

    dataset = Dataset2D("train", max_estudios=2)

    # Buscar dos cortes que contengan alguna etiqueta tumoral.
    indices_con_tumor = []

    for indice in range(len(dataset)):
        imagen, mascara = dataset[indice]

        if torch.any(mascara > 0):
            indices_con_tumor.append(indice)

        if len(indices_con_tumor) == 2:
            break

    if len(indices_con_tumor) < 2:
        raise RuntimeError(
            "No se encontraron dos cortes con tumor en los "
            "dos primeros estudios. Prueba con más estudios."
        )

    # Construir un lote de dos cortes.
    imagenes = []
    mascaras = []

    for indice in indices_con_tumor:
        imagen, mascara = dataset[indice]
        imagenes.append(imagen)
        mascaras.append(mascara)

    lote_imagenes = torch.stack(imagenes)
    lote_mascaras = torch.stack(mascaras)

    print("\nPrueba de lote con tumor")
    print("Índices seleccionados:", indices_con_tumor)
    print("Forma de entrada:", tuple(lote_imagenes.shape))
    print("Forma de máscaras:", tuple(lote_mascaras.shape))
    print(
        "Etiquetas por corte:",
        [torch.unique(m).tolist() for m in lote_mascaras],
    )
    print(
        "Píxeles tumorales por corte:",
        [int((m > 0).sum()) for m in lote_mascaras],
    )

    assert lote_imagenes.shape == (2, 4, 240, 240)
    assert lote_mascaras.shape == (2, 240, 240)
    assert all((m > 0).any() for m in lote_mascaras)

    print("Prueba de lote con tumor superada.")
