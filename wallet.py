import hashlib
import random
import binascii
from typing import Tuple

class Base58(object):
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    
    @staticmethod
    def encode(data: bytes) -> str:
        # Convert bytes to integer
        n = int.from_bytes(data, byteorder='big')
        
        # Divide that integer into base58
        res = []
        while n > 0:
            n, r = divmod(n, 58)
            res.append(Base58.alphabet[r])
        res = ''.join(reversed(res))
        
        # Add '1' characters for leading zero bytes
        for i in range(len(data)):
            if data[i] == 0:
                res = '1' + res
            else:
                break
                
        return res
    
    @staticmethod
    def decode(string: str) -> bytes:
        n = 0
        for char in string:
            n *= 58
            n += Base58.alphabet.index(char)
        return n.to_bytes((n.bit_length() + 7) // 8, byteorder='big')

class Wallet:
    VERSION_BYTE = b'\x00'  # Version byte for mainnet addresses
    
    def __init__(self):
        self.private_key = self._generate_private_key()
        self.public_key = self._generate_public_key()
        self.address = self._generate_address()
    
    def _generate_private_key(self) -> bytes:
        """Generate a random 32-byte private key."""
        return random.getrandbits(256).to_bytes(32, byteorder='big')
    
    def _generate_public_key(self) -> bytes:
        """
        Generate a public key from the private key.
        Note: In a real implementation, this would use elliptic curve multiplication.
        For this example, we'll use a simplified version.
        """
        return hashlib.sha256(self.private_key).digest()
    
    def _generate_address(self) -> str:
        """Generate a Bitcoin-style address using base58check encoding."""
        # Step 1: Apply SHA-256 to the public key
        sha256_hash = hashlib.sha256(self.public_key).digest()
        
        # Step 2: Apply RIPEMD-160 to the result
        ripemd160_hash = hashlib.new('ripemd160')
        ripemd160_hash.update(sha256_hash)
        hash160 = ripemd160_hash.digest()
        
        # Step 3: Add version byte in front
        versioned_hash = self.VERSION_BYTE + hash160
        
        # Step 4: Calculate checksum (double SHA-256)
        first_hash = hashlib.sha256(versioned_hash).digest()
        second_hash = hashlib.sha256(first_hash).digest()
        checksum = second_hash[:4]
        
        # Step 5: Concatenate versioned hash and checksum
        binary_address = versioned_hash + checksum
        
        # Step 6: Convert to base58
        address = Base58.encode(binary_address)
        
        return address
    
    @staticmethod
    def verify_address(address: str) -> bool:
        """Verify if a Bitcoin address is valid."""
        try:
            # Decode from base58
            decoded = Base58.decode(address)
            
            # Check length
            if len(decoded) != 25:
                return False
            
            # Split into parts
            version = decoded[0:1]
            hash160 = decoded[1:21]
            checksum = decoded[21:]
            
            # Verify checksum
            versioned_hash = version + hash160
            first_hash = hashlib.sha256(versioned_hash).digest()
            second_hash = hashlib.sha256(first_hash).digest()
            expected_checksum = second_hash[:4]
            
            return checksum == expected_checksum
        except:
            return False
    
    def get_address(self) -> str:
        """Get the wallet's address."""
        return self.address
    
    def get_private_key_hex(self) -> str:
        """Get the private key in hexadecimal format."""
        return binascii.hexlify(self.private_key).decode()
    
    def get_public_key_hex(self) -> str:
        """Get the public key in hexadecimal format."""
        return binascii.hexlify(self.public_key).decode()

def main():
    # Create a new wallet
    wallet = Wallet()
    
    # Print wallet details
    print("New Wallet Created:")
    print(f"Private Key: {wallet.get_private_key_hex()}")
    print(f"Public Key: {wallet.get_public_key_hex()}")
    print(f"Address: {wallet.get_address()}")
    
    # Verify the address
    is_valid = Wallet.verify_address(wallet.get_address())
    print(f"\nAddress is valid: {is_valid}")

if __name__ == "__main__":
    main() 