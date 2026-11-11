from subsurface_api.geo import (
    bbox,
    centroid,
    haversine_m,
    normalize_ring,
    perimeter_m,
    ring_to_wkt,
    spherical_area_m2,
)


def test_normalize_ring_drops_closing_point_and_duplicates():
    ring = normalize_ring([(0, 0), (1, 0), (1, 1), (1, 1), (0, 1), (0, 0)])
    assert ring == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def test_area_one_degree_square_near_equator():
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    area = spherical_area_m2(ring)
    # 1° lon ≈ 111,320 m, 1° lat ≈ 110,574 m at the equator → ≈ 1.231e10 m²
    assert 1.20e10 < area < 1.26e10


def test_area_scales_quadratically():
    small = spherical_area_m2([(0, 0), (1, 0), (1, 1), (0, 1)])
    big = spherical_area_m2([(0, 0), (2, 0), (2, 2), (0, 2)])
    assert abs(big / small - 4.0) < 0.01


def test_perimeter_and_haversine():
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    per = perimeter_m(ring)
    assert 4.30e5 < per < 4.55e5  # ≈ 2 × (111,320 + 110,574) m
    d = haversine_m((0.0, 0.0), (1.0, 0.0))
    assert 110_000 < d < 112_000


def test_centroid_and_bbox():
    ring = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    assert centroid(ring) == (1.0, 1.0)
    assert bbox(ring) == [0.0, 0.0, 2.0, 2.0]


def test_ring_to_wkt_is_closed():
    wkt = ring_to_wkt([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    assert wkt.startswith("POLYGON((") and wkt.endswith("))")
    assert wkt.count(",") == 3  # 4 points including the closing one
    assert wkt.count("0.0000000 0.0000000") == 2  # first vertex and closing point
