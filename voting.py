from transaction import Transaction
from typing import Set, Dict, Optional, List
import logging
import time
import json
import hashlib
from utils import double_sha256, serialize_data

class VoteTransaction(Transaction):
    def __init__(self, voter_id=None, candidate=None):
        self.voter_id = voter_id
        self.candidate = candidate
        self.is_vote = True
        self.timestamp = int(time.time())
        self.confirmed = False
        self.inputs = []
        self.outputs = []
        super().__init__()

    def _calculate_hash(self):
        """Calculate hash of transaction including vote-specific fields"""
        data = {
            'version': self.version_number,
            'in_counter': self.in_counter,
            'inputs': self.list_of_inputs,
            'out_counter': self.out_counter,
            'outputs': [output.to_dict() for output in self.list_of_outputs],
            'timestamp': self.timestamp,
            'voter_id': self.voter_id,
            'candidate': self.candidate,
            'is_vote': self.is_vote
        }
        self.transaction_hash = double_sha256(serialize_data(data))

    def to_dict(self):
        """Convert transaction to dictionary for serialization"""
        data = super().to_dict()
        data.update({
            'voter_id': self.voter_id,
            'candidate': self.candidate,
            'is_vote': self.is_vote
        })
        return data

    @classmethod
    def from_dict(cls, data):
        """Create VoteTransaction from dictionary"""
        tx = cls(data.get('voter_id'), data.get('candidate'))
        tx.inputs = [TransactionInput.from_dict(input_data) for input_data in data.get('inputs', [])]
        tx.outputs = [TransactionOutput.from_dict(output_data) for output_data in data.get('outputs', [])]
        tx.timestamp = data.get('timestamp')
        tx.txid = data.get('txid')
        return tx

    def print_transaction(self) -> None:
        """Override to print vote-specific details."""
        super().print_transaction()
        print(f"Vote Details:")
        print(f"  Voter ID: {self.voter_id}")
        print(f"  Candidate: {self.candidate}")
        print(f"  Time: {time.ctime(self.timestamp)}")
        print(f"  Status: {'Confirmed' if self.confirmed else 'Pending'}")

class VoterRegistry:
    def __init__(self):
        self.registered_voters: Set[str] = set()
        self.valid_candidates: Set[str] = set()
        self.voting_open: bool = False
        self.vote_counts: Dict[str, int] = {}
        self.pending_votes: Dict[str, VoteTransaction] = {}  # voter_id -> transaction
        self.confirmed_votes: Dict[str, VoteTransaction] = {}  # voter_id -> transaction

    def start_voting(self) -> None:
        """Open the voting period."""
        self.voting_open = True
        self.vote_counts = {candidate: 0 for candidate in self.valid_candidates}
        self.pending_votes.clear()
        self.confirmed_votes.clear()
        logging.info("Voting period has started")

    def end_voting(self) -> None:
        """Close the voting period."""
        self.voting_open = False
        logging.info("Voting period has ended")

    def register_voter(self, voter_id: str) -> bool:
        """Register a new voter."""
        if voter_id in self.registered_voters:
            logging.debug(f"Voter {voter_id} is already registered")
            return False
        self.registered_voters.add(voter_id)
        logging.info(f"Voter {voter_id} has been registered")
        return True

    def add_candidate(self, candidate: str) -> bool:
        """Add a new candidate to the election."""
        if candidate in self.valid_candidates:
            logging.debug(f"Candidate {candidate} is already registered")
            return False
        self.valid_candidates.add(candidate)
        logging.info(f"Candidate {candidate} has been added to the election")
        return True

    def is_registered(self, voter_id: str) -> bool:
        """Check if a voter is registered."""
        return voter_id in self.registered_voters

    def is_valid_candidate(self, candidate: str) -> bool:
        """Check if a candidate is valid."""
        return candidate in self.valid_candidates

    def is_voting_open(self) -> bool:
        """Check if voting period is open."""
        return self.voting_open

    def has_voted(self, voter_id: str) -> bool:
        """Check if a voter has already voted."""
        return voter_id in self.confirmed_votes or voter_id in self.pending_votes

    def add_pending_vote(self, vote_tx: VoteTransaction) -> None:
        """Add a vote to pending votes."""
        self.pending_votes[vote_tx.voter_id] = vote_tx

    def confirm_vote(self, vote_tx: VoteTransaction) -> None:
        """Move a vote from pending to confirmed and update counts."""
        if vote_tx.voter_id in self.pending_votes:
            del self.pending_votes[vote_tx.voter_id]
        self.confirmed_votes[vote_tx.voter_id] = vote_tx
        self.vote_counts[vote_tx.candidate] = self.vote_counts.get(vote_tx.candidate, 0) + 1
        vote_tx.confirmed = True

    def get_results(self) -> Dict[str, int]:
        """Get the current voting results."""
        return self.vote_counts.copy()

    def get_vote_status(self, voter_id: str) -> Optional[Dict]:
        """Get the status of a voter's vote."""
        if voter_id in self.confirmed_votes:
            vote = self.confirmed_votes[voter_id]
            return {
                "status": "Confirmed",
                "candidate": vote.candidate,
                "time": vote.timestamp
            }
        elif voter_id in self.pending_votes:
            vote = self.pending_votes[voter_id]
            return {
                "status": "Pending",
                "candidate": vote.candidate,
                "time": vote.timestamp
            }
        return None 