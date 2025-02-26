from blockchain import Blockchain
from transaction import Transaction
from mempool import TxnMemoryPool
from miner import Miner
import random
import time

def create_random_transaction() -> Transaction:
    """Create a random transaction for testing."""
    tx = Transaction()
    # Create a random input (hash of timestamp + random number)
    input_data = f"tx_{int(time.time())}_{random.randint(0, 1000000)}"
    tx.add_input(input_data)
    
    # Create 1-3 outputs with random values between 0.1 and 10 Barbaracoins
    num_outputs = random.randint(1, 3)
    for i in range(num_outputs):
        value = random.randint(100, 10000)  # 0.1 to 10 Barbaracoins in milli-Barbaracoins
        script = f"Address_{random.randint(1000, 9999)}"
        tx.add_output(value, script)
    
    return tx

def main():
    # Create blockchain and mempool
    blockchain = Blockchain()
    mempool = TxnMemoryPool()
    
    # Create miner
    miner = Miner(blockchain, mempool, "MinerAddress_001")
    
    # Create 91 random transactions
    print("Creating 91 random transactions...")
    for _ in range(91):
        tx = create_random_transaction()
        mempool.add_transaction(tx)
    
    print(f"Initial mempool size: {mempool.size()}")
    
    # Mine blocks until mempool is empty
    while mempool.size() > 0:
        mined_block = miner.mine_block()
        if mined_block:
            blockchain.add_block(mined_block.transactions)
            print(f"Block added at height {blockchain.current_height}")
            print(f"Remaining transactions in mempool: {mempool.size()}")
    
    print(f"\nFinal blockchain height: {blockchain.current_height}")
    print("Mining complete!")

if __name__ == "__main__":
    main() 