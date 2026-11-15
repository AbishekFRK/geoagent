import math

import pytest

from geoagent import geo


def haversine_km(lat1, lon1, lat2, lon2):
    """Independent spherical check, deliberately not using pyproj."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def test_distance_matches_haversine_within_half_percent():
    res = geo.distance_bearing(12.9716, 77.5946, 13.0827, 80.2707)
    expected = haversine_km(12.9716, 77.5946, 13.0827, 80.2707)
    assert res["distance_km"] == pytest.approx(expected, rel=0.005)


def test_bearing_due_north_and_east():
    north = geo.distance_bearing(0, 0, 1, 0)
    east = geo.distance_bearing(0, 0, 0, 1)
    assert north["initial_bearing_deg"] == pytest.approx(0, abs=0.01)
    assert east["initial_bearing_deg"] == pytest.approx(90, abs=0.01)


def test_distance_to_self_is_zero():
    assert geo.distance_bearing(10, 20, 10, 20)["distance_km"] == 0


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_invalid_coordinates_raise(lat, lon):
    with pytest.raises(ValueError):
        geo.distance_bearing(lat, lon, 0, 0)


def test_find_place_by_code_name_and_substring():
    assert geo.find_place("BLR").code == "BLR"
    assert geo.find_place("chennai").name == "Chennai"
    # Ambiguous substring prefers the city over the airport.
    assert geo.find_place("Bengaluru").kind == "city"
    assert geo.find_place("Atlantis") is None


def test_nearest_features_sorted_and_filtered():
    res = geo.nearest_features(12.9716, 77.5946, n=3, kind="airport")
    assert len(res) == 3
    assert [r["distance_km"] for r in res] == sorted(r["distance_km"] for r in res)
    assert res[0]["code"] == "BLR"
    assert all(r["kind"] == "airport" for r in res)


def test_features_within_respects_radius():
    res = geo.features_within(12.9716, 77.5946, radius_km=50, kind="airport")
    assert [r["code"] for r in res] == ["BLR"]
    assert geo.features_within(12.9716, 77.5946, radius_km=0, kind="airport") == []


def test_point_in_polygon():
    square = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]],  # lon, lat
    }
    assert geo.point_in_polygon(5, 5, square) is True
    assert geo.point_in_polygon(15, 5, square) is False
    with pytest.raises(ValueError):
        geo.point_in_polygon(1, 1, {"type": "Point", "coordinates": [1, 1]})
