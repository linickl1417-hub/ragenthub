"""事件总线抽象：sync（默认，直接切分） / kafka（异步）"""
from __future__ import annotations
import json
from app.config import settings
from app.pipelines.ingest import ingest_file
from pathlib import Path


class _SyncBus:
    """同步总线：上传即切分入库"""
    def publish_document_uploaded(self, file_path: str, domain: str):
        n = ingest_file(Path(file_path), domain)
        return {"chunks": n, "mode": "sync"}


class _KafkaBus:
    """Kafka 总线：发事件，由 worker 消费切分"""
    def __init__(self, bootstrap: str):
        from kafka import KafkaProducer
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        )
        self.topic = "doc.uploaded"

    def publish_document_uploaded(self, file_path: str, domain: str):
        future = self._producer.send(self.topic, {"file_path": file_path, "domain": domain})
        future.get(timeout=5)
        return {"topic": self.topic, "mode": "kafka"}


_singleton = None


def get_event_bus():
    global _singleton
    if _singleton is None:
        if settings.event_bus == "kafka":
            _singleton = _KafkaBus(settings.kafka_bootstrap)
        else:
            _singleton = _SyncBus()
    return _singleton


def kafka_worker_loop():
    """独立进程：python -m app.core.events 消费 Kafka 事件做切分"""
    from kafka import KafkaConsumer
    consumer = KafkaConsumer(
        "doc.uploaded",
        bootstrap_servers=settings.kafka_bootstrap,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        group_id="ragenthub-ingest",
        auto_offset_reset="earliest",
    )
    print("[kafka-worker] listening on doc.uploaded ...")
    for msg in consumer:
        data = msg.value
        try:
            n = ingest_file(Path(data["file_path"]), data["domain"])
            print(f"[kafka-worker] ingested {n} chunks from {data['file_path']}")
        except Exception as e:  # noqa: BLE001
            print(f"[kafka-worker] error: {e}")


if __name__ == "__main__":
    kafka_worker_loop()
