"""
NEXUS Auth Engine — Universal Memorabilia Authentication
No SKU database. Scoring based on:
  - Image quality per step
  - Hash fingerprint (tamper-proof)
  - Item type scoring weights
  - Optional OCR field extraction
"""

import uuid
import hashlib
import os
import re
import json
import base64
import time
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

import requests

from nexus_auth.item_types import get_item, ITEM_TYPES

logger = logging.getLogger("NEXUS_AUTH")

# ---------------------------------------------------------------------------
# Config — Danielson is the scanner in venue mode
# ---------------------------------------------------------------------------
DANIELSON_URL = os.getenv("DANIELSON_URL", "http://192.168.1.219:5001")
ZULTAN_URL    = os.getenv("ZULTAN_URL",    "http://192.168.1.152:8000")

SCAN_DIR      = os.path.join(os.path.expanduser("~"), "nexus_auth_scans")
COUNTER_FILE  = os.path.join(SCAN_DIR, ".item_counter")

os.makedirs(SCAN_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

@dataclass
class AuthSession:
    session_id:     str = ""
    item_type_key:  str = "other"
    timestamp_start: Optional[datetime] = None
    timestamp_end:   Optional[datetime] = None
    operator_name:  str = "NEXUS Operator"

    # 5 image slots — values are local file paths
    images: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "step_1_front":     None,
        "step_2_signature": None,
        "step_3_tag":       None,
        "step_4_detail":    None,
        "step_5_uv":        None,
    })

    # OCR-extracted fields (from step 2 and 3)
    ocr_data: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "text_raw":          None,
        "serial_number":     None,
        "cert_number":       None,
        "player_name":       None,
        "team":              None,
        "year":              None,
        "edition":           None,
        "grader":            None,
        "grade":             None,
        "manufacturer":      None,
    })

    # Scoring result
    scoring: Dict[str, Any] = field(default_factory=lambda: {
        "status":            "PENDING",
        "front_captured":    False,
        "signature_captured":False,
        "tag_captured":      False,
        "uv_captured":       False,
        "confidence_score":  0.0,
        "images_captured":   0,
    })

    certificate: Optional[Dict] = None
    item_id:     Optional[str]  = None
    auth_hash:   Optional[str]  = None
    nft_tx:      Optional[str]  = None     # Polygon tx hash after mint


def create_session(item_type_key: str, operator: str = "NEXUS Operator") -> AuthSession:
    s = AuthSession()
    s.session_id      = str(uuid.uuid4())
    s.item_type_key   = item_type_key
    s.timestamp_start = datetime.now()
    s.operator_name   = operator
    return s


# ---------------------------------------------------------------------------
# Image capture — Danielson CZUR endpoint
# ---------------------------------------------------------------------------

def capture_image(session: AuthSession, step_key: str,
                  uv_mode: bool = False) -> Optional[str]:
    """
    Trigger camera capture on Danielson.
    Returns local file path, or None on failure.
    """
    try:
        if uv_mode:
            _uv_on()
            time.sleep(0.5)

        r = requests.post(
            f"{DANIELSON_URL}/api/capture/czur",
            json={"width": 3264, "height": 2448},
            timeout=30,
        )

        if uv_mode:
            _uv_off()

        if r.status_code != 200:
            logger.error(f"Capture failed: HTTP {r.status_code}")
            return None

        data = r.json()
        if not data.get("success"):
            logger.error(f"Capture unsuccessful: {data.get('error')}")
            return None

        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session.session_id[:8]}_{step_key}_{ts}.jpg"
        filepath = os.path.join(SCAN_DIR, filename)

        snarf_path = data.get("image_path")
        downloaded = False

        if snarf_path:
            try:
                dl = requests.get(
                    f"{DANIELSON_URL}/api/image",
                    params={"path": snarf_path},
                    timeout=15,
                )
                if dl.status_code == 200 and len(dl.content) > 1000:
                    with open(filepath, "wb") as f:
                        f.write(dl.content)
                    downloaded = True
            except Exception as e:
                logger.warning(f"Full image download failed: {e}")

        if not downloaded:
            card_b64 = data.get("card_image_b64")
            if card_b64:
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(card_b64))
            else:
                logger.error("No image data in response")
                return None

        # Track the Danielson-side path for OCR calls
        if not hasattr(session, '_remote_paths'):
            session._remote_paths = {}
        session._remote_paths[step_key] = snarf_path

        session.images[step_key] = filepath
        logger.info(f"Captured {step_key}: {filepath}")
        return filepath

    except requests.exceptions.ConnectionError:
        logger.error("Danielson unreachable")
        return None
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return None


# ---------------------------------------------------------------------------
# UV light control
# ---------------------------------------------------------------------------

def _uv_on():
    try:
        for ch in [1, 2]:
            requests.post(
                f"{DANIELSON_URL}/api/lights/ch/{ch}",
                json={"r": 80, "g": 0, "b": 255},
                timeout=3,
            )
        logger.info("UV lights ON")
    except Exception as e:
        logger.warning(f"UV on failed: {e}")


