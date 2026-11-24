# SIS2: Data Streaming and Validation Pipeline (Apache Kafka + Pandera)

End-to-end data pipeline: **NYC Open Data API → Kafka Producer → Kafka Topic → Kafka Consumer → Pandera validation → pandas/NumPy cleaning → SQLite3 → EDA (Matplotlib/Seaborn)**.


## Data source
- API: NYC Open Data — Motor Vehicle Collisions (Crashes)
- Endpoint: `https://data.cityofnewyork.us/resource/h9gi-nx95.json`
- Parameters (SoQL): `$limit=500`, `$offset=0, 500` (2 pages), `$order=crash_date DESC`
- No API key is required.



## Project structure
```
main.py              # runs the whole pipeline and prints the summary
src/
  api_client.py      # API collection -> data/raw_responses.json, data/raw_data.csv
  producer.py        # Kafka Producer (JSON serialization) -> topic nyc_collisions
  consumer.py        # Kafka Consumer (JSON deserialization) -> data/consumed_data.json
  validator.py       # Pandera schema + 3 test records -> data/validated_data.csv, data/invalid_records.csv
  cleaner.py         # missing values, duplicates, types, text, NumPy, filtering, groupby, pivot/melt
  loader.py          # SQLite schema, INSERT OR IGNORE, idempotency test, SQL verification
  analysis.py        # descriptive stats, grouped analysis, figures/*.png
data/                # raw, intermediate and final data, output.db
figures/             # generated visualizations
docs/data_dictionary.md
report/project_report.pdf
```

## Setup

### 1. Python environment
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 2. Start the Kafka broker (Docker)
```bash
docker run -d --name kafka -p 9092:9092 apache/kafka:4.0.0
docker ps        # container "kafka" must be "Up"
```

### 3. Create the Kafka topic
```bash
docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --create --topic nyc_collisions \
  --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
```
Broker address used by the code: `localhost:9092`. Topic: `nyc_collisions`.

## Run

### Full pipeline (recommended)
Run from the project root:
```bash
python3 main.py
```

### Step by step (same order)
```bash
python3 src/api_client.py
python3 src/producer.py
python3 src/consumer.py     # stops automatically after 10 s without new messages
python3 src/validator.py
python3 src/cleaner.py
python3 src/loader.py       # loads data twice to demonstrate idempotency
python3 src/analysis.py
```

## Expected outputs
- `data/raw_responses.json`, `data/raw_data.csv` — original API data (~1000 records)
- `data/consumed_data.json` — records received from Kafka
- `data/validated_data.csv`, `data/invalid_records.csv` — validation results with error descriptions
- `data/cleaned_data.csv`, `data/borough_summary.csv`, `data/borough_time_of_day_pivot.csv`
- `data/output.db` — SQLite database, table `collisions`
- `figures/1_crashes_by_hour.png`, `2_borough_comparison.png`, `3_top_contributing_factors.png`, `4_borough_time_heatmap.png`

## Verifying successful execution
At the end `main.py` prints **PIPELINE SUMMARY** with record counts for each stage and four checks, all must be `[OK]`:
- Published == Consumed
- Consumed + test records == Valid + Invalid
- Cleaned == Stored in SQLite
- No duplicate IDs in SQLite

`loader.py` must print `Idempotency: PASSED` (second load inserts 0 rows).

Manual database check:
```bash
sqlite3 data/output.db "SELECT COUNT(*), COUNT(DISTINCT collision_id) FROM collisions;"
```

## Notes
- The API returns the most recent crashes, so record counts can differ slightly between runs.
- The consumer uses group `sis2-pipeline-consumer`: each pipeline run reads only new messages. To start from an empty topic, delete and recreate it:
  ```bash
  docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --delete --topic nyc_collisions --bootstrap-server localhost:9092
  ```
- No credentials are used or stored in the repository.