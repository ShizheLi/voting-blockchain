from utils import double_sha256, serialize_data
import time

class Header:
    def __init__(self, hash_merkle_root: str = "", hash_prev_block: str = "0" * 64):
        self.version: int = 1
        self.hash_prev_block: str = hash_prev_block
        self.hash_merkle_root: str = hash_merkle_root
        self.timestamp: int = int(time.time())
        self.bits: int = 0  # Difficulty target (not implemented for this simple version)
        self.nonce: int = 0
    
    def get_header_hash(self) -> str:
        """Calculate and return the header hash."""
        data = {
            'timestamp': self.timestamp,
            'hash_merkle_root': self.hash_merkle_root,
            'bits': self.bits,
            'nonce': self.nonce,
            'hash_prev_block': self.hash_prev_block
        }
        return double_sha256(serialize_data(data))
    
    def increment_nonce(self) -> None:
        """Increment the nonce value."""
        self.nonce += 1 