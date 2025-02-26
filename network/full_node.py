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

from proto.generated import blockchain_pb2
from proto.generated import blockchain_pb2_grpc
from blockchain import Blockchain
from transaction import Transaction
from mempool import TxnMemoryPool
from block import Block

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Mining difficulty target
TARGET_BITS = 0x1e200000
HEX_TARGET = 0x0000200000000000000000000000000000000000000000000000000000000000

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
        
        logging.info(f"Received handshake from node {node_addr}")
        logging.info(f"  Version: {version}")
        logging.info(f"  Time: {time.ctime(node_time)}")
        logging.info(f"  Best Height: {best_height}")
        
        # Add the node to our known peers and mark as handshaked
        self.node.add_peer(node_addr, handshaked=True)
        
        # Start a background thread to handshake with the new node
        if self.node.should_handshake(node_addr):
            threading.Thread(
                target=self.node.handshake_with_node,
                args=(node_addr,),
                daemon=True
            ).start()
        
        return blockchain_pb2.NodeList(node_addresses=list(self.node.known_peers))
    
    def NewTransactionBroadcast(self, request, context):
        """Handle incoming transaction broadcast."""
        tx_hash = request.transaction_hash
        
        if tx_hash in self.node.seen_transactions:
            logging.debug(f"Ignoring already seen transaction: {tx_hash[:8]}...")
            return blockchain_pb2.BroadcastResponse(
                success=True,
                message="Transaction already known"
            )
        
        tx = pickle.loads(request.serialized_data)
        logging.info(f"Received new transaction: {tx_hash[:8]}...")
        
        self.node.mempool.add_transaction(tx)
        self.node.seen_transactions.add(tx_hash)
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
        
        # Create gRPC server
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        blockchain_pb2_grpc.add_FullNodeServiceServicer_to_server(
            FullNodeServicer(self), self.server
        )
        
        # Mining control
        self.mining_event = threading.Event()
        self.mining_thread = None
    
    def generate_random_transaction(self) -> Transaction:
        """Generate a random transaction for testing."""
        tx = Transaction()
        # Create a random input
        input_data = f"tx_{int(time.time())}_{random.randint(0, 1000000)}"
        tx.add_input(input_data)
        
        # Create 1-3 outputs with random values
        num_outputs = random.randint(1, 3)
        for i in range(num_outputs):
            value = random.randint(100, 10000)  # 0.1 to 10 Barbaracoins
            script = f"Address_{random.randint(1000, 9999)}"
            tx.add_output(value, script)
        
        return tx
    
    def broadcast_transaction(self, tx: Transaction, exclude_peer: str = None):
        """Broadcast transaction to all known peers."""
        # Prepare the broadcast message
        serialized_data = pickle.dumps(tx)
        broadcast_msg = blockchain_pb2.NewTransaction(
            serialized_data=serialized_data,
            transaction_hash=tx.transaction_hash
        )
        
        # Make a copy of handshaked peers to avoid concurrent modification
        with self.handshake_lock:
            peers_to_broadcast = list(self.handshaked_peers)
        
        # Broadcast to all handshaked peers except the excluded one
        for peer in peers_to_broadcast:
            if peer != exclude_peer:
                try:
                    with grpc.insecure_channel(f"{peer}:{self.node_port}") as channel:
                        stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                        stub.NewTransactionBroadcast(broadcast_msg)
                except grpc.RpcError as e:
                    logging.error(f"Failed to broadcast transaction to {peer}: {e}")
    
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
        
        # Broadcast to all handshaked peers except the excluded one
        for peer in peers_to_broadcast:
            if peer != exclude_peer:
                try:
                    with grpc.insecure_channel(f"{peer}:{self.node_port}") as channel:
                        stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                        stub.NewBlockBroadcast(broadcast_msg)
                except grpc.RpcError as e:
                    logging.error(f"Failed to broadcast block to {peer}: {e}")
    
    def mine_blocks(self):
        """Mining loop that runs in a separate thread."""
        logging.info("Starting mining thread")
        while not self.mining_event.is_set():
            # Generate a new transaction every 2-5 seconds
            if random.random() < 0.2:  # 20% chance each second
                tx = self.generate_random_transaction()
                logging.info(f"Generated new transaction: {tx.transaction_hash[:8]}...")
                self.mempool.add_transaction(tx)
                self.seen_transactions.add(tx.transaction_hash)
                self.broadcast_transaction(tx)
            
            # Try to mine a block
            transactions = self.mempool.get_transactions(10)  # Get up to 10 transactions
            if transactions:
                logging.info(f"Attempting to mine block with {len(transactions)} transactions")
                
                prev_block_hash = self.blockchain.height_map[self.blockchain.current_height]
                new_block = Block(prev_block_hash)
                new_block.block_header.bits = TARGET_BITS
                
                for tx in transactions:
                    new_block.add_transaction(tx)
                
                start_time = time.time()
                attempts = 0
                while not self.mining_event.is_set():
                    if int(new_block.blockhash, 16) < HEX_TARGET:
                        end_time = time.time()
                        logging.info(f"Successfully mined block at height {self.blockchain.current_height + 1}")
                        logging.info(f"Mining took {end_time - start_time:.2f} seconds and {attempts} attempts")
                        logging.info(f"Block hash: {new_block.blockhash}")
                        
                        self.blockchain.add_block(transactions)
                        self.seen_blocks.add(new_block.blockhash)
                        self.broadcast_block(new_block)
                        time.sleep(random.randint(0, 3))
                        break
                    
                    new_block.block_header.increment_nonce()
                    new_block._update_block()
                    attempts += 1
                    
                    if attempts % 1000 == 0:
                        logging.debug(f"Mining attempt {attempts}, current hash: {new_block.blockhash[:16]}...")
                
                time.sleep(1)  # Check every second
    
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
        """Register this node with the DNS seed and get the previous node."""
        print(f"Connecting to DNS seed at {self.dns_seed_addr}")
        
        # Create registration request
        registration = blockchain_pb2.Registration(
            version=self.version,
            time=int(time.time()),
            addr_me=self.addr_me
        )
        
        try:
            # Create gRPC channel
            with grpc.insecure_channel(self.dns_seed_addr) as channel:
                stub = blockchain_pb2_grpc.NodeRegistryStub(channel)
                
                # Send registration
                response = stub.RegisterNode(registration)
                
                # Process response
                if response.node_addresses:
                    previous_node = response.node_addresses[0]
                    print("Received previous node address:", previous_node)
                    self.add_peer(previous_node)
                    return previous_node
                else:
                    print("No previous nodes registered")
                    return None
                
        except grpc.RpcError as e:
            print(f"Failed to register with DNS seed: {e}")
            return None
    
    def handshake_with_node(self, node_addr: str):
        """Perform handshake with another node."""
        if not self.should_handshake(node_addr):
            return False
            
        print(f"\nInitiating handshake with node at {node_addr}")
        
        # Create handshake request
        handshake = blockchain_pb2.HandshakeRequest(
            version=self.version,
            time=int(time.time()),
            addr_me=self.addr_me,
            best_height=self.best_height
        )
        
        try:
            # Create gRPC channel
            with grpc.insecure_channel(f"{node_addr}:{self.node_port}") as channel:
                stub = blockchain_pb2_grpc.FullNodeServiceStub(channel)
                
                # Send handshake
                response = stub.Handshake(handshake)
                
                # Mark this node as handshaked
                with self.handshake_lock:
                    self.handshaked_peers.add(node_addr)
                
                # Process response and discover new peers
                new_peers = set()
                for peer_addr in response.node_addresses:
                    self.add_peer(peer_addr)
                    if self.should_handshake(peer_addr):
                        new_peers.add(peer_addr)
                
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
            print(f"Failed to handshake with node {node_addr}: {e}")
            return False
    
    def start(self):
        """Start the full node."""
        logging.info(f"Starting full node on port {self.node_port}")
        logging.info(f"My IP address: {self.addr_me}")
        
        # Start the gRPC server
        self.server.add_insecure_port(f'[::]:{self.node_port}')
        self.server.start()
        
        # First register with DNS seed
        initial_peer = self.register_with_dns_seed()
        
        # If we got an initial peer, start the handshake process
        if initial_peer:
            self.handshake_with_node(initial_peer)
        
        logging.info("Node initialization complete")
        logging.info(f"Known peers: {self.known_peers}")
        logging.info(f"Handshaked peers: {self.handshaked_peers}")
        
        # Start mining in a separate thread
        self.mining_thread = threading.Thread(target=self.mine_blocks, daemon=True)
        self.mining_thread.start()
        logging.info("Mining thread started")
        
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logging.info("Node shutting down")
            self.mining_event.set()
            self.server.stop(0)

def main():
    # DNS seed address should be provided by Docker's DNS resolution
    node = FullNode("DNS_SEED")
    node.start()

if __name__ == "__main__":
    main() 