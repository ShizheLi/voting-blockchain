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
from voting import VoteTransaction, VoterRegistry

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
    ⭐️ Welcome to Blockchain-Based Voting System CLI! ⭐️
    Type help or ? to list commands.
    """
    prompt = '(Blockchain-Based Voting System) '
    
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
    
    def _get_voter_registry(self):
        """Get the voter registry from the node."""
        if not self.node:
            print("Node is not running")
            return None
        return self.node.voter_registry

    def do_start(self, arg):
        """Start the node and connect to the network."""
        if self.node:
            print("Node is already running")
            return

        # Create initial wallet if none exists
        if not self.wallets:
            wallet = Wallet()
            print("\n╔════════════════ INITIAL WALLET ════════════════╗")
            print(f"║ Address: {wallet.get_address()}")
            self.wallets[wallet.get_address()] = wallet
            self.current_wallet = wallet
            print("╚══════════════════════════════════════════════════╝")

        print("\n┌─────────────── INITIALIZING NODE ───────────────┐")
        self.node = FullNode("DNS_SEED")
        
        print("│ Starting node services...")
        self.node.start()
        
        print("\n┌─────────────── NODE STATUS ───────────────┐")
        print(f"│ Connected Peers: {len(self.node.handshaked_peers)}")
        print(f"│ Blockchain Height: {self.node.blockchain.current_height}")
        print("└───────────────────────────────────────────┘")
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
        
        print("\n╔════════════════ NEW WALLET CREATED ════════════════╗")
        print(f"║ Address: {address}")
        print(f"║ Private Key: {wallet.get_private_key_hex()}")
        print(f"║ Public Key: {wallet.get_public_key_hex()}")
        print("╚════════════════════════════════════════════════════╝")
    
    def do_listwallet(self, arg):
        """
        List all wallets.
        Usage: listwallet
        """
        if not self.wallets:
            print("No wallets created yet")
            return
        
        print("\n╔════════════════ WALLETS ════════════════╗")
        for address, wallet in self.wallets.items():
            mark = "✓" if wallet == self.current_wallet else " "
            print(f"║ {mark} {address}")
        print("╚═════════════════════════════════════════╝")
    
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
        
        print(f"\n┌─────────────── BALANCE ───────────────┐")
        print(f"│    Address: {address}")
        print(f"│ 💰 Amount: {balance/1000:.3f} Barbaracoins")
        print("└─────────────────────────────────────────┘")
    
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
        
        print(f"\n┌─────────────── TRANSACTION SENT ───────────────┐")
        print(f"│ 🆔 Transaction ID: {tx.transaction_hash}")
        print(f"│ 💰 Amount: {amount:.3f} Barbaracoins")
        print(f"│ 👤 Recipient: {recipient}")
        if change > 0:
            print(f"│    Change: {change/1000:.3f} Barbaracoins")
        print("└───────────────────────────────────────────────┘")
    
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
        
        print("\n╔════════════════ BLOCK INFORMATION ════════════════╗")
        print(f"║    Hash: {block.blockhash}")
        print(f"║    Previous Block: {block.block_header.hash_prev_block}")
        print(f"║    Merkle Root: {block.block_header.hash_merkle_root}")
        print(f"║ 🕒 Timestamp: {time.ctime(block.block_header.timestamp)}")
        print(f"║     Nonce: {block.block_header.nonce}")
        print(f"║ 📝 Transaction Count: {len(block.transactions)}")
        
        if '--verbose' in arg:
            print("\n┌─────────────── TRANSACTIONS ───────────────┐")
            for tx in block.transactions:
                print(f"\n│ 🆔 Transaction: {tx.transaction_hash}")
                print(f"│    Input Count: {tx.in_counter}")
                print(f"│    Output Count: {tx.out_counter}")
                for output in tx.list_of_outputs:
                    print(f"│   💰 Output: {output.value/1000:.3f} coins to {output.script}")
        print("╚═══════════════════════════════════════════════════╝")
    
    def do_getpeers(self, arg):
        """
        List connected peers.
        Usage: getpeers
        """
        if not self.node:
            print("Node is not running")
            return
        
        print("\n╔════════════════ CONNECTED PEERS ════════════════╗")
        for peer in self.node.handshaked_peers:
            print(f"║ 🖥️ {peer}")
        print(f"\n║    Total: {len(self.node.handshaked_peers)} peers")
        print("╚═══════════════════════════════════════════════════╝")
    
    def do_getmempoolinfo(self, arg):
        """
        Get memory pool information.
        Usage: getmempoolinfo
        """
        if not self.node:
            print("Node is not running")
            return
        
        print("\n╔════════════════ MEMORY POOL INFO ════════════════╗")
        print(f"║ 📝 Transaction Count: {self.node.mempool.size()}")
        
        if '--verbose' in arg:
            print("\n┌─────────────── PENDING TRANSACTIONS ───────────────┐")
            for tx in self.node.mempool.transactions:
                print(f"│ 🆔 {tx.transaction_hash}: {len(tx.list_of_outputs)} outputs")
        print("╚════════════════════════════════════════════════════╝")
    
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
        print("\n╔════════════════ MINING STATUS ════════════════╗")
        print(f"║ ⛏️ Is Mining: {info['is_mining']}")
        print(f"║    Mining Address: {info['mining_address']}")
        print(f"║    Blockchain Height: {info['blockchain_height']}")
        print(f"║    Mempool Size: {info['mempool_size']}")
        print("╚═══════════════════════════════════════════════╝")
    
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

    def do_registervoter(self, arg):
        """
        Register a new voter.
        Usage: registervoter <voter_id>
        """
        if not arg:
            print("Usage: registervoter <voter_id>")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        if registry.register_voter(arg):
            print(f"Successfully registered voter: {arg}")
            # Broadcast voter registration to other nodes
            self.node.broadcast_voter_registration(arg)
        else:
            print(f"Failed to register voter: {arg}")

    def do_addcandidate(self, arg):
        """
        Add a new candidate to the election.
        Usage: addcandidate <candidate_name>
        """
        if not arg:
            print("Usage: addcandidate <candidate_name>")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        if registry.add_candidate(arg):
            print(f"Successfully added candidate: {arg}")
            # Broadcast candidate addition to other nodes
            self.node.broadcast_candidate_addition(arg)
        else:
            print(f"Failed to add candidate: {arg}")

    def do_startvoting(self, arg):
        """Start the voting period."""
        if not self.node:
            print("Node not started. Use 'start' command first.")
            return
        
        registry = self._get_voter_registry()
        if not registry:
            return
            
        if not registry.valid_candidates:
            print("No candidates registered. Add candidates first.")
            return
            
        # Start the voting period
        registry.start_voting()
        
        # Start mining with shorter block interval (every 10 seconds)
        self.node.start_mining(block_interval=10)
        
        print("\n╔═══════════════════ VOTING STARTED ═══════════════════╗")
        print("║ Registered candidates:")
        for candidate in registry.valid_candidates:
            print(f"║ - {candidate}")
        print("╚══════════════════════════════════════════════════════╝")

    def do_endvoting(self, arg):
        """
        End the voting period.
        Usage: endvoting
        """
        if not self.node:
            print("Node is not running")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        if not registry.is_voting_open():
            print("Voting is not currently open")
            return

        registry.end_voting()
        print("\n╔═══════════════════ VOTING ENDED ═══════════════════╗")
        self.do_results("")

    def do_vote(self, arg):
        """
        Cast a vote for a candidate.
        Usage: vote <voter_id> <candidate>
        """
        if not self.node:
            print("Node is not running. Please start the node first.")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        if not registry.is_voting_open():
            print("Voting is not currently open")
            return

        args = arg.split()
        if len(args) != 2:
            print("Usage: vote <voter_id> <candidate>")
            return

        voter_id, candidate = args

        if not registry.is_registered(voter_id):
            print(f"Error: Voter {voter_id} is not registered")
            return

        if not registry.is_valid_candidate(candidate):
            print(f"Error: {candidate} is not a valid candidate")
            return

        if registry.has_voted(voter_id):
            print(f"Error: Voter {voter_id} has already voted")
            return

        # Create and broadcast vote transaction
        vote_tx = VoteTransaction(voter_id, candidate)
        self.node.mempool.add_transaction(vote_tx)
        self.node.broadcast_transaction(vote_tx)
        registry.add_pending_vote(vote_tx)
        
        print(f"\n┌─────────────── VOTE CAST ───────────────┐")
        print(f"│    Voter: {voter_id}")
        print(f"│ 👤 Candidate: {candidate}")
        print("│ Vote is pending confirmation. Use 'votestatus <voter_id>' to check status.")
        print("└─────────────────────────────────────────┘")

    def do_votestatus(self, arg):
        """
        Check the status of a voter's vote.
        Usage: votestatus <voter_id>
        """
        if not arg:
            print("Usage: votestatus <voter_id>")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        if not registry.is_registered(arg):
            print(f"Error: Voter {arg} is not registered")
            return

        status = registry.get_vote_status(arg)
        if status:
            print(f"\n┌─────────────── VOTE STATUS ────────────┐")
            print(f"│    Voter: {arg}")
            print(f"│    Status: {status['status']}")
            print(f"│ 👤 Candidate: {status['candidate']}")
            print(f"│ 🕒 Time: {time.ctime(status['time'])}")
            print( "└────────────────────────────────────────┘")
        else:
            print(f"No vote found for voter {arg}")

    def do_pendingvotes(self, arg):
        """
        List all pending votes.
        Usage: pendingvotes
        """
        registry = self._get_voter_registry()
        if not registry:
            return

        if not registry.pending_votes:
            print("No pending votes")
            return

        print("\n╔════════════════ PENDING VOTES ════════════════╗")
        for voter_id, vote in registry.pending_votes.items():
            print(f"║    Voter: {voter_id}")
            print(f"║ 👤 Candidate: {vote.candidate}")
            print(f"║ 🕒 Time: {time.ctime(vote.timestamp)}")
            print("║--------------------------------------------")
        print("╚═══════════════════════════════════════════════╝")

    def do_listvotes(self, arg):
        """
        List all confirmed votes in the blockchain.
        Usage: listvotes
        """
        if not self.node:
            print("Node is not running")
            return

        registry = self._get_voter_registry()
        if not registry:
            return

        print("\n╔════════════════ CONFIRMED VOTES ════════════════╗")
        vote_count = 0
        processed_votes = set()  # Track processed vote transactions

        for height in range(self.node.blockchain.current_height + 1):
            block = self.node.blockchain.get_block_by_height(height)
            for tx in block.transactions:
                if hasattr(tx, 'is_vote') and tx.is_vote:
                    # Skip if we've already processed this vote transaction
                    if tx.transaction_hash in processed_votes:
                        continue
                    
                    vote_count += 1
                    processed_votes.add(tx.transaction_hash)
                    print(f"║    Block {height}:")
                    print(f"║    Voter: {tx.voter_id}")
                    print(f"║ 👤 Candidate: {tx.candidate}")
                    print(f"║ 🕒 Time: {time.ctime(tx.timestamp)}")
                    registry.confirm_vote(tx)
                    print("║--------------------------------------------")

        if vote_count == 0:
            print("║ No confirmed votes found in blockchain")
        else:
            print(f"║ 📊 Total confirmed votes: {vote_count}")
        print("╚═════════════════════════════════════════════════╝")

    def do_results(self, arg):
        """
        Display current voting results.
        Usage: results [--full]
        """
        registry = self._get_voter_registry()
        if not registry:
            return

        results = registry.get_results()
        if not results:
            print("No votes recorded yet")
            return

        print("\n╔═══════════════════ VOTING RESULTS ═══════════════════╗")
        total_votes = sum(results.values())
        
        for candidate, votes in results.items():
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            print(f"║ 👤 {candidate}: {votes} votes ({percentage:.1f}%)")

        print(f"\n║ 📊 Total votes: {total_votes}")
        
        if "--full" in arg:
            print("\n┌─────────────── VOTING DETAILS ───────────────┐")
            print("│ Confirmed votes:")
            for voter_id, vote in registry.confirmed_votes.items():
                print(f"│    {voter_id} -> {vote.candidate}")
            
            if registry.pending_votes:
                print("\n│ Pending votes:")
                for voter_id, vote in registry.pending_votes.items():
                    print(f"│ ⏳ {voter_id} -> {vote.candidate} (pending)")
        print("╚════════════════════════════════════════════════════╝")

def main():
    try:
        BlockchainCLI().cmdloop()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, exiting...")
        sys.exit(0)

if __name__ == '__main__':
    main() 