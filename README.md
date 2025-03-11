# Blockchain-Based Voting System

A decentralized blockchain implementation that supports secure voting features.

## Team Members

- Qi Yang
- Shizhe Li

## Overview

It is a blockchain-based voting system designed to address transparency, security, and trust issues in traditional voting systems. By recording votes as transactions on a blockchain, the system ensures vote immutability and traceability while maintaining voter privacy.

The project demonstrates how blockchain technology can be applied to decentralized voting in a single platform.

## Features

- **Voting System**:
  - Candidate registration
  - Voter registration and verification
  - Secure voting process
  - Real-time vote status tracking
  - Vote result verification
- **Decentralized Architecture**: Distributed P2P network for high availability
- **CLI Interface**: User-friendly command-line interface with detailed status information

## Installation and Setup

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (for multi-node setup)

### Local Setup

```
docker compose down  // Ensure all nodes are stopped
docker compose up -d  // Start all nodes
docker ps  // View container names, e.g., node-a, node-b, node-c
docker exec -it <container_name> python3 cli.py  // Enter the container

example:
docker exec -it voting-blockchain-node-1 python3 cli.py
docker exec -it voting-blockchain-node-2 python3 cli.py
docker exec -it voting-blockchain-node-3 python3 cli.py
```

### 1. Node Initialization

```
start
```

### 2. Add Candidate

```
addcandidate <candidate_name>

example:
addcandidate Alice
addcandidate Bob
```

### 3. Register Voter

```
registervoter <voter_id>

example:
registervoter voter1
registervoter voter2
registervoter voter3
```

### 4. Start Voting

```
startvoting  // Equivalent to startmining, broadcasts the vote as a transaction, other nodes mine this transaction
```

### 5. Voting

```
vote <voter_id> <candidate_name>

example:
vote voter1 Alice
vote voter2 Bob
vote voter3 Alice
```

### 6. View Voting Results

```
votestatus <voter_id>  // Check voter status
votestatus voter1
votestatus voter2
votestatus voter3
pendingvotes  // Check pending votes
pendingvotes
listvotes  // Check all votes
listvotes
listvotes
```

### 7. If Cleanup is Needed

```
# List all images
docker images

# List all containers
docker ps -a

# Remove unused images
docker image prune -a

# Remove unused containers
docker container prune

# Remove unused networks
docker network prune

# Remove unused volumes
docker volume prune
```

### 8. If Code Changes Are Needed

```
# 1. Completely stop and remove all containers and related resources
docker compose down --volumes --remove-orphans

# 2. Rebuild the images (force no cache)
docker compose build --no-cache

# 3. Start the services
docker compose up -d

# 4. Verify the changes
docker exec -it <container_name> python3 cli.py
```
