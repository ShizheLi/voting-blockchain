import grpc
import time
import socket
import random
import json
import threading
from concurrent import futures
from typing import Set, Dict
import pickle
import logging
from wallet import Wallet
from utils import double_sha256

from proto.generated import blockchain_pb2
from proto.generated import blockchain_pb2_grpc
from blockchain import Blockchain
from transaction import Transaction
from mempool import TxnMemoryPool
from block import Block

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Changed to INFO as base level
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Mining difficulty target (making it easier to mine blocks)
TARGET_BITS = 0x2100ffff
HEX_TARGET = 0x00ffff0000000000000000000000000000000000000000000000000000000000

class FullNodeServicer(blockchain_pb2_grpc.FullNodeServiceServicer):
    def __init__(self, node):
        self.node = node
    
    def Handshake(self, request, context):
        """Handle incoming handshake requests."""
        # Extract handshake information
        version = request.version
        node_time = request.time
        node_addr = request.addr_me
        best_height = request.best_height
        
        logging.debug(f"Received handshake from node {node_addr}")
        logging.debug(f"  Version: {version}")
        logging.debug(f"  Time: {time.ctime(node_time)}")
        logging.debug(f"  Best Height: {best_height}")
        
        # Add the node to our known peers and mark as handshaked
        self.node.add_peer(node_addr, handshaked=True)
        
        # Start a background thread to handshake with the new node
        if self.node.should_handshake(node_addr):
            threading.Thread(
                target=self.node.handshake_with_node,
                args=(node_addr,),
                daemon=True
            ).start()
        
        # Prepare registry data for synchronization
        registry_data = {
            'candidates': list(self.node.voter_registry.valid_candidates),
            'voters': list(self.node.voter_registry.registered_voters),
            'voting_open': self.node.voter_registry.voting_open
        }
        
        # Send registry data along with node addresses
        response = blockchain_pb2.NodeList(
            node_addresses=list(self.node.known_peers),
            registry_data=json.dumps(registry_data).encode()
        )
        
        return response
    
    def NewTransactionBroadcast(self, request, context):
        """Handle incoming transaction broadcast."""
        tx_hash = request.transaction_hash
        
        # Handle non-transaction messages (candidate additions and voter registrations)
        if tx_hash == "message":
            try:
                message_data = request.serialized_data.decode()
                self.node.handle_message(message_data)
                return blockchain_pb2.BroadcastResponse(
                    success=True,
                    message="Message processed successfully"
                )
            except Exception as e:
                return blockchain_pb2.BroadcastResponse(
                    success=False,
                    message=f"Failed to process message: {str(e)}"
                )
        
        # Check if we've already seen this transaction
        if tx_hash in self.node.seen_transactions:
            logging.debug(f"Ignoring already seen transaction: {tx_hash[:8]}...")
            return blockchain_pb2.BroadcastResponse(
                success=True,
                message="Transaction already known"
            )
        
        # Add to seen transactions before processing to prevent duplicates
        self.node.seen_transactions.add(tx_hash)
        
        # Deserialize transaction data
        tx_data = json.loads(request.serialized_data.decode())
        
        # Create appropriate transaction type
        if tx_data.get('is_vote', False):
            from voting import VoteTransaction
            tx = VoteTransaction.from_dict(tx_data)
            # Update voter registry
            self.node.voter_registry.add_pending_vote(tx)
        else:
            tx = Transaction()
            tx.version_number = tx_data['version']
            tx.list_of_inputs = tx_data['inputs']
            tx.in_counter = len(tx.list_of_inputs)
            tx.list_of_outputs = [Output(**output) for output in tx_data['outputs']]
            tx.out_counter = len(tx.list_of_outputs)
            tx.is_coinbase = tx_data['is_coinbase']
            tx._calculate_hash()
        
        logging.info(f"Received new transaction: {tx_hash[:8]}...")
        
        self.node.mempool.add_transaction(tx)
        self.node.broadcast_transaction(tx, exclude_peer=context.peer())
        
        return blockchain_pb2.BroadcastResponse(
            success=True,
            message="Transaction accepted and propagated"
        )
    
    def NewBlockBroadcast(self, request, context):
        """Handle incoming block broadcast."""
        block_hash = request.block_hash
        
        if block_hash in self.node.seen_blocks:
            logging.debug(f"Ignoring already seen block: {block_hash[:8]}...")
            return blockchain_pb2.BroadcastResponse(
                success=True,
                message="Block already known"
            )
        
        block = pickle.loads(request.serialized_data)
        logging.info(f"Received new block: {block_hash[:8]}...")
        logging.info(f"Block contains {len(block.transactions)} transactions")
        
        self.node.blockchain.add_block(block.transactions)
        self.node.seen_blocks.add(block_hash)
        
        time.sleep(random.randint(0, 3))
        self.node.broadcast_block(block, exclude_peer=context.peer())
        
        return blockchain_pb2.BroadcastResponse(
            success=True,
            message="Block accepted and propagated"
        )

    def handle_message(self, message):
        """Handle incoming messages from peers"""
        try:
            message_data = message.decode()
            message_json = json.loads(message_data)
            
            if message_json.get('type') == 'candidate_addition':
                self.node.handle_candidate_addition(message_data)
            elif message_json.get('type') == 'voter_registration':
                self.node.handle_voter_registration(message_data)
            else:
                # Handle other message types
                pass
                
        except json.JSONDecodeError:
            logging.error("Failed to decode message as JSON")
        except Exception as e:
            logging.error(f"Error handling message: {e}")

