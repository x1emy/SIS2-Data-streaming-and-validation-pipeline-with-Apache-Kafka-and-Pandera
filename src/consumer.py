import json
import os
from kafka import KafkaConsumer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "nyc_collisions"
CONSUMED_PATH = "data/consumed_data.json"
TIMEOUT_MS = 10000


def create_consumer():
    return KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id="sis2-pipeline-consumer",
        consumer_timeout_ms=TIMEOUT_MS,
    )


def consume_messages(consumer):
    records, failed = [], 0
    for message in consumer:
        try:
            record = json.loads(message.value.decode("utf-8"))
            records.append(record)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            failed += 1
            print(f"Bad message at offset {message.offset}: {error}")
    return records, failed


if __name__ == "__main__":
    try:
        consumer = create_consumer()
    except KafkaError as error:
        print(f"Kafka broker is not available: {error}")
        raise SystemExit(1)

    records, failed = consume_messages(consumer)
    consumer.commit()
    consumer.close()

    os.makedirs("data", exist_ok=True)
    with open(CONSUMED_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Consumed: {len(records)}, Failed to parse: {failed}")
    print(f"Saved to {CONSUMED_PATH}")