def _uv_off():
    try:
        requests.post(
            f"{DANIELSON_URL}/api/lights/ch/1",
            json={"r": 0, "g": 50, "b": 0},
            timeout=3,
        )
        requests.post(
            f"{DANIELSON_URL}/api/lights/ch/2",
            json={"r": 0, "g": 0, "b": 0},
            timeout=3,
        )
        logger.info("UV lights OFF")
    except Exception as e:
        logger.warning(f"UV off failed: {e}")


# ---------------------------------------------------------------------------
# OCR extraction — generalized for all memorabilia
# ---------------------------------------------------------------------------

SERIAL_PATTERNS = [
    r"[A-Z]{2,3}[\s-]?\d{6,12}",
    r"Serial[\s:#]*([A-Z0-9-]+)",
    r"Cert[\s:#]*([A-Z0-9-]+)",
    r"COA[\s:#]*([A-Z0-9-]+)",
    r"#\s*(\d{4,12})",
    r"No\.?\s*(\d{4,12})",
]

EDITION_PATTERN  = r"(\d+)\s*/\s*(\d+)"           # e.g. "23 / 500"
YEAR_PATTERN     = r"\b(19[89]\d|20[012]\d)\b"
GRADE_PATTERN    = r"\b(PSA|BGS|SGC|CSG|HGA)\b[\s.-]*(\d+(?:\.\d)?)"
GRADERS          = ["PSA", "BGS", "SGC", "CSG", "HGA", "JSA", "Beckett"]

KNOWN_TEAMS = [
    "Yankees", "Red Sox", "Lakers", "Celtics", "Warriors", "Heat",
    "Patriots", "Cowboys", "Packers", "Chiefs", "Giants", "Jets",
    "Maple Leafs", "Canadiens", "Blackhawks", "Penguins",
    "Barcelona", "Real Madrid", "Manchester United", "Liverpool",
    "Brazil", "Argentina", "USA", "France", "England", "Germany",
]


def run_ocr(session: AuthSession, step_key: str) -> str:
    """Run OCR on a captured image, return raw text."""
    filepath = session.images.get(step_key)
    if not filepath or not os.path.exists(filepath):
        return ""

    remote_path = getattr(session, '_remote_paths', {}).get(step_key)

    try:
        payload = {}
        if remote_path:
            payload["image_path"] = remote_path
        else:
            with open(filepath, "rb") as f:
                payload["image_b64"] = base64.b64encode(f.read()).decode()

        r = requests.post(
            f"{DANIELSON_URL}/api/ocr",
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                text = data.get("text", "")
                if not text:
                    lines = data.get("lines", [])
                    text  = "\n".join(str(l) for l in lines)
                return text
    except Exception as e:
        logger.error(f"OCR error: {e}")

    return ""


def extract_ocr_fields(text: str) -> Dict[str, Optional[str]]:
    """Parse OCR text into structured fields."""
    result: Dict[str, Optional[str]] = {
        "text_raw":      text[:500] if text else None,
        "serial_number": None,
        "cert_number":   None,
        "player_name":   None,
        "team":          None,
        "year":          None,
        "edition":       None,
        "grader":        None,
        "grade":         None,
        "manufacturer":  None,
    }

    if not text:
        return result

    # Serial / Cert number
    for pat in SERIAL_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["serial_number"] = m.group(0).strip()
            break

    # Edition (e.g. 23/500)
    m = re.search(EDITION_PATTERN, text)
    if m:
        result["edition"] = f"{m.group(1)}/{m.group(2)}"

    # Year
    m = re.search(YEAR_PATTERN, text)
    if m:
        result["year"] = m.group(1)

    # Grader + grade
    m = re.search(GRADE_PATTERN, text, re.IGNORECASE)
    if m:
        result["grader"] = m.group(1).upper()
        result["grade"]  = m.group(2)
    else:
        for g in GRADERS:
            if g.lower() in text.lower():
                result["grader"] = g
                break

    # Team
    for team in KNOWN_TEAMS:
        if team.lower() in text.lower():
            result["team"] = team
            break

    return result


# ---------------------------------------------------------------------------
# Scoring — universal, driven by item type weights
# ---------------------------------------------------------------------------

MIN_FILE_SIZE = 5_000  # bytes — anything smaller = bad capture


def _image_valid(path: Optional[str]) -> bool:
    return bool(path and os.path.exists(path) and os.path.getsize(path) > MIN_FILE_SIZE)


def score_session(session: AuthSession) -> Dict[str, Any]:
    """
    Score based on image capture quality + item type weights.
    No external database lookup — authenticity comes from the hash fingerprint
    plus human-in-the-loop approval of each image during capture.
    """
    item   = get_item(session.item_type_key)
    weights = item["scoring"]

    sc = session.scoring
    sc["front_captured"]     = _image_valid(session.images.get("step_1_front"))
    sc["signature_captured"] = _image_valid(session.images.get("step_2_signature"))
    sc["tag_captured"]       = _image_valid(session.images.get("step_3_tag"))
    sc["uv_captured"]        = _image_valid(session.images.get("step_5_uv"))
    sc["images_captured"]    = sum(
        1 for v in session.images.values() if _image_valid(v)
    )

    score = 0.0
    if sc["front_captured"]:
        score += weights["front_captured"]
    if sc["signature_captured"]:
        score += weights["signature_captured"]
    if sc["tag_captured"]:
        score += weights["tag_captured"]
    if sc["uv_captured"]:
        score += weights["uv_captured"]

    # Bonus: serial/cert number extracted from OCR
    if session.ocr_data.get("serial_number") or session.ocr_data.get("cert_number"):
        score = min(score + 5.0, 100.0)

    # Bonus: grader found (e.g. PSA/BGS)
    if session.ocr_data.get("grader"):
        score = min(score + 5.0, 100.0)

    sc["confidence_score"] = min(round(score, 1), 100.0)
    sc["status"] = "AUTHENTICATED" if sc["confidence_score"] >= 60.0 else "FAILED"

    session.scoring      = sc
    session.timestamp_end = datetime.now()
    return sc


# ---------------------------------------------------------------------------
# Certificate generation
# ---------------------------------------------------------------------------

def _next_item_number() -> int:
    last = 0
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE) as f:
                last = int(f.read().strip())
        except (ValueError, IOError):
            pass
    nxt = last + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(nxt))
    return nxt


