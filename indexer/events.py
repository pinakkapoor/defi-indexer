"""
on-chain event indexer.

connects to an ethereum node (or L2), listens for specific contract events,
and stores them in a local database. the backbone of the whole system.

most defi analytics starts with event logs — Transfer, Swap, Deposit, etc.
instead of querying the chain every time, we index events once and query locally.
"""

import time
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from web3 import Web3
from web3.contract import Contract

logger = logging.getLogger(__name__)


@dataclass
class IndexedEvent:
    tx_hash: str
    block_number: int
    timestamp: datetime
    contract_address: str
    event_name: str
    args: dict
    chain_id: int = 1


class EventIndexer:
    """
    indexes events from ethereum smart contracts.

    usage:
        indexer = EventIndexer(rpc_url="https://eth-mainnet.g.alchemy.com/v2/...")
        indexer.add_contract("uniswap_v2_pool", address, abi)
        events = indexer.index_range(from_block=18000000, to_block=18001000)
    """

    def __init__(self, rpc_url: str, chain_id: int = 1, batch_size: int = 1000):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.batch_size = batch_size
        self.contracts: dict[str, Contract] = {}
        self._block_timestamps: dict[int, datetime] = {}

    def add_contract(self, name: str, address: str, abi: list):
        """register a contract to index events from"""
        checksum = Web3.to_checksum_address(address)
        contract = self.w3.eth.contract(address=checksum, abi=abi)
        self.contracts[name] = contract
        logger.info(f"registered contract '{name}' at {address}")

    def _get_block_timestamp(self, block_number: int) -> datetime:
        """cache block timestamps to avoid redundant RPC calls"""
        if block_number not in self._block_timestamps:
            block = self.w3.eth.get_block(block_number)
            self._block_timestamps[block_number] = datetime.utcfromtimestamp(
                block["timestamp"]
            )
        return self._block_timestamps[block_number]

    def index_range(
        self,
        from_block: int,
        to_block: int,
        event_names: Optional[list[str]] = None,
    ) -> list[IndexedEvent]:
        """
        index events from all registered contracts in a block range.

        processes in batches to avoid hitting RPC limits.
        most providers cap at 10k blocks per eth_getLogs call.
        """
        all_events = []

        for start in range(from_block, to_block + 1, self.batch_size):
            end = min(start + self.batch_size - 1, to_block)
            logger.debug(f"indexing blocks {start}-{end}")

            for name, contract in self.contracts.items():
                for event_name in self._get_event_names(contract, event_names):
                    try:
                        event_filter = getattr(contract.events, event_name)
                        logs = event_filter.create_filter(
                            fromBlock=start, toBlock=end
                        ).get_all_entries()

                        for log in logs:
                            ts = self._get_block_timestamp(log["blockNumber"])
                            all_events.append(IndexedEvent(
                                tx_hash=log["transactionHash"].hex(),
                                block_number=log["blockNumber"],
                                timestamp=ts,
                                contract_address=log["address"],
                                event_name=event_name,
                                args=dict(log["args"]),
                                chain_id=self.chain_id,
                            ))

                    except Exception as e:
                        logger.warning(f"error indexing {event_name} from {name}: {e}")

        logger.info(f"indexed {len(all_events)} events from blocks {from_block}-{to_block}")
        return all_events

    def _get_event_names(
        self, contract: Contract, filter_names: Optional[list[str]]
    ) -> list[str]:
        """get event names from contract ABI, optionally filtered"""
        abi_events = [
            item["name"] for item in contract.abi if item.get("type") == "event"
        ]
        if filter_names:
            return [e for e in abi_events if e in filter_names]
        return abi_events

    def get_latest_block(self) -> int:
        return self.w3.eth.block_number
