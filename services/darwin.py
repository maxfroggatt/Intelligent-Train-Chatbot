import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
import boto3
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
from collections import defaultdict
from dotenv import load_dotenv
from services.station_lookup import get_tiploc_from_crs

# Load environment variables from .env file
load_dotenv()

# AWS credentials and Darwin feed settings
AWS_ACCESS_KEY = os.getenv("DARWIN_AWS_KEY")
AWS_SECRET_KEY = os.getenv("DARWIN_AWS_SECRET")
REGION = os.getenv("REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
PREFIX = os.getenv("PREFIX")
NS = {'tt': 'http://www.thalesgroup.com/rtti/XmlTimetable/v8'}

# List latest timetable file versions from S3
def list_available_file_versions():
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION
    )
    s3 = session.resource('s3')
    bucket = s3.Bucket(BUCKET_NAME)
    versions = defaultdict(list)

    # Extract versioned XML files by date
    for obj in bucket.objects.filter(Prefix=PREFIX):
        key = obj.key
        if key.endswith('.xml.gz') and '_v' in key and 'ref' not in key:
            filename = key.split('/')[-1]
            date_part = filename.split('_')[0]
            version = int(filename.split('_v')[-1].split('.')[0])
            versions[date_part].append((version, key))

    latest_per_date = {}
    for date, items in versions.items():
        best = max(items)  # get highest version number
        latest_per_date[date] = best[1]

    return latest_per_date

seen_times = set()

# Parse Darwin XML and extract matching journeys
def parse_journey_file(file_key, origin_crs='NRW', dest_crs='LST', latest_dep_time='10:00'):
    origin_tiploc = get_tiploc_from_crs(origin_crs)
    dest_tiploc = get_tiploc_from_crs(dest_crs)

    # Validate TIPLOCs and log search info
    if not origin_tiploc or not dest_tiploc:
        print(f"Could not find TIPLOCs for {origin_crs} or {dest_crs}")
        return []

    print(f"Searching from {origin_crs} ({origin_tiploc}) to {dest_crs} ({dest_tiploc}) after {latest_dep_time}")

    # Download and parse timetable XML from S3
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION
    )
    s3 = session.client('s3')
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
    xml_data = gzip.decompress(obj['Body'].read())

    tree = ET.parse(BytesIO(xml_data))
    root = tree.getroot()
    journeys = root.findall('tt:Journey', NS)

    print(f"Total journeys in file: {len(journeys)}")

    matched_journeys = []

    # Extract CRS and departure times from journeys
    for journey in journeys:
        stops = []
        for tag in ['OR', 'IP', 'PP', 'DT']:
            for loc in journey.findall(f'tt:{tag}', NS):
                crs = loc.attrib.get('tpl')
                dep = loc.attrib.get('ptd')
                stops.append({'crs': crs, 'dep': dep})

        crs_list = [s['crs'] for s in stops]

        # Find origin/destination indices and departure time
        if origin_tiploc in crs_list:
            o_idx = crs_list.index(origin_tiploc)
            d_idx = crs_list.index(dest_tiploc) if dest_tiploc in crs_list else -1
            departure_time = stops[o_idx]['dep']

            # Check valid journey and extract arrival info
            if d_idx > o_idx and departure_time and departure_time >= latest_dep_time:
                arrival_time = journey.find(f'tt:DT', NS).attrib.get('pta') or journey.find(f'tt:DT', NS).attrib.get(
                    'arr')
                station_names = [get_tiploc_from_crs(t) or t for t in crs_list]
                dep_arr_key = (departure_time, arrival_time)

                # Avoid duplicates and save matched journey
                if dep_arr_key not in seen_times:
                    seen_times.add(dep_arr_key)
                    matched_journeys.append({
                        'origin': origin_crs,
                        'destination': dest_crs,
                        'departure_time': departure_time,
                        'arrival_time': arrival_time,
                        'tiploc_route': crs_list,
                        'station_route': station_names,
                        'matched': True
                    })

    # Print match count and return journeys
    print(f"Matched journeys ({origin_crs} to {dest_crs}): {len(matched_journeys)}")
    return matched_journeys

# Run journey parser on latest timetable file
if __name__ == "__main__":
    print("Fetching available Darwin timetable files...")
    files_by_date = list_available_file_versions()

    if not files_by_date:
        print("No valid files found.")
    else:
        latest_date = sorted(files_by_date.keys())[-1]
        best_file = files_by_date[latest_date]

        print(f"Latest available date: {latest_date}")
        print(f"Using file: {best_file}")

        # Test run
        matches = parse_journey_file(
            best_file,
            origin_crs='NRW',
            dest_crs='LST',
            latest_dep_time='10:00'
        )

        for match in matches:
            print(f"Departure at {match['departure_time']} | Route: {match['tiploc_route']}")