# defi-indexer

indexes defi protocols and computes the metrics that actually matter — not just TVL but user retention, fee capture efficiency, and liquidity depth. built this because dune dashboards are great for one-off queries but terrible for systematic analysis.

## what it does

1. **index**: connects to an ethereum node, pulls events from specified contracts, stores them locally
2. **compute**: processes raw events into protocol-level metrics (TVL, volume, fees, user retention)
3. **serve**: FastAPI exposes everything for dashboards and downstream analysis

## architecture

```
indexer/
  events.py      ← event indexer (web3.py, batch processing, block caching)
  storage.py     ← SQLAlchemy storage layer (SQLite dev / Postgres prod)

analytics/
  protocol_metrics.py  ← TVL, volume, fees, user metrics, fee capture efficiency

contracts/
  SimplePool.sol       ← test pool contract that emits real AMM events

api/
  main.py              ← FastAPI endpoints for events and metrics
```

## key metrics

| metric | what it tells you |
|--------|-------------------|
| TVL | how much capital is locked — but can be inflated by recursive deposits |
| volume/TVL | capital efficiency — uniswap V3 >> V2 because concentrated liquidity |
| fee capture | annualized fees / TVL — how much the protocol earns per dollar locked |
| user retention | % of users active in consecutive periods — most protocols are terrible at this |
| new vs returning | growth quality — growing through new users or retaining existing ones? |

## quickstart

```bash
pip install -e ".[dev]"

# run tests (no RPC needed)
pytest tests/

# start API
uvicorn api.main:app --reload

# index events (requires RPC_URL)
export RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"
python -m indexer.run --from-block 18000000 --contracts uniswap_v2
```

## solidity test contracts

the `contracts/` directory has a minimal AMM pool (`SimplePool.sol`) that emits the same events as production pools. useful for testing the indexer locally without needing a mainnet fork.

```bash
cd contracts
npx hardhat compile
npx hardhat test
```

## why not just use dune?

dune is great for exploration. but if you want to:
- compare 20 protocols on the same metrics consistently
- run analysis programmatically (not clicking through a UI)
- control the data pipeline end-to-end
- avoid SQL spaghetti that breaks when dune updates their schema

then you need something like this.

## limitations

- currently ethereum mainnet only (L2 support is planned — just different RPC URLs + different block speeds)
- price data is external (pass a price map) — doesn't fetch prices itself
- no real-time streaming yet (polls in batches)
- the storage layer works fine for single-protocol analysis but would need partitioning for multi-chain at scale
