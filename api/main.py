"""
FastAPI server for defi-indexer.

serves indexed events and computed metrics.
"""

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from indexer.storage import EventStore

app = FastAPI(
    title="defi-indexer",
    description="DeFi protocol analytics API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = EventStore()


@app.get("/health")
async def health():
    latest_block = store.get_latest_block()
    return {"status": "ok", "latest_indexed_block": latest_block}


@app.get("/api/events")
async def get_events(
    contract: str = None,
    event_name: str = None,
    from_block: int = None,
    to_block: int = None,
    limit: int = Query(default=100, le=1000),
):
    """query indexed events"""
    events = store.get_events(
        contract_address=contract,
        event_name=event_name,
        from_block=from_block,
        to_block=to_block,
        limit=limit,
    )
    return [
        {
            "tx_hash": e.tx_hash,
            "block_number": e.block_number,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "contract_address": e.contract_address,
            "event_name": e.event_name,
            "args": e.args,
        }
        for e in events
    ]


@app.get("/api/metrics/{protocol}")
async def get_metrics(
    protocol: str,
    metric: str = None,
    limit: int = Query(default=30, le=365),
):
    """get computed metrics for a protocol"""
    metrics = store.get_metrics(
        protocol=protocol,
        metric_name=metric,
        limit=limit,
    )

    if not metrics:
        raise HTTPException(404, f"no metrics found for protocol '{protocol}'")

    return [
        {
            "metric": m.metric_name,
            "value": m.value,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            "metadata": m.metadata_,
        }
        for m in metrics
    ]


@app.get("/api/protocols")
async def list_protocols():
    """list all indexed protocols with latest metrics"""
    # in a real implementation this would query distinct protocols
    # and their latest metric snapshots
    return {"note": "connect a database and run the indexer to populate this"}
