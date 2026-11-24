import json
from kafka import KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "nyc_collisions"
RAW_JSON_PATH = "data/raw_responses.json"


def load_records(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda key: str(key).encode("utf-8"),
        acks="all",
        retries=3,
    )


def publish_records(producer, records):
    published, failed = 0, 0
    for record in records:
        try:
            future = producer.send(TOPIC, key=record.get("collision_id"), value=record)
            future.get(timeout=10)   # ждём подтверждения, что сообщение записано в топик
            published += 1
        except KafkaError as error:
            failed += 1
            print(f"Failed to send record {record.get('collision_id')}: {error}")
    producer.flush()
    return published, failed


if __name__ == "__main__":
    records = load_records(RAW_JSON_PATH)
    print(f"Loaded {len(records)} records from {RAW_JSON_PATH}")
    try:
        producer = create_producer()
    except KafkaError as error:
        print(f"Kafka broker is not available: {error}")
        raise SystemExit(1)

    published, failed = publish_records(producer, records)
    producer.close()
    print(f"Published: {published}, Failed: {failed}")
    with open("data/producer_stats.json", "w", encoding="utf-8") as f:
        json.dump({"published": published, "failed": failed}, f)