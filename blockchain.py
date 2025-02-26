from typing import Optional, Dict, List
from block import Block
from transaction import Transaction

class Blockchain:
    def __init__(self):
        self.blocks: Dict[str, Block] = {}  # hash -> block mapping
        self.height_map: Dict[int, str] = {}  # height -> hash mapping
        self.transaction_map: Dict[str, Transaction] = {}  # transaction_hash -> transaction mapping
        self.current_height: int = -1
        self._create_genesis_block()
    
    def _create_genesis_block(self) -> None:
        """Create the genesis block with a default transaction."""
        genesis_block = Block()
        
        # Create a genesis transaction (coinbase)
        genesis_tx = Transaction.create_coinbase(
            value=50_000,  # 50 Barbaracoins
            recipient_script="Genesis Miner"
        )
        genesis_block.add_transaction(genesis_tx)
        
        self._add_block(genesis_block)
    
    def _add_block(self, block: Block) -> None:
        """Add a block to the blockchain."""
        self.current_height += 1
        self.blocks[block.blockhash] = block
        self.height_map[self.current_height] = block.blockhash
        
        # Add transactions to the transaction map
        for tx in block.transactions:
            self.transaction_map[tx.transaction_hash] = tx
    
    def add_block(self, transactions: List[Transaction]) -> None:
        """Add a new block with the given transactions."""
        prev_block_hash = self.height_map[self.current_height]
        new_block = Block(prev_block_hash)
        
        for tx in transactions:
            new_block.add_transaction(tx)
        
        self._add_block(new_block)
    
    def get_block_by_height(self, height: int) -> Optional[Block]:
        """Get a block by its height."""
        if height in self.height_map:
            block_hash = self.height_map[height]
            return self.blocks[block_hash]
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get a block by its hash."""
        return self.blocks.get(block_hash)
    
    def get_transaction_by_hash(self, tx_hash: str) -> Optional[Transaction]:
        """Get a transaction by its hash."""
        return self.transaction_map.get(tx_hash)

def main():
    # Create blockchain
    blockchain = Blockchain()
    
    # Create 10 test transactions
    transactions = []
    for i in range(10):
        tx = Transaction()
        tx.add_input(f"Input {i}")
        tx.add_output(f"Output {i}")
        transactions.append(tx)
    
    # Add first 5 transactions to block 1
    blockchain.add_block(transactions[:5])
    
    # Add remaining 5 transactions to block 2
    blockchain.add_block(transactions[5:])
    
    # Test Function 1: Get block by height
    print("\nTesting get_block_by_height(1):")
    block = blockchain.get_block_by_height(1)
    if block:
        block.print_block()
    
    # Test Function 2: Get transaction by hash
    # Use the hash from one of the transactions we created
    test_tx_hash = transactions[3].transaction_hash
    print("\nTesting get_transaction_by_hash:")
    tx = blockchain.get_transaction_by_hash(test_tx_hash)
    if tx:
        tx.print_transaction()

if __name__ == "__main__":
    main() 