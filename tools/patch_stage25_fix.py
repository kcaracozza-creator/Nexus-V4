#!/usr/bin/env python3
"""
Patch 6: Stage 2.5 OCR name fast-path + enchantments stopword fix.
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# Fix 1: After Stage 2.5 runs OCR, check extracted card name first
old_ocr_words = """        # Run OCR once and check against ALL top-k candidates (not just top-1)
        ocr_check = run_ocr(image_path)
        ocr_full = ocr_check.get('full_text', '') if ocr_check.get('success') else ''
        # All unique words from full OCR text (>=3 chars, alphabetic)
        import re as _re
        ocr_all_words = set(_re.findall(r'[a-zA-Z]{3,}', ocr_full.lower()))
        logger.info(f\"[ACR] Near-miss OCR words: {sorted(ocr_all_words)[:15]}\")"""

new_ocr_words = """        # Run OCR once and check against ALL top-k candidates (not just top-1)
        ocr_check = run_ocr(image_path)
        ocr_full = ocr_check.get('full_text', '') if ocr_check.get('success') else ''
        # All unique words from full OCR text (>=3 chars, alphabetic)
        import re as _re
        ocr_all_words = set(_re.findall(r'[a-zA-Z]{3,}', ocr_full.lower()))
        logger.info(f\"[ACR] Near-miss OCR words: {sorted(ocr_all_words)[:15]}\")

        # FAST PATH: if OCR extracted a card name, look it up directly
        _ocr_xname = ocr_check.get('card_name', '').strip() if ocr_check.get('success') else ''
        if _ocr_xname and len(_ocr_xname) >= 4:
            try:
                from difflib import SequenceMatcher as _SM_x
                _xmeta = _zultan_metadata(card_type=card_type, card_name=_ocr_xname, source_confidence=0)
                if _xmeta.get('success') and _xmeta.get('card_name'):
                    _xname = _xmeta.get('card_name', '')
                    _xsim = _SM_x(None, _ocr_xname.lower(), _xname.lower()).ratio() * 100
                    logger.info(f\"[ACR] OCR name '{_ocr_xname}' lookup -> '{_xname}' ({_xsim:.1f}%)\")
                    if _xsim >= 70:
                        _xconf = min(art['confidence'] + 3.0, 97.0)
                        result.update({'success': True, 'card_name': _xname,
                            'set_code': _xmeta.get('set_code'),
                            'collector_number': _xmeta.get('collector_number'),
                            'confidence': _xconf, 'stage': 'art_match',
                            'method': 'ocr_name_direct', 'card': _xmeta.get('card'),
                            'stages_run': stages_run,
                            'elapsed_ms': int((time.time() - start_time) * 1000)})
                        logger.info(f\"[ACR] Near-miss OCR name confirmed: {_xname!r} @ {_xconf:.1f}%\")
                        return result
            except Exception as _xe:
                logger.warning(f\"[ACR] OCR name fast-path failed: {_xe}\")"""

if old_ocr_words in content:
    content = content.replace(old_ocr_words, new_ocr_words, 1)
    print("Fix 1 applied: OCR name fast-path in Stage 2.5")
else:
    print("ERROR: Fix 1 target not found")
    sys.exit(1)

# Fix 2: Add enchantments (plural) to stopwords
old_sw = "stopwords = {'creature', 'instant', 'sorcery', 'artifact', 'enchantment', 'planeswalker',"
new_sw = "stopwords = {'creature', 'instant', 'sorcery', 'artifact', 'enchantment', 'enchantments', 'planeswalker',"

if old_sw in content:
    content = content.replace(old_sw, new_sw, 1)
    print("Fix 2 applied: enchantments in stopwords")
else:
    print("WARNING: stopwords line not found")

with open(SERVER, "w") as f:
    f.write(content)

import subprocess
r = subprocess.run(['python3', '-c', f'import py_compile; py_compile.compile("{SERVER}", doraise=True)'],
                   capture_output=True, text=True)
if r.returncode == 0:
    print("Syntax OK")
else:
    print(f"SYNTAX ERROR: {r.stderr}")
    sys.exit(1)

print("All patches applied")
