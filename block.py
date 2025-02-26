from typing import List
from header import Header
from transaction import Transaction
from utils import create_merkle_root

class Block:
    MAGIC_NUMBER: int = 0xD9B4BEF9
    
    def __init__(self, prev_block_hash: str = "0" * 64):
        self.magic_number: int = self.MAGIC_NUMBER
        self.blocksize: int = 0
        self.block_header: Header = Header(hash_prev_block=prev_block_hash)
        self.transaction_counter: int = 0
        self.transactions: List[Transaction] = []
        self.blockhash: str = ""
        self._update_block()
    
    def add_transaction(self, transaction: Transaction) -> None:
        """Add a transaction to the block and update block data."""
        self.transactions.append(transaction)
        self.transaction_counter = len(self.transactions)
        self._update_block()
    
    def _update_block(self) -> None:
        """Update block's merkle root and hash."""
        if self.transactions:
            merkle_root = create_merkle_root(self.transactions)
            self.block_header.hash_merkle_root = merkle_root
        self.blockhash = self.block_header.get_header_hash()
    
    def print_block(self) -> None:
        """Print block details."""
        print("\n=== Block Information ===")
        print(f"Block Hash: {self.blockhash}")
        print(f"Magic Number: {hex(self.magic_number)}")
        print(f"Block Size: {self.blocksize}")
        print(f"Transaction Count: {self.transaction_counter}")
        print(f"Previous Block Hash: {self.block_header.hash_prev_block}")
        print(f"Merkle Root: {self.block_header.hash_merkle_root}")
        print(f"Timestamp: {self.block_header.timestamp}")
        print(f"Bits: {self.block_header.bits}")
        print(f"Nonce: {self.block_header.nonce}")
        print("\nTransactions:")
        for tx in self.transactions:
            tx.print_transaction() 