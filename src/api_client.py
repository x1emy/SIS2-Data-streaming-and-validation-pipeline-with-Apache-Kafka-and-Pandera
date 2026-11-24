import json
import os
import requests
import pandas as pd

API_URL = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"
PAGE_SIZE = 500
NUM_PAGES = 2
RAW_JSON_PATH = "data/raw_responses.json"
RAW_CSV_PATH = "data/raw_data.csv"


def fetch_page(offset):
    params = {
        "$limit": PAGE_SIZE,
        "$offset": offset,
        "$order": "crash_date DESC",
    }
    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        print(f"Failed to load page with offset {offset}: {error}")
        return []


def collect_records():
    all_records = []
    for page in range(NUM_PAGES):
        offset = page * PAGE_SIZE
        records = fetch_page(offset)
        print(f"Page {page + 1} (offset {offset}): {len(records)} records")
        all_records.extend(records)
    return all_records


def save_raw(records):
    os.makedirs("data", exist_ok=True)
    with open(RAW_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    df = pd.DataFrame(records)
    df.to_csv(RAW_CSV_PATH, index=False)
    return df


if __name__ == "__main__":
    records = collect_records()
    if not records:
        print("No data collected")
    else:
        df = save_raw(records)
        print(f"Total collected: {df.shape[0]} rows, {df.shape[1]} columns")
        print(f"Saved to {RAW_JSON_PATH} and {RAW_CSV_PATH}")