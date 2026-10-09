import numpy as np

from app.domain.masks import MaskKind, dilate, fmask_valid, qa_pixel_valid, scl_valid, valid_mask


def test_scl_keeps_vegetation_soil_water_and_drops_clouds():
    scl = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    assert scl_valid(scl).tolist() == [False, False, True, False, True, True, True, True, False, False, False, True]


def test_landsat_qa_pixel_bits():
    clear = 0b1010101000000  # bits altos (confiança) não importam
    cloud = 1 << 3
    shadow = 1 << 4
    fill = 1
    assert qa_pixel_valid(np.array([clear, cloud, shadow, fill])).tolist() == [True, False, False, False]


def test_hls_fmask_bits_and_fill():
    water_clear = 1 << 5
    adjacent = 1 << 2
    assert fmask_valid(np.array([water_clear, adjacent, 255, np.nan])).tolist() == [True, False, False, False]


def test_dilate_grows_invalid_area_by_buffer():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    assert dilate(mask, 1).sum() == 9
    assert dilate(mask, 2).sum() == 25


def test_valid_mask_buffer_shrinks_valid_area():
    scl = np.full((1, 7, 7), 4)
    scl[0, 3, 3] = 9  # uma nuvem no centro
    valid = valid_mask(MaskKind.SCL, scl, buffer_px=1)
    assert (~valid).sum() == 9
