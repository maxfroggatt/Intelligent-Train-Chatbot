# run : pytest unit_testing/test_station_lookup.py -v

# Mocked station data (imitates loaded CSV content)
mock_station_data = {
    "NRW": {"tiploc": "NRWCH", "name": "norwich"},
    "LST": {"tiploc": "LIVST", "name": "liverpool street"},
    "CBG": {"tiploc": "CAMBDG", "name": "cambridge"}
}

# Functions using mock data
def get_name_from_tiploc(tiploc_code):
    tiploc_code = tiploc_code.upper()
    for crs, info in mock_station_data.items():
        if info.get("tiploc") == tiploc_code:
            return info.get("name")
    return None

def get_tiploc_from_crs(crs_code):
    return mock_station_data.get(crs_code.upper(), {}).get("tiploc")

def get_name_from_crs(crs_code):
    return mock_station_data.get(crs_code.upper(), {}).get("name")

# Tests
def test_get_name_from_tiploc():
    assert get_name_from_tiploc("NRWCH") == "norwich"
    assert get_name_from_tiploc("LIVST") == "liverpool street"
    assert get_name_from_tiploc("XYZ") is None

def test_get_tiploc_from_crs():
    assert get_tiploc_from_crs("NRW") == "NRWCH"
    assert get_tiploc_from_crs("LST") == "LIVST"
    assert get_tiploc_from_crs("XXX") is None

def test_get_name_from_crs():
    assert get_name_from_crs("CBG") == "cambridge"
    assert get_name_from_crs("LST") == "liverpool street"
    assert get_name_from_crs("FOO") is None