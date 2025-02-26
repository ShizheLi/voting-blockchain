from typing import List, Optional
from blockchain import Blockchain
from block import Block
from transaction import Transaction
from mempool import TxnMemoryPool
import time

class Miner:
    # Constants for mining
    BLOCK_REWARD = 50_000  # 50 Barbaracoins (in milli-Barbaracoins)
    MAX_TXNS = 10  # Maximum transactions per block (including coinbase)
    BITS = 0x207fffff  # Regtest difficulty bits
    
    def __init__(self, blockchain: Blockchain, mempool: TxnMemoryPool, miner_address: str):
        self.blockchain = blockchain
        self.mempool = mempool
        self.miner_address = miner_address
        print(f"Miner initialized with address: {self.miner_address}")
    
    def _calculate_target(self) -> int:
        """Calculate the target value from bits."""
        coefficient = self.BITS & 0x00ffffff
        exponent = (self.BITS >> 24) & 0xff
        target = coefficient * pow(2, 8 * (exponent - 0x3))
        return target
    
    def _check_hash_meets_target(self, block_hash: str, target: int) -> bool:
        """Check if the block hash meets the target difficulty."""
        # Convert hash to integer for comparison
        hash_int = int(block_hash, 16)
        return hash_int < target
    
    def mine_block(self) -> Optional[Block]:
        """Mine a new block with transactions from the mempool."""
        # Get transactions from mempool (leaving space for coinbase)
        available_txns = self.mempool.get_transactions(self.MAX_TXNS - 1)
        if not available_txns:
            print("No transactions in mempool to mine")
            return None
        
        # Create coinbase transaction with current wallet address
        coinbase_tx = Transaction.create_coinbase(
            self.BLOCK_REWARD,
            self.miner_address  # Use the current wallet address
        )
        print(f"Created coinbase transaction with reward to: {self.miner_address}")
        
        # Create new block
        prev_block_hash = self.blockchain.height_map[self.blockchain.current_height]
        new_block = Block(prev_block_hash)
        new_block.block_header.bits = self.BITS
        
        # Add transactions
        new_block.add_transaction(coinbase_tx)
        for tx in available_txns:
            new_block.add_transaction(tx)
        
        # Calculate target
        target = self._calculate_target()
        
        print(f"Mining block with {len(available_txns) + 1} transactions...")
        start_time = time.time()
        
        # Mine the block
        while True:
            if self._check_hash_meets_target(new_block.blockhash, target):
                end_time = time.time()
                print(f"Block mined in {end_time - start_time:.2f} seconds")
                print(f"Nonce: {new_block.block_header.nonce}")
                print(f"Block hash: {new_block.blockhash}")
                return new_block
            
            new_block.block_header.increment_nonce()
            new_block._update_block()  # Recalculate block hash with new nonce 