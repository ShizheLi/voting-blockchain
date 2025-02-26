class Output:
    def __init__(self, value: int, index: int, script: str):
        """
        Initialize an Output.
        Args:
            value: Value in milli-Barbaracoins (1/1000ths of a Barbaracoin)
            index: Output index
            script: Script string (simplified for this implementation)
        """
        self.value: int = value  # Value in milli-Barbaracoins
        self.index: int = index
        self.script: str = script
    
    def to_dict(self) -> dict:
        """Convert output to dictionary for serialization."""
        return {
            'value': self.value,
            'index': self.index,
            'script': self.script
        } 