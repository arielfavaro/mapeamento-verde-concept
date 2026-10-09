"""Máscaras de nuvem/sombra por pixel para cada produto.

Todas as funções recebem o array da banda de qualidade e devolvem um array booleano
em que ``True`` significa "pixel válido" (sem nuvem, sombra ou falha).
"""

from enum import StrEnum

import numpy as np


class MaskKind(StrEnum):
    SCL = "scl"  # Sentinel-2 L2A: Scene Classification Layer
    QA_PIXEL = "qa_pixel"  # Landsat Coleção 2: QA_PIXEL (bits)
    FMASK = "fmask"  # HLS v2: Fmask (bits)


# Classes SCL descartadas: 0 sem dado, 1 saturado/defeituoso, 3 sombra de nuvem,
# 8/9 nuvem média/alta probabilidade, 10 cirrus fino.
SCL_INVALID = (0, 1, 3, 8, 9, 10)

# QA_PIXEL (Landsat C2): bit 0 preenchimento, 1 nuvem dilatada, 2 cirrus, 3 nuvem, 4 sombra, 5 neve.
QA_PIXEL_INVALID_BITS = 0b111111

# Fmask (HLS v2): bit 1 nuvem, 2 adjacente a nuvem/sombra, 3 sombra de nuvem. 255 = sem dado.
FMASK_INVALID_BITS = 0b1110
FMASK_FILL = 255


def scl_valid(scl: np.ndarray) -> np.ndarray:
    scl = np.nan_to_num(scl, nan=0).astype(np.uint8)
    return ~np.isin(scl, SCL_INVALID)


def qa_pixel_valid(qa: np.ndarray) -> np.ndarray:
    qa = np.nan_to_num(qa, nan=1).astype(np.uint16)
    return (qa & QA_PIXEL_INVALID_BITS) == 0


def fmask_valid(fmask: np.ndarray) -> np.ndarray:
    fmask = np.nan_to_num(fmask, nan=FMASK_FILL).astype(np.uint8)
    return ((fmask & FMASK_INVALID_BITS) == 0) & (fmask != FMASK_FILL)


_MASK_FUNCS = {
    MaskKind.SCL: scl_valid,
    MaskKind.QA_PIXEL: qa_pixel_valid,
    MaskKind.FMASK: fmask_valid,
}


def valid_mask(kind: MaskKind, qa: np.ndarray, buffer_px: int = 0) -> np.ndarray:
    """Calcula a máscara de validade e, opcionalmente, expande as áreas inválidas.

    As bordas de nuvem costumam escapar dos classificadores; ``buffer_px`` aumenta a área
    descartada em N pixels ao redor de cada pixel inválido (dilatação 8-conexa).
    """
    valid = _MASK_FUNCS[kind](qa)
    if buffer_px > 0:
        valid = ~dilate(~valid, buffer_px)
    return valid


def dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    """Dilatação binária 8-conexa nas duas últimas dimensões, apenas com numpy."""
    out = mask.copy()
    for _ in range(iterations):
        grown = out.copy()
        grown[..., 1:, :] |= out[..., :-1, :]
        grown[..., :-1, :] |= out[..., 1:, :]
        grown[..., :, 1:] |= out[..., :, :-1]
        grown[..., :, :-1] |= out[..., :, 1:]
        grown[..., 1:, 1:] |= out[..., :-1, :-1]
        grown[..., :-1, :-1] |= out[..., 1:, 1:]
        grown[..., 1:, :-1] |= out[..., :-1, 1:]
        grown[..., :-1, 1:] |= out[..., 1:, :-1]
        out = grown
    return out
