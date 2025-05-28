# run : pytest unit_testing/test_darwin_parser.py -v
import sys
import os
import gzip
from unittest.mock import patch
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Compressed Darwin-style XML with two journeys
def create_mock_xml():
    sample_xml = '''
    <tt:TDATA xmlns:tt="http://www.thalesgroup.com/rtti/XmlTimetable/v8">
        <tt:Journey>
            <tt:OR tpl="NRWCH" ptd="10:15" />
            <tt:IP tpl="IPSWH" />
            <tt:DT tpl="LIVST" pta="12:30" />
        </tt:Journey>
        <tt:Journey>
            <tt:OR tpl="NRWCH" ptd="08:00" />
            <tt:DT tpl="LIVST" pta="10:00" />
        </tt:Journey>
    </tt:TDATA>
    '''
    compressed = BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb") as f:
        f.write(sample_xml.encode("utf-8"))
    compressed.seek(0)
    return {"Body": BytesIO(compressed.getvalue())}

mock_get_tiploc_from_crs = lambda x: {"NRW": "NRWCH", "LST": "LIVST"}.get(x)

# PATCHES shared across tests
@patch("services.darwin.get_tiploc_from_crs", side_effect=mock_get_tiploc_from_crs)
@patch("boto3.Session.client")
def test_valid_journey_match(mock_boto_client, mock_lookup):
    from services import darwin
    mock_boto_client.return_value.get_object.return_value = create_mock_xml()
    darwin.seen_times = set()
    journeys = darwin.parse_journey_file("fakefile", "NRW", "LST", "10:00")
    assert len(journeys) == 1
    assert journeys[0]['departure_time'] == "10:15"

@patch("services.darwin.get_tiploc_from_crs", side_effect=mock_get_tiploc_from_crs)
@patch("boto3.Session.client")
def test_early_journey_ignored(mock_boto_client, mock_lookup):
    from services import darwin
    mock_boto_client.return_value.get_object.return_value = create_mock_xml()
    darwin.seen_times = set()
    journeys = darwin.parse_journey_file("fakefile", "NRW", "LST", "09:00")
    assert len(journeys) == 1  # Only one departs after 09:00

@patch("services.darwin.get_tiploc_from_crs", return_value=None)
@patch("boto3.Session.client")
def test_missing_tiploc_returns_empty(mock_boto_client, mock_lookup):
    from services import darwin
    mock_boto_client.return_value.get_object.return_value = create_mock_xml()
    darwin.seen_times = set()
    journeys = darwin.parse_journey_file("fakefile", "XXX", "LST", "10:00")
    assert journeys == []