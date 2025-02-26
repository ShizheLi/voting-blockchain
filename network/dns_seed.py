import grpc
from concurrent import futures
import time
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import generated protobuf code
from proto.generated import blockchain_pb2
from proto.generated import blockchain_pb2_grpc

class NodeRegistry(blockchain_pb2_grpc.NodeRegistryServicer):
    def __init__(self):
        self.registered_nodes = []  # List of registered node IP addresses
        logging.info("DNS seed node initialized")
    
    def RegisterNode(self, request, context):
        """Register a new node and return the latest registered node (if any)."""
        # Extract registration information
        version = request.version
        node_time = request.time
        node_addr = request.addr_me
        
        logging.info(f"Registering new node:")
        logging.info(f"  Version: {version}")
        logging.info(f"  Time: {time.ctime(node_time)}")
        logging.info(f"  Address: {node_addr}")
        
        # Add the new node to our list
        self.registered_nodes.append(node_addr)
        logging.info(f"Total registered nodes: {len(self.registered_nodes)}")
        
        # Return the previous node (if any) to the registering node
        previous_nodes = []
        if len(self.registered_nodes) > 1:
            # Return only the most recently registered node before this one
            previous_nodes = [self.registered_nodes[-2]]
            logging.info(f"Returning previous node: {previous_nodes[0]}")
        else:
            logging.info("No previous nodes to return")
        
        return blockchain_pb2.NodeList(node_addresses=previous_nodes)

def serve(port=58333):
    """Start the DNS seed server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    registry = NodeRegistry()
    blockchain_pb2_grpc.add_NodeRegistryServicer_to_server(
        registry, server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logging.info(f"DNS seed node started on port {port}")
    
    try:
        while True:
            time.sleep(86400)  # Sleep for 24 hours
    except KeyboardInterrupt:
        logging.info("DNS seed node shutting down")
        server.stop(0)

if __name__ == '__main__':
    serve() 