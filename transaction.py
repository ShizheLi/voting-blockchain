from typing import List
from utils import double_sha256, serialize_data
from output import Output
import time
import random

class Transaction:
    def __init__(self, version_number: int = 1, is_coinbase: bool = False):
        self.version_number: int = version_number
        self.in_counter: int = 0
        self.list_of_inputs: List[str] = []
        self.out_counter: int = 0
        self.list_of_outputs: List[Output] = []
        self.transaction_hash: str = ""
        self.is_coinbase = is_coinbase
        self._calculate_hash()
    
    @classmethod
    def create_coinbase(cls, value: int, recipient_script: str) -> 'Transaction':
        """Create a coinbase transaction that generates new Barbaracoins."""
        tx = cls(is_coinbase=True)
        # Coinbase transactions have one dummy input
        tx.add_input(f"coinbase_{int(time.time())}_{random.randint(0, 1000000)}")
        # Add the block reward output
        tx.add_output(value, recipient_script)
        return tx
    
    def add_input(self, input_data: str) -> None:
        """Add an input to the transaction."""
        self.list_of_inputs.append(input_data)
        self.in_counter = len(self.list_of_inputs)
        self._calculate_hash()
    
    def add_output(self, value: int, script: str) -> None:
        """Add an output to the transaction."""
        output = Output(value, len(self.list_of_outputs), script)
        self.list_of_outputs.append(output)
        self.out_counter = len(self.list_of_outputs)
        self._calculate_hash()
    
    def _calculate_hash(self) -> None:
        """Calculate the transaction hash based on all fields."""
        data = {
            'version': self.version_number,
            'in_counter': self.in_counter,
            'inputs': self.list_of_inputs,
            'out_counter': self.out_counter,
            'outputs': [output.to_dict() for output in self.list_of_outputs],
            'is_coinbase': self.is_coinbase
        }
        self.transaction_hash = double_sha256(serialize_data(data))
    
    def get_hash(self) -> str:
        """Return the transaction hash."""
        return self.transaction_hash
    
    def print_transaction(self) -> None:
        """Print transaction details."""
        print(f"\nTransaction Hash: {self.transaction_hash}")
        print(f"Version Number: {self.version_number}")
        print(f"Is Coinbase: {self.is_coinbase}")
        print(f"Input Count: {self.in_counter}")
        print("Inputs:", self.list_of_inputs)
        print(f"Output Count: {self.out_counter}")
        print("Outputs:")
        for output in self.list_of_outputs:
            print(f"  Value: {output.value/1000:.3f} Barbaracoins")
            print(f"  Index: {output.index}")
            print(f"  Script: {output.script}") 