class FullNode:
    def __init__(self, dns_seed_host: str, dns_seed_port: int = 58333, node_port: int = 58333):
        self.version = 1
        self.addr_me = self._get_my_ip()
        self.dns_seed_addr = f"{dns_seed_host}:{dns_seed_port}"
        self.node_port = node_port
        self.known_peers: Set[str] = set()  # All known peer addresses
        self.handshaked_peers: Set[str] = set()  # Peers we've already handshaked with
        self.seen_transactions: Set[str] = set()  # Transaction hashes we've seen
        self.seen_blocks: Set[str] = set()  # Block hashes we've seen
        self.handshake_lock = threading.Lock()  # Lock for thread-safe handshaking
        
        # Initialize blockchain and mempool
        self.blockchain = Blockchain()
        self.mempool = TxnMemoryPool()
        self.best_height = 0  # Initially only has genesis block
        
        # Initialize voter registry
        from voting import VoterRegistry
        self.voter_registry = VoterRegistry()
        
        # Create gRPC server
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        blockchain_pb2_grpc.add_FullNodeServiceServicer_to_server(
            FullNodeServicer(self), self.server
        )
        
        # Mining control
        self.mining_event = threading.Event()
        self.mining_thread = None
        self.mining_block = None  # Current block being mined
        self.mining_transactions = set()  # Transactions in current mining block
        self.chain_work = {}  # Track work for each chain tip
        self.fork_points = {}  # Track potential fork points
        self.new_transaction_event = threading.Event()  # Signal for new transaction
        self.last_block_time = 0  # Track when the last block was mined

    def handle_message(self, message_data):
        """Handle incoming messages from peers"""
        try:
            message_json = json.loads(message_data)
            
            if message_json.get('type') == 'candidate_addition':
                self.handle_candidate_addition(message_data)
            elif message_json.get('type') == 'voter_registration':
                self.handle_voter_registration(message_data)
            else:
                # Handle other message types
                pass
                
        except json.JSONDecodeError:
            logging.error("Failed to decode message as JSON")
        except Exception as e:
            logging.error(f"Error handling message: {e}")

    def generate_random_transaction(self) -> Transaction:
        """Generate a random transaction for testing."""
        # Create a coinbase transaction instead of random transactions
        tx = Transaction.create_coinbase(
            value=50_000,  # 50 Barbaracoins
            recipient_script=self.current_wallet.get_address() if hasattr(self, 'current_wallet') else Wallet().get_address()
        )
        return tx
    
    def broadcast_transaction(self, tx: Transaction, exclude_peer: str = None):
        """Broadcast transaction to all known peers."""
        # Prepare the broadcast message
        if hasattr(tx, 'to_dict'):
            tx_data = tx.to_dict()
        else:
            tx_data = {
                'version': tx.version_number,
                'inputs': tx.list_of_inputs,
                'outputs': [output.to_dict() for output in tx.list_of_outputs],
                'is_coinbase': tx.is_coinbase
            }
        
        serialized_data = json.dumps(tx_data).encode()
        broadcast_msg = blockchain_pb2.NewTransaction(
            serialized_data=serialized_data,
            transaction_hash=tx.transaction_hash
        )
        
        # Make a copy of handshaked peers to avoid concurrent modification
        with self.handshake_lock:
            peers_to_broadcast = list(self.handshaked_peers)
        
        logging.info(f"Broadcasting transaction {tx.transaction_hash[:8]} to {len(peers_to_broadcast)} peers")
        successful_broadcasts = 0
        
        # Broadcast to all handshaked peers except the excluded one
        for peer in peers_to_broadcast:
            if peer != exclude_peer:
                try:
                    with grpc.insecure_channel(f"{peer}:{self.node_port}") as channel:
                        stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                        response = stub.NewTransactionBroadcast(broadcast_msg)
                        if response.success:
                            successful_broadcasts += 1
                            logging.debug(f"Successfully broadcast transaction to {peer}")
                except grpc.RpcError as e:
                    logging.error(f"Failed to broadcast transaction to {peer}: {e}")
        
        logging.info(f"Transaction broadcast complete: {successful_broadcasts}/{len(peers_to_broadcast)} successful")
    
    def broadcast_block(self, block: Block, exclude_peer: str = None):
        """Broadcast block to all known peers."""
        # Prepare the broadcast message
        serialized_data = pickle.dumps(block)
        broadcast_msg = blockchain_pb2.NewBlock(
            serialized_data=serialized_data,
            block_hash=block.blockhash
        )
        
        # Make a copy of handshaked peers to avoid concurrent modification
        with self.handshake_lock:
            peers_to_broadcast = list(self.handshaked_peers)
        
        logging.info(f"Broadcasting block {block.blockhash[:8]} to {len(peers_to_broadcast)} peers")
        logging.info(f"Block height: {self.blockchain.current_height}")
        logging.info(f"Block contains {len(block.transactions)} transactions")
        successful_broadcasts = 0
        
        # Broadcast to all handshaked peers except the excluded one
        for peer in peers_to_broadcast:
            if peer != exclude_peer:
                try:
                    with grpc.insecure_channel(f"{peer}:{self.node_port}") as channel:
                        stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                        response = stub.NewBlockBroadcast(broadcast_msg)
                        if response.success:
                            successful_broadcasts += 1
                            logging.debug(f"Successfully broadcast block to {peer}")
                except grpc.RpcError as e:
                    logging.error(f"Failed to broadcast block to {peer}: {e}")
        
        logging.info(f"Block broadcast complete: {successful_broadcasts}/{len(peers_to_broadcast)} successful")
    
    def calculate_chain_work(self, block_hash: str) -> int:
        """Calculate the total work in a chain (number of zeros in block hashes)."""
        if block_hash not in self.chain_work:
            block = self.blockchain.get_block_by_hash(block_hash)
            if not block:
                return 0
            parent_work = self.calculate_chain_work(block.block_header.hash_prev_block)
            # Count leading zeros in block hash
            work = len(block.blockhash) - len(block.blockhash.lstrip('0'))
            self.chain_work[block_hash] = parent_work + work
        return self.chain_work[block_hash]
    
    def handle_fork(self, new_block: Block) -> bool:
        """Handle potential blockchain fork."""
        current_tip = self.blockchain.height_map[self.blockchain.current_height]
        
        # If new block builds on current tip, no fork
        if new_block.block_header.hash_prev_block == current_tip:
            return True
        
        logging.info(f"Potential fork detected at height {self.blockchain.current_height}")
        
        # Calculate work for both chains
        new_chain_work = self.calculate_chain_work(new_block.blockhash)
        current_chain_work = self.calculate_chain_work(current_tip)
        
        logging.info(f"New chain work: {new_chain_work}, Current chain work: {current_chain_work}")
        
        # If new chain has more work, reorganize
        if new_chain_work > current_chain_work:
            logging.info("Fork resolution: Switching to new chain with more work")
            self.reorganize_chain(new_block)
            return True
        
        logging.info("Fork resolution: Keeping current chain")
        return False
    
    def reorganize_chain(self, new_tip: Block) -> None:
        """Reorganize the blockchain to follow the new chain."""
        # Find common ancestor
        current_tip = self.blockchain.height_map[self.blockchain.current_height]
        new_blocks = []
        old_blocks = []
        
        # Collect blocks in new chain
        block = new_tip
        while block and block.blockhash != current_tip:
            new_blocks.insert(0, block)
            block = self.blockchain.get_block_by_hash(block.block_header.hash_prev_block)
        
        # Collect blocks in old chain
        block = self.blockchain.get_block_by_hash(current_tip)
        while block and block.blockhash != new_blocks[0].block_header.hash_prev_block:
            old_blocks.append(block)
            block = self.blockchain.get_block_by_hash(block.block_header.hash_prev_block)
        
        logging.info(f"Chain reorganization: Removing {len(old_blocks)} blocks, adding {len(new_blocks)} blocks")
        
        # Remove old blocks
        for block in old_blocks:
            # Return transactions to mempool
            for tx in block.transactions:
                if not tx.is_coinbase:
                    self.mempool.add_transaction(tx)
        
        # Add new blocks
        for block in new_blocks:
            self.blockchain.add_block(block.transactions)
    
    def mine_blocks(self):
        """Mining loop that runs in a separate thread."""
        logging.info("Starting mining thread")  # Changed to INFO
        while not self.mining_event.is_set():
            # Generate a new transaction every 2-5 seconds
            if random.random() < 0.2:  # 20% chance each second
                tx = self.generate_random_transaction()
                self.mempool.add_transaction(tx)
                self.seen_transactions.add(tx.transaction_hash)
                self.broadcast_transaction(tx)
                self.new_transaction_event.set()  # Signal new transaction
            
            # Get transactions for mining
            if not self.mining_block or self.new_transaction_event.is_set():
                transactions = self.mempool.get_transactions(10)
                if transactions:
                    prev_block_hash = self.blockchain.height_map[self.blockchain.current_height]
                    self.mining_block = Block(prev_block_hash)
                    self.mining_block.block_header.bits = TARGET_BITS
                    self.mining_block.block_header.increment_nonce()
                    self.mining_transactions = set()
                    
                    # Create coinbase transaction
                    coinbase_tx = Transaction.create_coinbase(
                        value=50_000,  # 50 Barbaracoins
                        recipient_script=self.current_wallet.get_address() if hasattr(self, 'current_wallet') else Wallet().get_address()
                    )
                    self.mining_block.add_transaction(coinbase_tx)
                    
                    # Add other transactions to block
                    for tx in transactions:
                        self.mining_block.add_transaction(tx)
                        self.mining_transactions.add(tx.transaction_hash)
                    
                    self.new_transaction_event.clear()
                    logging.debug(f"Mining new block at height {self.blockchain.current_height + 1}")  # Changed to DEBUG
            
            # Try to mine the block
            if self.mining_block:
                if int(self.mining_block.blockhash, 16) < HEX_TARGET:
                    logging.info(f"Successfully mined block at height {self.blockchain.current_height + 1}")  # Changed to INFO
                    
                    if self.handle_fork(self.mining_block):
                        self.blockchain.add_block(self.mining_block.transactions)
                        self.seen_blocks.add(self.mining_block.blockhash)
                        self.broadcast_block(self.mining_block)
                        logging.info("Block added to blockchain and broadcast to peers")  # Changed to INFO
                    
                    self.mining_block = None
                    self.mining_transactions.clear()
                    time.sleep(random.randint(0, 3))
                else:
                    self.mining_block.block_header.increment_nonce()
                    self.mining_block._update_block()
            
            time.sleep(0.1)  # Small delay to prevent CPU overuse
    
    def add_peer(self, peer_addr: str, handshaked: bool = False) -> None:
        """Add a peer to our known peers list."""
        if peer_addr != self.addr_me:  # Don't add ourselves
            self.known_peers.add(peer_addr)
            if handshaked:
                with self.handshake_lock:
                    self.handshaked_peers.add(peer_addr)
    
    def should_handshake(self, peer_addr: str) -> bool:
        """Check if we should handshake with a peer."""
        with self.handshake_lock:
            return (peer_addr != self.addr_me and  # Not ourselves
                    peer_addr in self.known_peers and  # Known peer
                    peer_addr not in self.handshaked_peers)  # Not already handshaked
    
    def _get_my_ip(self) -> str:
        """Get the container's IP address."""
        # In Docker, we can get our IP this way
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    
    def register_with_dns_seed(self):
        """Register with DNS seed and get list of known peers."""
        try:
            channel = grpc.insecure_channel(self.dns_seed_addr)
            stub = blockchain_pb2_grpc.NodeRegistryStub(channel)
            
            # Create registration request
            request = blockchain_pb2.Registration(
                version=self.version,
                time=int(time.time()),
                addr_me=self.addr_me
            )
            
            # Send registration request
            response = stub.RegisterNode(request)
            
            # Process response
            if response.node_addresses:
                for node in response.node_addresses:
                    logging.debug(f"Discovered peer: {node}")
                    self.add_peer(node)
                return response.node_addresses
            else:
                logging.debug("No previous nodes registered")
                return []
                
        except grpc.RpcError as e:
            logging.debug(f"DNS seed connection: {e}")
            return []
    
    def handshake_with_node(self, node_addr: str):
        """Perform handshake with another node."""
        if not self.should_handshake(node_addr):
            logging.debug(f"Skipping handshake with {node_addr}: already handshaked or self")
            return False
            
        logging.info(f"\nInitiating handshake with node at {node_addr}")
        
        # Create handshake request
        handshake = blockchain_pb2.HandshakeRequest(
            version=self.version,
            time=int(time.time()),
            addr_me=self.addr_me,
            best_height=self.blockchain.current_height
        )
        
        try:
            # Create gRPC channel
            with grpc.insecure_channel(f"{node_addr}:{self.node_port}") as channel:
                stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                
                logging.info(f"Sending handshake to {node_addr}")
                logging.info(f"  Version: {self.version}")
                logging.info(f"  Best Height: {self.blockchain.current_height}")
                
                # Send handshake
                response = stub.Handshake(handshake)
                
                # Process registry data if available
                if hasattr(response, 'registry_data') and response.registry_data:
                    try:
                        registry_data = json.loads(response.registry_data.decode())
                        # Sync candidates
                        for candidate in registry_data.get('candidates', []):
                            if candidate not in self.voter_registry.valid_candidates:
                                self.voter_registry.add_candidate(candidate)
                                logging.info(f"Synchronized candidate from peer: {candidate}")
                        
                        # Sync voters
                        for voter in registry_data.get('voters', []):
                            if voter not in self.voter_registry.registered_voters:
                                self.voter_registry.register_voter(voter)
                                logging.info(f"Synchronized voter from peer: {voter}")
                        
                        # Sync voting status
                        if registry_data.get('voting_open', False) and not self.voter_registry.voting_open:
                            self.voter_registry.start_voting()
                            logging.info("Synchronized voting status: voting is open")
                    except json.JSONDecodeError:
                        logging.error("Failed to decode registry data from peer")
                    except Exception as e:
                        logging.error(f"Error processing registry data: {e}")
                
                # Mark this node as handshaked
                with self.handshake_lock:
                    self.handshaked_peers.add(node_addr)
                    logging.info(f"Successfully handshaked with {node_addr}")
                    logging.info(f"Total handshaked peers: {len(self.handshaked_peers)}")
                
                # Process response and discover new peers
                new_peers = set()
                for peer_addr in response.node_addresses:
                    if peer_addr not in self.known_peers:
                        logging.info(f"Discovered new peer: {peer_addr}")
                    self.add_peer(peer_addr)
                    if self.should_handshake(peer_addr):
                        new_peers.add(peer_addr)
                
                logging.info(f"Known peers after handshake: {len(self.known_peers)}")
                logging.info(f"New peers to handshake with: {len(new_peers)}")
                
                # Handshake with any newly discovered peers
                for peer_addr in new_peers:
                    # Start a new thread for each handshake to avoid blocking
                    threading.Thread(
                        target=self.handshake_with_node,
                        args=(peer_addr,),
                        daemon=True
                    ).start()
                
                return True
                
        except grpc.RpcError as e:
            logging.error(f"Failed to handshake with node {node_addr}: {e}")
            return False
    
    def start(self):
        """Start the full node."""
        logging.info(f"Starting full node on port {self.node_port}")
        logging.info(f"My IP address: {self.addr_me}")
        
        # Start the gRPC server
        self.server.add_insecure_port(f'[::]:{self.node_port}')
        self.server.start()
        
        # First register with DNS seed
        print(f"Connecting to DNS seed at {self.dns_seed_addr}")
        initial_peers = self.register_with_dns_seed()
        
        # Try to connect to all known peers
        if initial_peers:
            for peer in initial_peers:
                if peer != self.addr_me:  # Don't connect to self
                    self.handshake_with_node(peer)
                    time.sleep(1)  # Add small delay between handshakes
        
        logging.info("Node initialization complete")
        logging.info(f"Known peers: {self.known_peers}")
        logging.info(f"Handshaked peers: {self.handshaked_peers}")
        
        # Start a background thread for peer discovery and maintenance
        def maintain_connections():
            while True:
                try:
                    # Try to discover and connect to new peers
                    new_peers = self.register_with_dns_seed()
                    if new_peers:
                        for peer in new_peers:
                            if peer not in self.handshaked_peers and peer != self.addr_me:
                                self.handshake_with_node(peer)
                                time.sleep(1)
                    time.sleep(60)  # Check for new peers every 60 seconds
                except Exception as e:
                    logging.debug(f"Connection maintenance: {e}")
                    time.sleep(5)
        
        threading.Thread(target=maintain_connections, daemon=True).start()
        
        # Start a background thread for keeping the server alive
        def keep_alive():
            try:
                while True:
                    time.sleep(3600)  # Sleep for 1 hour
            except KeyboardInterrupt:
                self.server.stop(0)
        
        threading.Thread(target=keep_alive, daemon=True).start()
    
    def start_mining(self, block_interval=60):
        """Start mining blocks with the specified interval."""
        if self.mining_thread and self.mining_thread.is_alive():
            logging.info("Mining already in progress")
            return

        logging.info("Starting mining thread")
        self.mining_thread = threading.Thread(target=self._mine_blocks, args=(block_interval,))
        self.mining_thread.daemon = True
        self.mining_thread.start()
        logging.info("Mining thread started")

    def _mine_blocks(self, block_interval):
        """Mine new blocks at specified intervals."""
        while True:
            # Only mine if there are pending transactions or if the interval has passed
            if self.mempool.has_pending_transactions() or self.last_block_time + block_interval <= time.time():
                block = self._create_new_block()
                if block:
                    self._add_block(block)
                    self.last_block_time = time.time()
                    
            # Sleep for a short time to prevent CPU overuse
            time.sleep(1)

    def _create_new_block(self):
        """Create a new block with transactions from the mempool."""
        transactions = self.mempool.get_transactions(10)
        if not transactions:
            return None
        
        prev_block_hash = self.blockchain.height_map[self.blockchain.current_height]
        block = Block(prev_block_hash)
        block.block_header.bits = TARGET_BITS
        
        # Create coinbase transaction
        coinbase_tx = Transaction.create_coinbase(
            value=50_000,  # 50 Barbaracoins
            recipient_script=self.current_wallet.get_address() if hasattr(self, 'current_wallet') else Wallet().get_address()
        )
        block.add_transaction(coinbase_tx)
        
        # Add other transactions to block
        for tx in transactions:
            block.add_transaction(tx)
        
        return block

    def _add_block(self, block: Block):
        """Add a mined block to the blockchain."""
        self.blockchain.add_block(block.transactions)
        self.seen_blocks.add(block.blockhash)
        self.broadcast_block(block)
        logging.info("Block added to blockchain and broadcast to peers")

    def broadcast_candidate_addition(self, candidate):
        """Broadcast a new candidate to all peers."""
        # 只有当候选人确实存在时才广播
        if candidate in self.voter_registry.valid_candidates:
            message = {
                'type': 'candidate_addition',
                'candidate': candidate,
                'timestamp': int(time.time())
            }
            self.broadcast_to_peers(json.dumps(message))
            logging.info(f"Broadcasted candidate addition: {candidate}")
        else:
            logging.debug(f"Skipped broadcasting non-existent candidate: {candidate}")

    def handle_candidate_addition(self, message_data):
        """Handle received candidate addition message."""
        try:
            message = json.loads(message_data)
            candidate = message['candidate']
            # 只有当候选人不存在时才添加并广播
            if candidate not in self.voter_registry.valid_candidates:
                if self.voter_registry.add_candidate(candidate):
                    logging.info(f"Added candidate from peer: {candidate}")
                    # 只有在成功添加候选人后才广播
                    self.broadcast_candidate_addition(candidate)
            else:
                logging.debug(f"Ignored duplicate candidate: {candidate}")
        except Exception as e:
            logging.error(f"Error handling candidate addition: {e}")

    def broadcast_voter_registration(self, voter_id):
        """Broadcast a new voter registration to all peers."""
        # 只有当选民确实已注册时才广播
        if voter_id in self.voter_registry.registered_voters:
            message = {
                'type': 'voter_registration',
                'voter_id': voter_id,
                'timestamp': int(time.time())
            }
            self.broadcast_to_peers(json.dumps(message))
            logging.info(f"Broadcasted voter registration: {voter_id}")
        else:
            logging.debug(f"Skipped broadcasting non-registered voter: {voter_id}")

    def handle_voter_registration(self, message_data):
        """Handle received voter registration message."""
        try:
            message = json.loads(message_data)
            voter_id = message['voter_id']
            # 只有当选民不存在时才注册并广播
            if voter_id not in self.voter_registry.registered_voters:
                if self.voter_registry.register_voter(voter_id):
                    logging.info(f"Registered voter from peer: {voter_id}")
                    # 只有在成功注册选民后才广播
                    self.broadcast_voter_registration(voter_id)
            else:
                logging.debug(f"Ignored duplicate voter registration: {voter_id}")
        except Exception as e:
            logging.error(f"Error handling voter registration: {e}")

    def broadcast_to_peers(self, message):
        """Broadcast a message to all connected peers."""
        for peer in self.handshaked_peers:
            try:
                channel = grpc.insecure_channel(f"{peer}:{self.node_port}")
                stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                request = blockchain_pb2.NewTransaction(
                    serialized_data=message.encode(),
                    transaction_hash="message"
                )
                response = stub.NewTransactionBroadcast(request)
                if not response.success:
                    logging.warning(f"Failed to broadcast to {peer}: {response.message}")
            except Exception as e:
                logging.error(f"Error broadcasting to {peer}: {e}")
                continue

def main():
    # DNS seed address should be provided by Docker's DNS resolution
    node = FullNode("DNS_SEED")
    node.start()

if __name__ == "__main__":
    main() 