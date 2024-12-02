"""
event storage layer.

stores indexed events in SQLite (local dev) or Postgres (production).
uses SQLAlchemy so the backend is swappable.
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String, index=True)
    block_number = Column(Integer, index=True)
    timestamp = Column(DateTime, index=True)
    contract_address = Column(String, index=True)
    event_name = Column(String, index=True)
    args = Column(JSON)
    chain_id = Column(Integer, default=1)


class MetricRecord(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    protocol = Column(String, index=True)
    metric_name = Column(String, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, index=True)
    chain_id = Column(Integer, default=1)
    metadata_ = Column("metadata", JSON, default=dict)


class EventStore:
    """persistent storage for indexed events and computed metrics"""

    def __init__(self, db_url: str = "sqlite:///defi_indexer.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def store_events(self, events: list) -> int:
        """bulk insert indexed events"""
        session = self.Session()
        try:
            records = [
                EventRecord(
                    tx_hash=e.tx_hash,
                    block_number=e.block_number,
                    timestamp=e.timestamp,
                    contract_address=e.contract_address,
                    event_name=e.event_name,
                    args=e.args,
                    chain_id=e.chain_id,
                )
                for e in events
            ]
            session.bulk_save_objects(records)
            session.commit()
            return len(records)
        finally:
            session.close()

    def store_metric(self, protocol: str, metric_name: str, value: float,
                     timestamp: datetime, chain_id: int = 1, metadata: dict = None):
        """store a computed metric"""
        session = self.Session()
        try:
            record = MetricRecord(
                protocol=protocol,
                metric_name=metric_name,
                value=value,
                timestamp=timestamp,
                chain_id=chain_id,
                metadata_=metadata or {},
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def get_events(self, contract_address: str = None, event_name: str = None,
                   from_block: int = None, to_block: int = None,
                   limit: int = 1000) -> list[EventRecord]:
        """query stored events"""
        session = self.Session()
        try:
            q = session.query(EventRecord)

            if contract_address:
                q = q.filter(EventRecord.contract_address == contract_address)
            if event_name:
                q = q.filter(EventRecord.event_name == event_name)
            if from_block:
                q = q.filter(EventRecord.block_number >= from_block)
            if to_block:
                q = q.filter(EventRecord.block_number <= to_block)

            return q.order_by(EventRecord.block_number.desc()).limit(limit).all()
        finally:
            session.close()

    def get_metrics(self, protocol: str, metric_name: str = None,
                    limit: int = 100) -> list[MetricRecord]:
        """query stored metrics"""
        session = self.Session()
        try:
            q = session.query(MetricRecord).filter(MetricRecord.protocol == protocol)
            if metric_name:
                q = q.filter(MetricRecord.metric_name == metric_name)
            return q.order_by(MetricRecord.timestamp.desc()).limit(limit).all()
        finally:
            session.close()

    def get_latest_block(self) -> int:
        """get the most recent indexed block number"""
        session = self.Session()
        try:
            result = session.query(EventRecord.block_number)\
                .order_by(EventRecord.block_number.desc())\
                .first()
            return result[0] if result else 0
        finally:
            session.close()
