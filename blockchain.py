from typing import Optional, Dict, List
from block import Block
from transaction import Transaction
import logging
from wallet import Wallet

class Blockchain:
    def __init__(self):
        self.blocks: Dict[str, Block] = {}  # hash -> block mapping
        self.height_map: Dict[int, str] = {}  # height -> hash mapping
        self.transaction_map: Dict[str, Transaction] = {}  # transaction_hash -> transaction mapping
        self.utxo_set: Dict[str, List[Output]] = {}  # txid -> list of unspent outputs
        self.current_height: int = -1
        self._create_genesis_block()
    
    def _create_genesis_block(self) -> None:
        """Create the genesis block with a default transaction."""
        genesis_wallet = Wallet()
        genesis_block = Block()
        
        # Create a genesis transaction (coinbase)
        genesis_tx = Transaction.create_coinbase(
            value=50_000,  # 50 Barbaracoins
            recipient_script=genesis_wallet.get_address()  # Use a real wallet address
        )
        genesis_block.add_transaction(genesis_tx)
        print(f"Genesis block created with reward to address: {genesis_wallet.get_address()}")
        
        self._add_block(genesis_block)
    
    def _add_to_utxo(self, tx: Transaction) -> None:
        """Add transaction outputs to UTXO set."""
        self.utxo_set[tx.transaction_hash] = tx.list_of_outputs.copy()
        logging.info(f"Added {len(tx.list_of_outputs)} outputs to UTXO set for tx {tx.transaction_hash[:8]}")
        logging.debug(f"UTXO set size: {sum(len(outputs) for outputs in self.utxo_set.values())}")
    
    def _remove_from_utxo(self, tx_hash: str, output_index: int) -> None:
        """Remove a spent output from UTXO set."""
        if tx_hash in self.utxo_set and output_index < len(self.utxo_set[tx_hash]):
            del self.utxo_set[tx_hash][output_index]
            if not self.utxo_set[tx_hash]:  # If no outputs left
                del self.utxo_set[tx_hash]
            logging.info(f"Removed output {output_index} from UTXO set for tx {tx_hash[:8]}")
            logging.debug(f"UTXO set size: {sum(len(outputs) for outputs in self.utxo_set.values())}")
    
    def validate_transaction(self, tx: Transaction) -> bool:
        """Validate a transaction against the current state."""
        if tx.is_coinbase:
            logging.info("Validating coinbase transaction")
            return True
        
        logging.info(f"Validating transaction {tx.transaction_hash[:8]}")
        
        # Check if inputs exist in UTXO set
        for tx_input in tx.list_of_inputs:
            input_parts = tx_input.split(':')
            if len(input_parts) != 2:
                logging.error(f"Invalid input format: {tx_input}")
                return False
            
            prev_tx_hash, output_index = input_parts
            output_index = int(output_index)
            
            if prev_tx_hash not in self.utxo_set or output_index >= len(self.utxo_set[prev_tx_hash]):
                logging.error(f"Input {tx_input} not found in UTXO set")
                return False
        
        logging.info(f"Transaction {tx.transaction_hash[:8]} validated successfully")
        return True
    
    def _add_block(self, block: Block) -> None:
        """Add a block to the blockchain."""
        self.current_height += 1
        self.blocks[block.blockhash] = block
        self.height_map[self.current_height] = block.blockhash
        
        logging.info(f"Adding block {block.blockhash[:8]} at height {self.current_height}")
        logging.info(f"Block contains {len(block.transactions)} transactions")
        
        # Process transactions
        for tx in block.transactions:
            # Remove spent inputs from UTXO set
            if not tx.is_coinbase:
                for tx_input in tx.list_of_inputs:
                    input_parts = tx_input.split(':')
                    if len(input_parts) == 2:
                        prev_tx_hash, output_index = input_parts
                        self._remove_from_utxo(prev_tx_hash, int(output_index))
            
            # Add new outputs to UTXO set
            self._add_to_utxo(tx)
            
            # Add to transaction map
            self.transaction_map[tx.transaction_hash] = tx
        
        logging.info(f"Block {block.blockhash[:8]} added successfully")
    
    def add_block(self, transactions: List[Transaction]) -> None:
        """Add a new block with the given transactions."""
        # Validate all transactions
        for tx in transactions:
            if not tx.is_coinbase and not self.validate_transaction(tx):
                logging.error(f"Transaction validation failed for {tx.transaction_hash[:8]}")
                return
        
        prev_block_hash = self.height_map[self.current_height]
        new_block = Block(prev_block_hash)
        
        for tx in transactions:
            new_block.add_transaction(tx)
        
        self._add_block(new_block)
        
        logging.info(f"New block added with {len(transactions)} transactions")
        logging.info(f"Current blockchain height: {self.current_height}")
        logging.info(f"Total UTXO count: {sum(len(outputs) for outputs in self.utxo_set.values())}")
    
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