#!/usr/bin/env python3
"""
NEXUS Database Layer — Card lookup, fuzzy matching, and consensus gate.
Uses Levenshtein for fuzzy OCR correction and SymSpell for high-speed correction.
"""
import sqlite3
import Levenshtein


class NexusDatabase:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def get_card_metadata(self, name_candidate):
        """Pulls Ground Truth from the 370K bridge table."""
        query = "SELECT name, oracle_text, color_identity, set_code, collector_number FROM cards WHERE name = ? COLLATE NOCASE"
        self.cursor.execute(query, (name_candidate,))
        return self.cursor.fetchone()

    def fuzzy_match_name(self, ocr_text):
        """Final boss of OCR: Maps garbled text back to real card names."""
        query = "SELECT name FROM cards WHERE name LIKE ?"
        self.cursor.execute(query, (f"{ocr_text[0]}%",))
        potential_names = [r[0] for r in self.cursor.fetchall()]

        best_match = None
        highest_ratio = 0
        for name in potential_names:
            ratio = Levenshtein.ratio(ocr_text.lower(), name.lower())
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = name
        return best_match, highest_ratio


def evaluate_consensus(ocr_raw, faiss_candidate, color_signal, db):
    """
    The Signal Gate: Blocks 'Cities' and 'Skerries'.
    Returns: (Success: bool, Final_Confidence: float, Signals: list)
    """
    signals = []
    confidence = 0.0

    # 1. Resolve OCR via Fuzzy Match
    best_name, ocr_ratio = db.fuzzy_match_name(ocr_raw)

    # 2. Pull Ground Truth Metadata for the candidate
    metadata = db.get_card_metadata(best_name if best_name else faiss_candidate)

    if not metadata:
        return False, 0.0, ["DB_MISS"]

    # 3. SIGNAL 1: CONVERGENCE (OCR matches Art)
    if best_name and best_name.lower() == faiss_candidate.lower():
        confidence += 0.85
        signals.append("CONVERGENCE")

    # 4. SIGNAL 2: COLOR MATCH (HSV matches DB Identity)
    db_colors = metadata[2] or ""
    if any(c in color_signal for c in db_colors):
        confidence += 0.05
        signals.append("COLOR_VERIFIED")

    # 5. SIGNAL 3: ORACLE/COLLECTOR MATCH
    if metadata[4] and str(metadata[4]) in ocr_raw:
        confidence += 0.10
        signals.append("COLLECTOR_LOCK")

    # 6. CONSENSUS BONUS
    if len(signals) >= 2:
        confidence += 0.05

    success = confidence >= 0.92
    return success, min(confidence, 1.0), signals
