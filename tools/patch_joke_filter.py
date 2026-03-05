#!/usr/bin/env python3
"""
Patch 9: Filter joke/acorn/silver-border sets from FAISS candidates.
Also expand candidate search to top 10 instead of top 5.
Also filter Stage 1 direct accept.
Also filter OCR name fast-path results.
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

JOKE_SETS = "{'fin', 'unf', 'unh', 'ust', 'unk', 'punk', 'rfin', 'wfin', 'ugl', 'unglued', 'htr', 'phtr'}"

# ── Fix 1: Filter joke sets from Stage 2.5 near-miss candidate loop ──────────
old1 = """        for candidate in all_candidates[:5]:
            cid = candidate.get('card_id')
            if not cid:
                continue
            try:
                cmeta = _zultan_metadata(card_type=card_type, card_id=cid, source_confidence=candidate.get('confidence', 0))
                if not cmeta.get('success'):
                    continue
                cname = cmeta.get('card_name', '')"""

new1 = """        _joke_sets = """ + JOKE_SETS + """

        for candidate in all_candidates[:10]:
            cid = candidate.get('card_id')
            if not cid:
                continue
            try:
                cmeta = _zultan_metadata(card_type=card_type, card_id=cid, source_confidence=candidate.get('confidence', 0))
                if not cmeta.get('success'):
                    continue
                if cmeta.get('set_code', '').lower() in _joke_sets:
                    logger.info(f"[ACR] Skip joke set: {cmeta.get('card_name')} ({cmeta.get('set_code')})")
                    continue
                cname = cmeta.get('card_name', '')"""

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied: joke set filter in Stage 2.5, expanded to top 10")
else:
    print("ERROR: Fix 1 target not found")
    sys.exit(1)

# ── Fix 2: Filter joke sets from Stage 1 direct accept ───────────────────────
old2 = """    if art.get('success') and art.get('confidence', 0) >= CONFIDENCE_THRESHOLD:
        # Direct art match — look up metadata and return
        meta = _zultan_metadata(card_type=card_type, card_id=art.get('card_id'), source_confidence=art.get('confidence', 0))
        if meta.get('success'):"""

new2 = """    _joke_sets_s1 = """ + JOKE_SETS + """

    if art.get('success') and art.get('confidence', 0) >= CONFIDENCE_THRESHOLD:
        # Direct art match — look up metadata and return
        meta = _zultan_metadata(card_type=card_type, card_id=art.get('card_id'), source_confidence=art.get('confidence', 0))
        if meta.get('success') and meta.get('set_code', '').lower() not in _joke_sets_s1:"""

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("Fix 2 applied: joke set filter on Stage 1 direct accept")
else:
    print("WARNING: Fix 2 Stage 1 target not found")

# ── Fix 3: Filter joke sets from OCR name fast-path ──────────────────────────
old3 = """                    if _xmeta.get('success') and _xmeta.get('card_name'):
                        _xname = _xmeta.get('card_name', '')"""

new3 = """                    _joke_sets_ocr = """ + JOKE_SETS + """
                    if _xmeta.get('success') and _xmeta.get('card_name') and _xmeta.get('set_code', '').lower() not in _joke_sets_ocr:
                        _xname = _xmeta.get('card_name', '')"""

if old3 in content:
    content = content.replace(old3, new3, 1)
    print("Fix 3 applied: joke set filter on OCR name fast-path")
else:
    print("WARNING: Fix 3 OCR fast-path target not found")

with open(SERVER, "w") as f:
    f.write(content)

import subprocess
r = subprocess.run(
    ['python3', '-c', f'import py_compile; py_compile.compile("{SERVER}", doraise=True)'],
    capture_output=True, text=True
)
if r.returncode == 0:
    print("Syntax OK")
else:
    print(f"SYNTAX ERROR: {r.stderr}")
    sys.exit(1)

print("All patches applied")
