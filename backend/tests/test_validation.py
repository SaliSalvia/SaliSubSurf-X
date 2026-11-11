from subsurface_api.validation import validate_region

SQUARE = [(51.0, 35.0), (51.01, 35.0), (51.01, 35.01), (51.0, 35.01)]  # ~1 km²


def test_valid_square():
    r = validate_region(SQUARE)
    assert r.valid, r.issues
    assert r.vertex_count == 4
    assert 0.8e6 < r.area_sqm < 1.3e6  # 0.01° × 0.01° near 35°N
    assert r.area_hectares > 50


def test_closed_ring_input_is_accepted():
    r = validate_region(SQUARE + [SQUARE[0]])
    assert r.valid
    assert r.vertex_count == 4


def test_too_few_vertices():
    r = validate_region(SQUARE[:2])
    assert not r.valid
    assert any("3 distinct vertices" in i for i in r.issues)


def test_too_many_vertices():
    pts = [(51.0 + i * 1e-4, 35.0) for i in range(11)]
    r = validate_region(pts)
    assert not r.valid
    assert any("At most 10" in i for i in r.issues)


def test_self_intersecting_bowtie():
    bowtie = [(0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0)]
    r = validate_region(bowtie)
    assert not r.valid
    assert any("cross each other" in i for i in r.issues)


def test_too_small_region():
    tiny = [(51.0, 35.0), (51.000001, 35.0), (51.000001, 35.000001), (51.0, 35.000001)]
    r = validate_region(tiny)
    assert not r.valid
    assert any("too small" in i for i in r.issues)


def test_out_of_range_coordinates():
    bad = [(200.0, 35.0), (201.0, 35.0), (201.0, 36.0), (200.0, 36.0)]
    r = validate_region(bad)
    assert not r.valid
    assert any("out of range" in i for i in r.issues)
