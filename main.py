"""Запускает весь пайплайн по порядку и печатает итоговую сводку по числу записей."""
import json
import sqlite3
import subprocess
import sys

import pandas as pd

STEPS = [
    ("1. API data collection", "src/api_client.py"),
    ("2. Kafka Producer", "src/producer.py"),
    ("3. Kafka Consumer", "src/consumer.py"),
    ("4. Pandera validation", "src/validator.py"),
    ("5. Cleaning and transformation", "src/cleaner.py"),
    ("6. SQLite loading (run twice: idempotency test)", "src/loader.py"),
    ("7. EDA and visualization", "src/analysis.py"),
]


def run_step(title, script):
    print(f"\n{'=' * 70}\n{title}  ->  python {script}\n{'=' * 70}", flush=True)
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"\nPipeline stopped: step '{title}' failed (exit code {result.returncode}).")
        sys.exit(result.returncode)


def pipeline_summary():
    with open("data/raw_responses.json", encoding="utf-8") as f:
        collected = len(json.load(f))
    with open("data/producer_stats.json", encoding="utf-8") as f:
        producer_stats = json.load(f)
    with open("data/consumed_data.json", encoding="utf-8") as f:
        consumed = len(json.load(f))
    valid = len(pd.read_csv("data/validated_data.csv"))
    invalid = pd.read_csv("data/invalid_records.csv")
    invalid_test = int(invalid["is_test"].sum())
    invalid_real = len(invalid) - invalid_test
    cleaned = len(pd.read_csv("data/cleaned_data.csv"))
    with sqlite3.connect("data/output.db") as conn:
        stored = conn.execute("SELECT COUNT(*) FROM collisions;").fetchone()[0]
        duplicates = conn.execute(
            "SELECT COUNT(*) FROM (SELECT collision_id FROM collisions "
            "GROUP BY collision_id HAVING COUNT(*) > 1);"
        ).fetchone()[0]

    summary = pd.DataFrame(
        [
            ("Collected from API", collected),
            ("Published to Kafka", producer_stats["published"]),
            ("Failed to publish", producer_stats["failed"]),
            ("Consumed from Kafka", consumed),
            ("Test records added", invalid_test),
            ("Valid records", valid),
            ("Invalid real records", invalid_real),
            ("Records after cleaning", cleaned),
            ("Stored in SQLite", stored),
            ("Duplicate IDs in SQLite", duplicates),
        ],
        columns=["stage", "records"],
    )
    print(f"\n{'=' * 70}\nPIPELINE SUMMARY\n{'=' * 70}")
    print(summary.to_string(index=False))
    print(
        "\nNotes: consumed + test records = valid + invalid; "
        "invalid records (wrong coordinates, test records) are excluded before cleaning; "
        "cleaning removes duplicates; SQLite keeps one row per collision_id."
    )
    checks = {
        "Published == Consumed": producer_stats["published"] == consumed,
        "Consumed + test == Valid + Invalid": consumed + invalid_test == valid + len(invalid),
        "Cleaned == Stored": cleaned == stored,
        "No duplicates in SQLite": duplicates == 0,
    }
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")


if __name__ == "__main__":
    for title, script in STEPS:
        run_step(title, script)
    pipeline_summary()