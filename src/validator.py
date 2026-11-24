import json
import os
import numpy as np
import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

CONSUMED_PATH = "data/consumed_data.json"
VALID_PATH = "data/validated_data.csv"
INVALID_PATH = "data/invalid_records.csv"

BOROUGHS = ["BROOKLYN", "QUEENS", "MANHATTAN", "BRONX", "STATEN ISLAND"]
ROW_CHECK = "total_injured_ge_pedestrians_injured"

#число должно быть целым
is_whole_number = pa.Check(lambda s: s % 1 == 0, name="is_whole_number")

schema = pa.DataFrameSchema(
    columns={
        "collision_id": pa.Column(
            str, pa.Check.str_matches(r"^[0-9a-f]{32}$"), nullable=False, unique=True,
            report_duplicates="exclude_first", coerce=True,
        ),
        "crash_date": pa.Column(
            pa.DateTime,
            [pa.Check.ge(pd.Timestamp("2012-07-01")), pa.Check.le(pd.Timestamp.now())],
            nullable=False, coerce=True,
        ),
        "crash_time": pa.Column(
            str, pa.Check.str_matches(r"^([01]?\d|2[0-3]):[0-5]\d$"), nullable=False, coerce=True,
        ),
        "borough": pa.Column(str, pa.Check.isin(BOROUGHS), nullable=True, coerce=True),
        "number_of_persons_injured": pa.Column(
            float, [pa.Check.ge(0), is_whole_number], nullable=True, coerce=True,
        ),
        "number_of_persons_killed": pa.Column(
            float, [pa.Check.ge(0), is_whole_number], nullable=True, coerce=True,
        ),
        "number_of_pedestrians_injured": pa.Column(float, pa.Check.ge(0), nullable=True, coerce=True),
        "latitude": pa.Column(float, pa.Check.in_range(40.4, 41.0), nullable=True, coerce=True),
        "longitude": pa.Column(float, pa.Check.in_range(-74.3, -73.6), nullable=True, coerce=True),
    },
    checks=[
        pa.Check(
            lambda df: (df["number_of_persons_injured"] >= df["number_of_pedestrians_injured"])
            | df["number_of_persons_injured"].isna()
            | df["number_of_pedestrians_injured"].isna(),
            name=ROW_CHECK,
        )
    ],
    strict=False,
)


def load_records(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_test_records(first_real_id):
    """Три неверные записи для проверки схемы"""
    return [
        {   # неверный формат ID, будущая дата, несуществующий район
            "collision_id": "-1", "crash_date": "2030-01-01T00:00:00.000", "crash_time": "10:00",
            "borough": "GOTHAM", "number_of_persons_injured": "1", "number_of_persons_killed": "0",
            "number_of_pedestrians_injured": "0", "latitude": "40.7", "longitude": "-73.9",
            "is_test": True,
        },
        {   # неверный формат ID, отрицательное и дробное число пострадавших, неверное время
            "collision_id": "999999991", "crash_date": "2026-01-15T00:00:00.000", "crash_time": "25:99",
            "borough": "QUEENS", "number_of_persons_injured": "-3", "number_of_persons_killed": "0.5",
            "number_of_pedestrians_injured": "0", "latitude": "40.7", "longitude": "-73.8",
            "is_test": True,
        },
        {   # дубликат ID, координаты вне Нью-Йорка, пешеходов больше, чем всего пострадавших
            "collision_id": str(first_real_id), "crash_date": "2026-02-01T00:00:00.000",
            "crash_time": "14:30", "borough": "BRONX", "number_of_persons_injured": "1",
            "number_of_persons_killed": "0", "number_of_pedestrians_injured": "4",
            "latitude": "99.0", "longitude": "10.0", "is_test": True,
        },
    ]


def validate(df):
    try:
        schema.validate(df, lazy=True)
        failure_cases = pd.DataFrame(columns=["index", "column", "check", "failure_case"])
    except SchemaErrors as err:
        failure_cases = err.failure_cases

    failure_cases = failure_cases.dropna(subset=["index"]).copy()
    failure_cases["index"] = failure_cases["index"].astype(int)

    failure_cases["error"] = np.where(
        failure_cases["check"].astype(str) == ROW_CHECK,
        "row: " + ROW_CHECK,
        failure_cases["column"].astype(str) + ": " + failure_cases["check"].astype(str),
    )
    failure_cases = failure_cases.drop_duplicates(subset=["index", "error"])
    errors_per_row = failure_cases.groupby("index")["error"].apply(lambda e: "; ".join(sorted(e)))

    invalid_mask = df.index.isin(errors_per_row.index) | df["is_test"]   # тестовые записи исключаются всегда
    invalid = df[invalid_mask].copy()
    invalid["validation_errors"] = errors_per_row.reindex(invalid.index).fillna("test record")
    valid = df[~invalid_mask].copy()
    return valid, invalid, failure_cases


if __name__ == "__main__":
    records = load_records(CONSUMED_PATH)
    for record in records:
        record["is_test"] = False
    test_records = make_test_records(records[0]["collision_id"])

    df = pd.DataFrame(records + test_records)
    print(f"Received from Kafka: {len(records)}, test records added: {len(test_records)}, total: {len(df)}")

    valid, invalid, failure_cases = validate(df)

    print("\nValidation errors by rule:")
    print(failure_cases["error"].value_counts().to_string())

    print("\nTest records — detected errors:")
    for idx, row in invalid[invalid["is_test"]].iterrows():
        print(f"  [{idx}] id={row['collision_id']}: {row['validation_errors']}")

    real_invalid = invalid[~invalid["is_test"]]
    print(f"\nValid records: {len(valid)}")
    print(f"Invalid real records: {len(real_invalid)}")
    print(f"Invalid test records: {int(invalid['is_test'].sum())}")

    schema.validate(valid, lazy=True)
    print("Re-validation of valid records: passed")

    os.makedirs("data", exist_ok=True)
    valid.drop(columns=["is_test"]).to_csv(VALID_PATH, index=False)
    invalid.to_csv(INVALID_PATH, index=False)
    print(f"Saved valid -> {VALID_PATH}, invalid -> {INVALID_PATH}")