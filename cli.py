import cmd
import sys
import time
import logging
from typing import Optional, Dict
import grpc
from wallet import Wallet
from blockchain import Blockchain
from transaction import Transaction
from block import Block
from network.full_node import FullNode
from proto.generated import blockchain_pb2, blockchain_pb2_grpc
import threading

class CLILoggingHandler(logging.Handler):
    def __init__(self, cli):
        super().__init__()
        self.cli = cli
    
    def emit(self, record):
        try:
            msg = self.format(record)
            # Save current line content
            try:
                line = self.cli.cmdqueue[0]
            except IndexError:
                line = ''
            # Clear current line
            self.cli.stdout.write('\r' + ' ' * (len(self.cli.prompt) + len(line)) + '\r')
            # Write log message
            self.cli.stdout.write(msg + '\n')
            # Rewrite prompt and current line
            self.cli.stdout.write(self.cli.prompt + line)
            self.cli.stdout.flush()
        except Exception:
            self.handleError(record)

class BlockchainCLI(cmd.Cmd):
    intro = """
    Welcome to BarbaraCoin CLI!
    Type help or ? to list commands.
    """
    prompt = '(barbaracoin) '
    
    def __init__(self):
        super().__init__()
        self.node: Optional[FullNode] = None
        self.wallets: Dict[str, Wallet] = {}  # address -> wallet mapping
        self.current_wallet: Optional[Wallet] = None
        
        # Set up custom logging handler
        handler = CLILoggingHandler(self)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S'))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
    
    def do_start(self, arg):
        """Start the node and connect to the network."""
        if self.node:
            print("Node is already running")
            return

        # Create initial wallet if none exists
        if not self.wallets:
            wallet = Wallet()
            print("\nCreated initial wallet:")
            print(f"Address: {wallet.get_address()}")
            self.wallets[wallet.get_address()] = wallet
            self.current_wallet = wallet

        print("\nInitializing node...")
        self.node = FullNode("DNS_SEED")
        
        print("Starting node services...")
        self.node.start()
        
        print("\nNode Status:")
        print(f"Connected Peers: {len(self.node.handshaked_peers)}")
        print(f"Blockchain Height: {self.node.blockchain.current_height}")
        print("\nNode started successfully. Use 'startmining' to begin mining blocks")
    
    def do_createwallet(self, arg):
        """
        Create a new wallet.
        Usage: createwallet
        """
        wallet = Wallet()
        address = wallet.get_address()
        self.wallets[address] = wallet
        self.current_wallet = wallet
        
        print("\nNew wallet created:")
        print(f"Address: {address}")
        print(f"Private Key: {wallet.get_private_key_hex()}")
        print(f"Public Key: {wallet.get_public_key_hex()}")
    
    def do_listwallet(self, arg):
        """
        List all wallets.
        Usage: listwallet
        """
        if not self.wallets:
            print("No wallets created yet")
            return
        
        print("\nWallets:")
        for address, wallet in self.wallets.items():
            mark = "*" if wallet == self.current_wallet else " "
            print(f"{mark} {address}")
    
    def do_selectwallet(self, arg):
        """
        Select a wallet as current wallet.
        Usage: selectwallet <address>
        """
        if not arg:
            print("Please provide a wallet address")
            return
        
        if arg not in self.wallets:
            print("Wallet not found")
            return
        
        self.current_wallet = self.wallets[arg]
        print(f"Selected wallet: {arg}")
    
    def do_getbalance(self, arg):
        """
        Get balance of current wallet or specified address.
        Usage: getbalance [address]
        """
        if not self.node:
            print("Node is not running")
            return
        
        address = arg if arg else (self.current_wallet.get_address() if self.current_wallet else None)
        if not address:
            print("No wallet selected and no address provided")
            return
        
        # Calculate balance from UTXO set
        balance = 0
        for tx_hash, outputs in self.node.blockchain.utxo_set.items():
            for output in outputs:
                if output.script == address:  # In our simplified model, script is the address
                    balance += output.value
        
        print(f"\nBalance for {address}:")
        print(f"{balance/1000:.3f} Barbaracoins")
    
    def do_sendcoins(self, arg):
        """
        Send coins to an address.
        Usage: sendcoins <recipient_address> <amount>
        """
        if not self.node:
            print("Node is not running")
            return
        
        if not self.current_wallet:
            print("No wallet selected")
            return
        
        args = arg.split()
        if len(args) != 2:
            print("Invalid arguments. Usage: sendcoins <recipient_address> <amount>")
            return
        
        recipient, amount = args[0], float(args[1])
        amount_milli = int(amount * 1000)  # Convert to milli-Barbaracoins
        
        # Create and broadcast transaction
        tx = Transaction()
        sender_address = self.current_wallet.get_address()
        
        # Find enough UTXOs to cover the amount
        total_input = 0
        for tx_hash, outputs in self.node.blockchain.utxo_set.items():
            for i, output in enumerate(outputs):
                if output.script == sender_address:
                    tx.add_input(f"{tx_hash}:{i}")
                    total_input += output.value
                    if total_input >= amount_milli:
                        break
            if total_input >= amount_milli:
                break
        
        if total_input < amount_milli:
            print("Insufficient funds")
            return
        
        # Add recipient output
        tx.add_output(amount_milli, recipient)
        
        # Add change output if necessary
        change = total_input - amount_milli
        if change > 0:
            tx.add_output(change, sender_address)
        
        # Broadcast transaction
        self.node.mempool.add_transaction(tx)
        self.node.seen_transactions.add(tx.transaction_hash)
        self.node.broadcast_transaction(tx)
        
        print(f"\nTransaction sent: {tx.transaction_hash}")
        print(f"Amount: {amount:.3f} Barbaracoins")
        print(f"Recipient: {recipient}")
        if change > 0:
            print(f"Change: {change/1000:.3f} Barbaracoins")
    
    def do_getblockcount(self, arg):
        """
        Get the current block height.
        Usage: getblockcount
        """
        if not self.node:
            print("Node is not running")
            return
        
        height = self.node.blockchain.current_height
        print(f"Current block height: {height}")
    
    def do_getblock(self, arg):
        """
        Get block information by height or hash.
        Usage: getblock <height_or_hash>
        """
        if not self.node:
            print("Node is not running")
            return
        
        if not arg:
            print("Please provide block height or hash")
            return
        
        # Try to get block by height first
        try:
            height = int(arg)
            block = self.node.blockchain.get_block_by_height(height)
        except ValueError:
            # If not an integer, try as hash
            block = self.node.blockchain.get_block_by_hash(arg)
        
        if not block:
            print("Block not found")
            return
        
        print("\nBlock Information:")
        print(f"Hash: {block.blockhash}")
        print(f"Previous Block: {block.block_header.hash_prev_block}")
        print(f"Merkle Root: {block.block_header.hash_merkle_root}")
        print(f"Timestamp: {time.ctime(block.block_header.timestamp)}")
        print(f"Nonce: {block.block_header.nonce}")
        print(f"Transaction Count: {len(block.transactions)}")
        
        if '--verbose' in arg:
            print("\nTransactions:")
            for tx in block.transactions:
                print(f"\n  Transaction: {tx.transaction_hash}")
                print(f"  Input Count: {tx.in_counter}")
                print(f"  Output Count: {tx.out_counter}")
                for output in tx.list_of_outputs:
                    print(f"    Output: {output.value/1000:.3f} coins to {output.script}")
    
    def do_getpeers(self, arg):
        """
        List connected peers.
        Usage: getpeers
        """
        if not self.node:
            print("Node is not running")
            return
        
        print("\nConnected Peers:")
        for peer in self.node.handshaked_peers:
            print(f"  {peer}")
        print(f"\nTotal: {len(self.node.handshaked_peers)} peers")
    
    def do_getmempoolinfo(self, arg):
        """
        Get memory pool information.
        Usage: getmempoolinfo
        """
        if not self.node:
            print("Node is not running")
            return
        
        print("\nMemory Pool Information:")
        print(f"Transaction Count: {self.node.mempool.size()}")
        
        if '--verbose' in arg:
            print("\nPending Transactions:")
            for tx in self.node.mempool.transactions:
                print(f"  {tx.transaction_hash}: {len(tx.list_of_outputs)} outputs")
    
    def do_startmining(self, arg):
        """Start mining blocks."""
        if not self.node:
            print("Node is not running. Use 'start' command first.")
            return
            
        if self.node.start_mining():
            print(f"Mining started. Mining rewards will be sent to: {self.current_wallet.get_address()}")
        else:
            print("Mining is already running")
            
    def do_stopmining(self, arg):
        """Stop mining blocks."""
        if not self.node:
            print("Node is not running")
            return
            
        if self.node.stop_mining():
            print("Mining stopped")
        else:
            print("Mining is not running")
            
    def do_getmininginfo(self, arg):
        """Get current mining status and information."""
        if not self.node:
            print("Node is not running")
            return
            
        info = self.node.get_mining_info()
        print("\nMining Status:")
        print(f"Is Mining: {info['is_mining']}")
        print(f"Mining Address: {info['mining_address']}")
        print(f"Blockchain Height: {info['blockchain_height']}")
        print(f"Mempool Size: {info['mempool_size']}")
    
    def do_exit(self, arg):
        """
        Exit the CLI.
        Usage: exit
        """
        if self.node:
            print("Stopping node...")
            self.node.mining_event.set()
            self.node.server.stop(0)
        print("Goodbye!")
        return True

def main():
    try:
        BlockchainCLI().cmdloop()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, exiting...")
        sys.exit(0)

if __name__ == '__main__':
    main() 