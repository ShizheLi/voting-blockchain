from typing import List, Optional
from transaction import Transaction

class TxnMemoryPool:
    def __init__(self):
        self.transactions: List[Transaction] = []
    
    def add_transaction(self, transaction: Transaction) -> None:
        """Add a transaction to the memory pool."""
        self.transactions.append(transaction)
    
    def get_transactions(self, max_count: int) -> List[Transaction]:
        """Get up to max_count transactions from the pool."""
        if max_count >= len(self.transactions):
            txns = self.transactions[:]
            self.transactions = []
            return txns
        
        txns = self.transactions[:max_count]
        self.transactions = self.transactions[max_count:]
        return txns
    
    def size(self) -> int:
        """Return the number of transactions in the pool."""
        return len(self.transactions)

    def has_pending_transactions(self) -> bool:
        """Check if there are any pending transactions in the pool."""
        return len(self.transactions) > 0 