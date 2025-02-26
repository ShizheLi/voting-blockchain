import hashlib
import json
from typing import List, Any

def double_sha256(data: str) -> str:
    """Apply SHA256 hash twice on the input data."""
    first_hash = hashlib.sha256(data.encode()).hexdigest()
    return hashlib.sha256(first_hash.encode()).hexdigest()

def create_merkle_root(transactions: List[Any]) -> str:
    """Create a Merkle root hash from a list of transactions."""
    if not transactions:
        return double_sha256("")
    
    # Convert transactions to hash strings
    hash_list = [tx.get_hash() for tx in transactions]
    
    # Keep hashing pairs until we get one final hash
    while len(hash_list) > 1:
        temp_list = []
        # Process pairs (if odd number, duplicate last one)
        for i in range(0, len(hash_list), 2):
            if i + 1 < len(hash_list):
                combined = hash_list[i] + hash_list[i + 1]
            else:
                combined = hash_list[i] + hash_list[i]
            temp_list.append(double_sha256(combined))
        hash_list = temp_list
    
    return hash_list[0]

def serialize_data(data: Any) -> str:
    """Convert any data structure to a consistent string format."""
    return json.dumps(data, sort_keys=True) 