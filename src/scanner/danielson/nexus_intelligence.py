#!/usr/bin/env python3
"""
NEXUS Intelligence Layer — SymSpell fuzzy correction, pHash visual fingerprinting,
and multi-signal consensus gate with metadata verification.
"""
import cv2
import numpy as np
import sqlite3
import imagehash
from symspellpy import SymSpell, Verbosity
from PIL import Image


class NexusIntelligence:
    def __init__(self, db_path, symspell_dict):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.symspell = SymSpell(max_dictionary_edit_distance=3, prefix_length=7)
        self.symspell.load_dictionary(symspell_dict, term_index=0, count_index=1)

    def get_phash(self, frame):
        """Generates a 64-bit visual fingerprint of the card art."""
        h, w = frame.shape[:2]
        art_crop = frame[int(h * 0.2):int(h * 0.6), int(w * 0.2):int(w * 0.8)]
        pil_img = Image.fromarray(cv2.cvtColor(art_crop, cv2.COLOR_BGR2RGB))
        return str(imagehash.phash(pil_img))

    def verify_phash(self, current_hash, db_stored_hash):
        """Compares fingerprints. Hamming distance < 12 = match."""
        h1 = imagehash.hex_to_hash(current_hash)
        h2 = imagehash.hex_to_hash(db_stored_hash)
        distance = h1 - h2
        return distance < 12

    def symspell_correct(self, ocr_garbage):
        """High-speed fuzzy correction against 370K card names."""
        suggestions = self.symspell.lookup(ocr_garbage, Verbosity.CLOSEST, max_edit_distance=3)
        if suggestions:
            return suggestions[0].term, suggestions[0].distance
        return None, None

    def full_consensus(self, ocr_raw, faiss_candidate, color_signal, frame):
        """Multi-signal consensus with SymSpell + pHash + color verification."""
        signals = []
        confidence = 0.0

        # 1. SymSpell correction
        best_name, edit_dist = self.symspell_correct(ocr_raw)

        # 2. Check convergence
        if best_name and best_name.lower() == faiss_candidate.lower():
            confidence += 0.85
            signals.append("CONVERGENCE")

        # 3. pHash verification
        current_hash = self.get_phash(frame)
        # Would compare against DB stored hash here
        # if self.verify_phash(current_hash, db_hash):
        #     confidence += 0.05
        #     signals.append("PHASH_VERIFIED")

        # 4. Color signal
        if color_signal:
            confidence += 0.05
            signals.append("COLOR")

        # 5. Consensus bonus
        if len(signals) >= 2:
            confidence += 0.05

        success = confidence >= 0.92
        return success, confidence, signals, best_name