def generate_certificate(session: AuthSession) -> Dict[str, Any]:
    """
    Build tamper-proof certificate.
    Hash = SHA-256 of all image bytes + metadata.
    This hash is what gets minted to Polygon.
    """
    item_id = f"NEXUS-AUTH-{datetime.now().year}-{_next_item_number():07d}"
    session.item_id = item_id

    hasher = hashlib.sha256()
    for key in sorted(session.images.keys()):
        path = session.images[key]
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                hasher.update(f.read())

    hasher.update(session.item_type_key.encode())
    hasher.update(session.session_id.encode())
    hasher.update(str(session.timestamp_start).encode())
    hasher.update((session.ocr_data.get("serial_number") or "").encode())

    auth_hash = hasher.hexdigest()
    session.auth_hash = auth_hash

    item = get_item(session.item_type_key)

    cert = {
        "status":        session.scoring["status"],
        "item_id":       item_id,
        "session_id":    session.session_id,
        "item_type":     session.item_type_key,
        "item_label":    item["label"],
        "item_icon":     item["icon"],
        "ocr_data":      {k: v for k, v in session.ocr_data.items() if v},
        "images": {
            "front":     session.images.get("step_1_front"),
            "signature": session.images.get("step_2_signature"),
            "tag":       session.images.get("step_3_tag"),
            "detail":    session.images.get("step_4_detail"),
            "uv":        session.images.get("step_5_uv"),
        },
        "images_captured": session.scoring["images_captured"],
        "authentication": {
            "operator":    session.operator_name,
            "date":        session.timestamp_start.strftime("%B %d, %Y"),
            "time":        session.timestamp_start.strftime("%I:%M %p"),
            "confidence":  session.scoring["confidence_score"],
            "checks": {
                "front_captured":     session.scoring["front_captured"],
                "signature_captured": session.scoring["signature_captured"],
                "tag_captured":       session.scoring["tag_captured"],
                "uv_captured":        session.scoring["uv_captured"],
            },
        },
        "blockchain": {
            "hash":             auth_hash,
            "nft_tx":           session.nft_tx,
            "verification_url": f"nexus.io/auth/{item_id}",
            "network":          "Polygon",
        },
    }

    session.certificate = cert

    # Save locally
    cert_path = os.path.join(SCAN_DIR, f"{item_id}_cert.json")
    with open(cert_path, "w") as f:
        json.dump(cert, f, indent=2, default=str)

    logger.info(f"Certificate: {item_id} | {session.scoring['status']} | hash:{auth_hash[:16]}...")
    return cert


# ---------------------------------------------------------------------------
# Full pipeline (called after all 5 steps)
# ---------------------------------------------------------------------------

def run_authentication(session: AuthSession) -> Dict[str, Any]:
    """
    1. OCR on signature and tag images
    2. Score session
    3. Generate certificate
    """
    # OCR step 2 (signature — looking for serial/cert numbers)
    sig_text = run_ocr(session, "step_2_signature")
    if sig_text:
        fields = extract_ocr_fields(sig_text)
        for k, v in fields.items():
            if v and not session.ocr_data.get(k):
                session.ocr_data[k] = v

    # OCR step 3 (tag / label — primary source of structured data)
    tag_text = run_ocr(session, "step_3_tag")
    if tag_text:
        fields = extract_ocr_fields(tag_text)
        for k, v in fields.items():
            if v and not session.ocr_data.get(k):
                session.ocr_data[k] = v
        if not session.ocr_data.get("text_raw"):
            session.ocr_data["text_raw"] = tag_text[:500]

    score_session(session)
    cert = generate_certificate(session)
    return cert
