#!/usr/bin/env python3
"""Validate a trained Tesseract model against ground truth + fuzzy DB lookup.

Runs OCR on test images, compares against ground truth, then applies
Levenshtein fuzzy matching against the MTG card name database to measure
the real-world correction pipeline.

Reports:
  - Raw OCR accuracy (exact match)
  - Character-level accuracy (Levenshtein distance)
  - Post-fuzzy accuracy (after DB lookup correction)
  - Common error patterns (substitutions, insertions, deletions)

Usage:
    python validate_ocr_model.py
    python validate_ocr_model.py --model nexus_mtg --samples 500
    python validate_ocr_model.py --checkpoint E:/path/to/best.checkpoint
"""

import argparse
import glob
import os
import random
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
LSTMTRAINING_EXE = r"C:\Program Files\Tesseract-OCR\lstmtraining.exe"
TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"
DB_PATH = r"E:\NEXUS_V2_RECREATED\data\nexus_cards.db"
TRAINING_DIR = r"E:\NEXUS_V2_RECREATED\training"

# ─── Levenshtein distance (stdlib, no deps) ────────────────────────────────

def levenshtein(s1: str, s2: str) -> int:
    """Standard Levenshtein edit distance."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s2:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,      # deletion
                curr[j] + 1,           # insertion
                prev[j] + (c1 != c2)   # substitution
            ))
        prev = curr
    return prev[-1]


def char_accuracy(ocr: str, gt: str) -> float:
    """Character-level accuracy: 1 - (edit_distance / max_len)."""
    if not gt:
        return 1.0 if not ocr else 0.0
    dist = levenshtein(ocr, gt)
    return max(0.0, 1.0 - dist / max(len(gt), len(ocr)))


def get_edit_ops(ocr: str, gt: str) -> list:
    """Extract character-level edit operations (substitutions, etc.)."""
    ops = []
    sm = SequenceMatcher(None, gt, ocr)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            ops.append(('sub', gt[i1:i2], ocr[j1:j2]))
        elif tag == 'delete':
            ops.append(('del', gt[i1:i2], ''))
        elif tag == 'insert':
            ops.append(('ins', '', ocr[j1:j2]))
    return ops


# ─── Card Name Database ────────────────────────────────────────────────────

class CardNameDB:
    """Fuzzy lookup against the MTG card name database."""

    def __init__(self, db_path: str):
        self.names = set()
        self.names_lower = {}  # lower -> original
        self._load(db_path)
        print(f"[DB] Loaded {len(self.names)} unique MTG card names")

    def _load(self, db_path: str):
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT DISTINCT name FROM cards WHERE tcg='mtg' AND name IS NOT NULL"
        )
        for (name,) in cursor:
            name = name.strip()
            if name:
                self.names.add(name)
                self.names_lower[name.lower()] = name
        conn.close()

    def exact_match(self, text: str) -> str | None:
        """Case-insensitive exact match."""
        return self.names_lower.get(text.lower().strip())

    def fuzzy_match(self, text: str, max_distance: int = 3) -> tuple:
        """Find closest card name by Levenshtein distance.

        Returns (best_match, distance) or (None, inf) if no match within threshold.
        """
        text_lower = text.lower().strip()
        if not text_lower:
            return None, float('inf')

        # Exact match first
        exact = self.names_lower.get(text_lower)
        if exact:
            return exact, 0

        # Fuzzy search — only check names within ±3 chars of target length
        best_name = None
        best_dist = max_distance + 1
        target_len = len(text_lower)

        for name_lower, name_orig in self.names_lower.items():
            if abs(len(name_lower) - target_len) > max_distance:
                continue
            dist = levenshtein(text_lower, name_lower)
            if dist < best_dist:
                best_dist = dist
                best_name = name_orig
                if dist == 1:
                    break  # Good enough — single char error

        if best_dist <= max_distance:
            return best_name, best_dist
        return None, float('inf')


# ─── OCR Runner ─────────────────────────────────────────────────────────────

def run_ocr(tif_path: str, model: str = 'eng', tessdata: str = None) -> str:
    """Run Tesseract OCR on a single image, return raw output text."""
    cmd = [TESSERACT_EXE, tif_path, 'stdout', '-l', model, '--psm', '7']
    env = dict(os.environ)
    if tessdata:
        env['TESSDATA_PREFIX'] = tessdata

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, env=env
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ''


def package_checkpoint(checkpoint_path: str, model_name: str) -> str:
    """Package a checkpoint into a .traineddata file for testing."""
    eng_best = os.path.join(TRAINING_DIR, 'eng_best.traineddata')
    output = os.path.join(TRAINING_DIR, 'tesseract_training',
                          f'{model_name}.traineddata')

    cmd = [
        LSTMTRAINING_EXE,
        '--stop_training',
        '--traineddata', eng_best,
        '--continue_from', checkpoint_path,
        '--model_output', output,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.isfile(output):
        return output
    print(f"[ERROR] Failed to package checkpoint: {result.stderr}")
    return ''


# ─── Validation ─────────────────────────────────────────────────────────────

def validate(data_dir: str, model: str, tessdata: str, db: CardNameDB,
             n_samples: int, hard_only: bool = False):
    """Run validation on ground truth samples."""

    # Gather all .tif + .gt.txt pairs
    tif_files = sorted(glob.glob(os.path.join(data_dir, '*.tif')))
    pairs = []
    for tif in tif_files:
        gt_path = tif.rsplit('.tif', 1)[0] + '.gt.txt'
        if os.path.isfile(gt_path):
            with open(gt_path, 'r', encoding='utf-8') as f:
                gt = f.read().strip()
            if gt:
                pairs.append((tif, gt))

    if not pairs:
        print(f"[ERROR] No .tif + .gt.txt pairs in {data_dir}")
        return

    # Optional: filter to only "hard" names (apostrophes, diacritics, etc.)
    if hard_only:
        hard_chars = set("''-éèêëàâäùûüïîôöçñæœ")
        pairs = [(t, g) for t, g in pairs if any(c in hard_chars for c in g)]
        print(f"[FILTER] {len(pairs)} hard-mode samples (special characters)")

    # Sample
    if n_samples > 0 and n_samples < len(pairs):
        pairs = random.sample(pairs, n_samples)

    print(f"\n[VALIDATE] Testing {len(pairs)} samples with model '{model}'")
    print(f"{'='*70}")

    # Stats
    exact_matches = 0
    fuzzy_matches = 0
    fuzzy_corrected = 0
    total_char_acc = 0.0
    total_char_acc_fuzzy = 0.0
    error_ops = Counter()  # (op_type, gt_char, ocr_char) -> count
    worst_cases = []  # (distance, gt, ocr, fuzzy)
    confusion = Counter()  # (gt_char, ocr_char) -> count

    t0 = time.time()
    for i, (tif_path, gt_text) in enumerate(pairs):
        ocr_text = run_ocr(tif_path, model, tessdata)

        # Raw comparison
        is_exact = (ocr_text == gt_text)
        if is_exact:
            exact_matches += 1

        c_acc = char_accuracy(ocr_text, gt_text)
        total_char_acc += c_acc

        # Fuzzy lookup
        fuzzy_name, fuzzy_dist = db.fuzzy_match(ocr_text)
        if fuzzy_name and fuzzy_name == gt_text:
            fuzzy_matches += 1
            if not is_exact:
                fuzzy_corrected += 1
        elif is_exact:
            fuzzy_matches += 1  # exact match counts as fuzzy success too

        # Char accuracy after fuzzy
        if fuzzy_name:
            total_char_acc_fuzzy += char_accuracy(fuzzy_name, gt_text)
        else:
            total_char_acc_fuzzy += c_acc

        # Error analysis
        if not is_exact:
            ops = get_edit_ops(ocr_text, gt_text)
            for op_type, gt_chars, ocr_chars in ops:
                error_ops[(op_type, gt_chars, ocr_chars)] += 1
                if op_type == 'sub':
                    for gc, oc in zip(gt_chars, ocr_chars):
                        confusion[(gc, oc)] += 1

            dist = levenshtein(ocr_text, gt_text)
            worst_cases.append((dist, gt_text, ocr_text, fuzzy_name))

        # Progress
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(f"  [{i+1}/{len(pairs)}] "
                  f"exact={exact_matches}/{i+1} "
                  f"({100*exact_matches/(i+1):.1f}%) "
                  f"fuzzy={fuzzy_matches}/{i+1} "
                  f"({100*fuzzy_matches/(i+1):.1f}%) "
                  f"[{rate:.0f}/s]")

    elapsed = time.time() - t0
    n = len(pairs)

    # ── Results ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f" VALIDATION RESULTS — model: {model}")
    print(f"{'='*70}")
    print(f" Samples:              {n}")
    print(f" Time:                 {elapsed:.1f}s ({n/elapsed:.0f}/s)")
    print(f"")
    print(f" Raw exact match:      {exact_matches}/{n} ({100*exact_matches/n:.1f}%)")
    print(f" Raw char accuracy:    {100*total_char_acc/n:.2f}%")
    print(f"")
    print(f" Post-fuzzy match:     {fuzzy_matches}/{n} ({100*fuzzy_matches/n:.1f}%)")
    print(f" Fuzzy corrections:    {fuzzy_corrected}")
    print(f" Post-fuzzy char acc:  {100*total_char_acc_fuzzy/n:.2f}%")
    print(f"{'='*70}")

    # ── Top error patterns ───────────────────────────────────────────────
    print(f"\n Top character confusions:")
    for (gc, oc), count in confusion.most_common(15):
        gc_repr = repr(gc) if not gc.isalnum() else gc
        oc_repr = repr(oc) if not oc.isalnum() else oc
        print(f"   {gc_repr} -> {oc_repr}  ({count}x)")

    # ── Top error operations ─────────────────────────────────────────────
    print(f"\n Top edit operations:")
    for (op, gt_c, ocr_c), count in error_ops.most_common(15):
        gt_repr = repr(gt_c) if gt_c else '""'
        ocr_repr = repr(ocr_c) if ocr_c else '""'
        print(f"   {op}: {gt_repr} -> {ocr_repr}  ({count}x)")

    # ── Worst cases ──────────────────────────────────────────────────────
    worst_cases.sort(reverse=True)
    print(f"\n Worst OCR errors (by edit distance):")
    for dist, gt, ocr, fuzzy in worst_cases[:20]:
        fuzzy_mark = f" -> [{fuzzy}]" if fuzzy and fuzzy == gt else ""
        fuzzy_fail = f" -> [{fuzzy}] WRONG" if fuzzy and fuzzy != gt else ""
        print(f"   d={dist}: GT='{gt}' OCR='{ocr}'{fuzzy_mark}{fuzzy_fail}")

    # ── Save report ──────────────────────────────────────────────────────
    report_path = os.path.join(TRAINING_DIR, 'tesseract_training',
                               f'validation_{model}.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Model: {model}\n")
        f.write(f"Samples: {n}\n")
        f.write(f"Raw exact: {exact_matches}/{n} ({100*exact_matches/n:.1f}%)\n")
        f.write(f"Raw char acc: {100*total_char_acc/n:.2f}%\n")
        f.write(f"Fuzzy match: {fuzzy_matches}/{n} ({100*fuzzy_matches/n:.1f}%)\n")
        f.write(f"Fuzzy corrections: {fuzzy_corrected}\n")
        f.write(f"\nTop confusions:\n")
        for (gc, oc), count in confusion.most_common(30):
            f.write(f"  {repr(gc)} -> {repr(oc)}  ({count}x)\n")
        f.write(f"\nWorst cases:\n")
        for dist, gt, ocr, fuzzy in worst_cases[:50]:
            f.write(f"  d={dist}: GT='{gt}' OCR='{ocr}' fuzzy='{fuzzy}'\n")

    print(f"\n Report saved: {report_path}")

    return {
        'exact_pct': 100 * exact_matches / n,
        'char_acc': 100 * total_char_acc / n,
        'fuzzy_pct': 100 * fuzzy_matches / n,
    }


# ─── Compare models ─────────────────────────────────────────────────────────

def compare_models(data_dir: str, db: CardNameDB, n_samples: int):
    """Compare eng_best vs nexus_mtg on the same sample set."""
    tif_files = sorted(glob.glob(os.path.join(data_dir, '*.tif')))
    pairs = []
    for tif in tif_files:
        gt_path = tif.rsplit('.tif', 1)[0] + '.gt.txt'
        if os.path.isfile(gt_path):
            with open(gt_path, 'r', encoding='utf-8') as f:
                gt = f.read().strip()
            if gt:
                pairs.append((tif, gt))

    if n_samples > 0 and n_samples < len(pairs):
        pairs = random.sample(pairs, n_samples)

    models = {
        'eng': TESSDATA_DIR,
        'nexus_mtg': TESSDATA_DIR,
    }

    # Check which models are available
    available = {}
    for model, td in models.items():
        path = os.path.join(td, f'{model}.traineddata')
        if os.path.isfile(path):
            available[model] = td
            print(f"[OK] {model}: {path}")
        else:
            print(f"[SKIP] {model}: not found at {path}")

    results = {}
    for model, td in available.items():
        print(f"\n{'─'*70}")
        print(f" Testing: {model}")
        print(f"{'─'*70}")
        results[model] = validate(data_dir, model, td, db, n_samples)

    if len(results) >= 2:
        print(f"\n{'='*70}")
        print(f" MODEL COMPARISON")
        print(f"{'='*70}")
        for model, r in results.items():
            print(f"  {model:15s}  exact={r['exact_pct']:.1f}%  "
                  f"char={r['char_acc']:.1f}%  "
                  f"fuzzy={r['fuzzy_pct']:.1f}%")
        print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate OCR model against ground truth + fuzzy DB lookup')
    parser.add_argument('--model', default='nexus_mtg',
                        help='Tesseract model name (default: nexus_mtg)')
    parser.add_argument('--tessdata', default=None,
                        help='TESSDATA_PREFIX override')
    parser.add_argument('--data', default=None,
                        help='Directory with .tif + .gt.txt pairs')
    parser.add_argument('--db', default=DB_PATH,
                        help='Card database path for fuzzy matching')
    parser.add_argument('--samples', type=int, default=500,
                        help='Number of samples to test (0=all)')
    parser.add_argument('--hard-only', action='store_true',
                        help='Only test names with special chars')
    parser.add_argument('--compare', action='store_true',
                        help='Compare eng vs nexus_mtg side-by-side')
    parser.add_argument('--checkpoint', default=None,
                        help='Package a checkpoint for testing (skips installed model)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducible sampling')
    args = parser.parse_args()

    random.seed(args.seed)

    data_dir = args.data or os.path.join(TRAINING_DIR, 'ocr_train_data')
    tessdata = args.tessdata or TESSDATA_DIR

    # Load card name database
    print("[INIT] Loading card name database...")
    db = CardNameDB(args.db)

    # Package checkpoint if specified
    if args.checkpoint:
        print(f"[INIT] Packaging checkpoint: {args.checkpoint}")
        model_path = package_checkpoint(args.checkpoint, args.model)
        if not model_path:
            sys.exit(1)
        # Install to tessdata for testing
        import shutil
        install_path = os.path.join(TESSDATA_DIR, f'{args.model}.traineddata')
        shutil.copy2(model_path, install_path)
        print(f"[INIT] Installed: {install_path}")

    if args.compare:
        compare_models(data_dir, db, args.samples)
    else:
        validate(data_dir, args.model, tessdata, db, args.samples,
                 hard_only=args.hard_only)


if __name__ == '__main__':
    main()
