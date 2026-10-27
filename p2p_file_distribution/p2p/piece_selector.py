"""
p2p/piece_selector.py
Implements piece selection algorithms: Rarest-First, Sequential, and Random.
Part of the P2P File Distribution System (Member 2 deliverable).
"""

import random
from typing import List, Dict, Set, Optional


class PieceSelector:
    """Calculates optimal piece download order based on swarm bitfields."""

    def __init__(self, total_pieces: int, strategy: str = "rarest_first"):
        self.total_pieces = total_pieces
        self.strategy = strategy

    def select_next_piece(
        self,
        needed_pieces: Set[int],
        peer_bitfields: Dict[str, List[int]],
        in_flight_pieces: Set[int]
    ) -> Optional[int]:
        """
        Selects the next piece to request from available candidates.
        Excludes pieces currently in-flight (being actively downloaded by another thread).
        """
        candidates = list(needed_pieces - in_flight_pieces)
        if not candidates:
            return None

        if self.strategy == "sequential":
            return min(candidates)

        if self.strategy == "random":
            return random.choice(candidates)

        if self.strategy == "rarest_first":
            # Calculate frequency of each candidate across known peer bitfields
            freq_map: Dict[int, int] = {p: 0 for p in candidates}
            for pid, bitfield in peer_bitfields.items():
                for piece_idx in candidates:
                    if piece_idx < len(bitfield) and bitfield[piece_idx] == 1:
                        freq_map[piece_idx] += 1

            # Only consider pieces that at least one peer possesses
            available_candidates = [p for p in candidates if freq_map[p] > 0]
            if not available_candidates:
                return candidates[0]

            # Find pieces with minimum frequency (rarest)
            min_freq = min(freq_map[p] for p in available_candidates)
            rarest_candidates = [p for p in available_candidates if freq_map[p] == min_freq]
            return random.choice(rarest_candidates)

        return candidates[0]
