"""
NEXUS Merchandise Authentication Engine
Handles: session management, OCR extraction, barcode decode,
         verification scoring, certificate generation.
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
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger("MERCH_AUTH")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DANIELSON_URL = os.getenv("DANIELSON_URL", "http://192.168.1.219:5001")
ZULTAN_URL = os.getenv("ZULTAN_URL", "http://192.168.1.152:8000")

SCAN_DIR = os.path.join(os.path.expanduser("~"), "nexus_merch_scans")
COUNTER_FILE = os.path.join(SCAN_DIR, ".item_counter")

os.makedirs(SCAN_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# FIFA Merchandise Database (mock — expandable)
# ---------------------------------------------------------------------------
FIFA_MERCHANDISE_DATABASE = {
    "FIFA-2026-USA-HOME-M": {
        "name": "USA Home Jersey - Medium",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-USA-HOME-L": {
        "name": "USA Home Jersey - Large",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-USA-HOME-S": {
        "name": "USA Home Jersey - Small",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-USA-AWAY-M": {
        "name": "USA Away Jersey - Medium",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-MEX-HOME-M": {
        "name": "Mexico Home Jersey - Medium",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-MEX-AWAY-L": {
        "name": "Mexico Away Jersey - Large",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-BRA-HOME-M": {
        "name": "Brazil Home Jersey - Medium",
        "manufacturer": "Nike",
        "official": True,
        "msrp": 164.99,
    },
    "FIFA-2026-ENG-HOME-L": {
        "name": "England Home Jersey - Large",
        "manufacturer": "Nike",
        "official": True,
        "msrp": 164.99,
    },
    "FIFA-2026-GER-HOME-M": {
        "name": "Germany Home Jersey - Medium",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 149.99,
    },
    "FIFA-2026-ARG-HOME-M": {
        "name": "Argentina Home Jersey - Medium",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 159.99,
    },
    "FIFA-2026-FRA-HOME-M": {
        "name": "France Home Jersey - Medium",
        "manufacturer": "Nike",
        "official": True,
        "msrp": 164.99,
    },
    "FIFA-2026-BALL-OFFICIAL": {
        "name": "Official Match Ball",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 169.99,
    },
    "FIFA-2026-SCARF-USA": {
        "name": "USA Supporter Scarf",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 34.99,
    },
    "FIFA-2026-CAP-OFFICIAL": {
        "name": "Official Tournament Cap",
        "manufacturer": "Adidas",
        "official": True,
        "msrp": 29.99,
    },
    "FIFA-2026-PENNANT-FINAL": {
        "name": "Final Match Commemorative Pennant",
        "manufacturer": "FIFA Licensing",
        "official": True,
        "msrp": 49.99,
    },
}


def fifa_database_lookup(sku: str) -> Optional[Dict]:
    """Look up a SKU in the FIFA merchandise database."""
    if not sku:
        return None
    return FIFA_MERCHANDISE_DATABASE.get(sku.upper().strip())


# ---------------------------------------------------------------------------
# Session data model
# ---------------------------------------------------------------------------
@dataclass
class MerchandiseAuthSession:
    session_id: str = ""
    timestamp_start: Optional[datetime] = None
    timestamp_end: Optional[datetime] = None
    operator_name: str = "NEXUS Operator"

    # 5 capture steps — values are file paths on disk
    images: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "step_1_primary_logo": None,
        "step_2_manufacturer_tag": None,
        "step_3_care_label": None,
        "step_4_hang_tag": None,
        "step_5_uv_scan": None,
    })

    # Extracted OCR / barcode data
    extracted_data: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "sku": None,
        "manufacturer": None,
        "size": None,
        "country": None,
        "barcode": None,
        "material": None,
    })

    # Verification result
    verification: Dict[str, Any] = field(default_factory=lambda: {
        "status": "PENDING",
        "sku_in_database": False,
        "logo_verified": False,
        "tag_format_verified": False,
        "uv_features_verified": False,
        "confidence_score": 0.0,
    })

    certificate: Optional[Dict] = None
    item_id: Optional[str] = None
    blockchain_hash: Optional[str] = None


def create_merchandise_session(operator: str = "NEXUS Operator") -> MerchandiseAuthSession:
    """Create a fresh authentication session."""
    session = MerchandiseAuthSession()
    session.session_id = str(uuid.uuid4())
    session.timestamp_start = datetime.now()
    session.operator_name = operator
    return session


# ---------------------------------------------------------------------------
# Image capture — talks to DANIELSON's CZUR endpoint
# ---------------------------------------------------------------------------
def capture_image(session: MerchandiseAuthSession, step_name: str,
                  uv_mode: bool = False) -> Optional[str]:
    """
    Trigger CZUR capture on DANIELSON and save result locally.
    Returns the local file path, or None on failure.
    """
    try:
        # UV mode: turn on UV LEDs before capture
        if uv_mode:
            trigger_uv_on()
            time.sleep(0.5)

        r = requests.post(
            f"{DANIELSON_URL}/api/capture/czur",
            json={"width": 3264, "height": 2448},
            timeout=30,
        )

        if uv_mode:
            trigger_uv_off()

        if r.status_code != 200:
            logger.error(f"CZUR capture failed: HTTP {r.status_code}")
            return None

        data = r.json()
        if not data.get("success"):
            logger.error(f"CZUR capture unsuccessful: {data.get('error')}")
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session.session_id[:8]}_{step_name}_{ts}.jpg"
        filepath = os.path.join(SCAN_DIR, filename)

        # For merchandise we want the FULL uncropped image (not card region crop).
        # Download from DANIELSON using the image_path returned by capture.
        remote_path = data.get("image_path")
        downloaded = False
        if remote_path:
            try:
                dl = requests.get(
                    f"{DANIELSON_URL}/api/image",
                    params={"path": remote_path},
                    timeout=15,
                )
                if dl.status_code == 200 and len(dl.content) > 1000:
                    with open(filepath, "wb") as f:
                        f.write(dl.content)
                    downloaded = True
                    logger.info(f"Full image downloaded: {len(dl.content)} bytes")
            except Exception as e:
                logger.warning(f"Full image download failed, falling back to b64 crop: {e}")

        # Fallback: use the cropped card_image_b64
        if not downloaded:
            card_b64 = data.get("card_image_b64")
            if card_b64:
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(card_b64))
            else:
                logger.error("No image data available")
                return None

        # Also store DANIELSON-side path for OCR calls
        if not hasattr(session, '_remote_paths'):
            session._remote_paths = {}
        session._remote_paths[step_name] = remote_path

        session.images[step_name] = filepath
        logger.info(f"Captured {step_name}: {filepath} ({os.path.getsize(filepath)} bytes)")
        return filepath

    except requests.exceptions.ConnectionError:
        logger.error("DANIELSON unreachable for CZUR capture")
        return None
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return None


# ---------------------------------------------------------------------------
# UV light control — ESP32 lightbox on DANIELSON
# ---------------------------------------------------------------------------
def trigger_uv_on():
    """Turn on UV-like lighting via ESP32 lightbox (purple/blue LEDs)."""
    try:
        # Use RGB LEDs in UV-like spectrum (deep blue/purple)
        requests.post(
            f"{DANIELSON_URL}/api/lights/ch/1",
            json={"r": 80, "g": 0, "b": 255},
            timeout=3,
        )
        requests.post(
            f"{DANIELSON_URL}/api/lights/ch/2",
            json={"r": 80, "g": 0, "b": 255},
            timeout=3,
        )
        logger.info("UV lights ON (purple/blue)")
    except Exception as e:
        logger.warning(f"UV light control failed: {e}")


def trigger_uv_off():
    """Turn off UV, restore dim green ready state."""
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
        logger.warning(f"UV light off failed: {e}")


# ---------------------------------------------------------------------------
# OCR tag extraction — calls DANIELSON OCR
# ---------------------------------------------------------------------------
KNOWN_MANUFACTURERS = [
    "ADIDAS", "NIKE", "PUMA", "REEBOK", "NEW BALANCE", "UNDER ARMOUR",
    "FANATICS", "MITCHELL & NESS", "NEW ERA", "47 BRAND", "MAJESTIC",
]

SKU_PATTERNS = [
    r"FIFA-\d{4}-[A-Z]+-[A-Z]+-[A-Z]+",
    r"FIFA-\d{4}-[A-Z]+-[A-Z]+",
    r"[A-Z]{2,4}-\d{5,10}",
    r"SKU[:\s]*([A-Z0-9-]+)",
    r"Style[:\s#]*([A-Z0-9-]+)",
    r"Art[:\s#]*([A-Z0-9-]+)",
]


def extract_tag_data(image_path: str, remote_path: str = None) -> Dict[str, Optional[str]]:
    """
    Run OCR on a manufacturer tag image and extract structured data.
    Returns dict with sku, manufacturer, size, country, material.
    """
    result = {
        "sku": None,
        "manufacturer": None,
        "size": None,
        "country": None,
        "material": None,
    }

    ocr_text = _run_ocr(image_path, remote_path=remote_path)
    if not ocr_text:
        return result

    logger.info(f"OCR raw text: {ocr_text[:200]}")

    # Extract SKU
    for pattern in SKU_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            result["sku"] = match.group(0).upper().strip()
            # Clean "SKU:" prefix
            if result["sku"].startswith(("SKU:", "SKU ")):
                result["sku"] = result["sku"].split(":", 1)[-1].strip()
            break

    # Extract manufacturer
    for mfg in KNOWN_MANUFACTURERS:
        if mfg.lower() in ocr_text.lower():
            result["manufacturer"] = mfg.title()
            break

    # Extract size
    size_match = re.search(
        r"\b(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL)\b", ocr_text, re.IGNORECASE
    )
    if size_match:
        result["size"] = size_match.group(1).upper()

    # Extract country of origin
    country_match = re.search(r"Made in ([A-Za-z\s]+)", ocr_text, re.IGNORECASE)
    if country_match:
        result["country"] = country_match.group(1).strip().title()

    # Extract material composition
    material_match = re.search(
        r"(\d+%\s*(?:polyester|cotton|nylon|spandex|elastane|recycled)[^,\n]*(?:,\s*\d+%\s*\w+)*)",
        ocr_text, re.IGNORECASE,
    )
    if material_match:
        result["material"] = material_match.group(1).strip()

    return result


def _run_ocr(image_path: str, remote_path: str = None) -> str:
    """Send image to DANIELSON OCR and return raw text."""
    try:
        payload = {}
        if remote_path:
            # Use DANIELSON-side path directly (no base64 needed)
            payload["image_path"] = remote_path
        else:
            # Fall back to base64
            with open(image_path, "rb") as f:
                payload["image_b64"] = base64.b64encode(f.read()).decode()

        r = requests.post(
            f"{DANIELSON_URL}/api/ocr",
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                # Collect all text — enhanced OCR returns various fields
                text = data.get("text", "")
                if not text:
                    lines = data.get("lines", [])
                    if lines:
                        text = "\n".join(str(l) for l in lines)
                if not text:
                    # Card OCR format: check card_name, set_code, etc.
                    parts = []
                    for key in ("card_name", "set_code", "collector_number",
                                "ocr_results", "raw_text"):
                        val = data.get(key)
                        if val:
                            parts.append(str(val))
                    text = "\n".join(parts)
                return text
        logger.warning(f"OCR returned {r.status_code}")
        return ""
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Barcode decoder
# ---------------------------------------------------------------------------
def decode_barcode(image_path: str) -> Optional[str]:
    """Attempt to decode a barcode from the image."""
    try:
        from pyzbar import pyzbar
        from PIL import Image

        img = Image.open(image_path)
        barcodes = pyzbar.decode(img)
        if barcodes:
            barcode_data = barcodes[0].data.decode("utf-8")
            logger.info(f"Barcode decoded: {barcode_data}")
            return barcode_data
    except ImportError:
        logger.warning("pyzbar not installed — trying zxing fallback")
    except Exception as e:
        logger.warning(f"Barcode decode error: {e}")

    # Fallback: try DANIELSON's barcode endpoint if available
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        r = requests.post(
            f"{DANIELSON_URL}/api/barcode",
            json={"image_b64": img_b64},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("barcode")
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Verification engine
# ---------------------------------------------------------------------------
def verify_merchandise(session: MerchandiseAuthSession) -> Dict[str, Any]:
    """
    Score the authentication session across 4 checks.
    Returns the updated verification dict.
    """
    v = session.verification
    v["sku_in_database"] = False
    v["logo_verified"] = False
    v["tag_format_verified"] = False
    v["uv_features_verified"] = False
    v["confidence_score"] = 0.0

    # CHECK 1: SKU in FIFA database (40 points)
    sku = session.extracted_data.get("sku")
    db_entry = fifa_database_lookup(sku)
    if db_entry:
        v["sku_in_database"] = True
        v["confidence_score"] += 40.0
        # Cross-check manufacturer
        if (session.extracted_data.get("manufacturer") and
                session.extracted_data["manufacturer"].lower() == db_entry["manufacturer"].lower()):
            v["confidence_score"] += 5.0  # bonus

    # CHECK 2: Logo photo captured and non-trivial (20 points)
    logo_path = session.images.get("step_1_primary_logo")
    if logo_path and os.path.exists(logo_path):
        if os.path.getsize(logo_path) > 5000:
            v["logo_verified"] = True
            v["confidence_score"] += 20.0

    # CHECK 3: Tag data extracted (20 points)
    has_manufacturer = bool(session.extracted_data.get("manufacturer"))
    has_size = bool(session.extracted_data.get("size"))
    has_sku = bool(session.extracted_data.get("sku"))
    if has_manufacturer and (has_size or has_sku):
        v["tag_format_verified"] = True
        v["confidence_score"] += 20.0

    # CHECK 4: UV scan captured (20 points)
    uv_path = session.images.get("step_5_uv_scan")
    if uv_path and os.path.exists(uv_path):
        if os.path.getsize(uv_path) > 5000:
            v["uv_features_verified"] = True
            v["confidence_score"] += 20.0

    # Cap at 100
    v["confidence_score"] = min(v["confidence_score"], 100.0)

    # Final status — NEXUS performs a screening check only (not professional authentication)
    if v["confidence_score"] >= 60.0:
        v["status"] = "CHECKS_PASSED"
    else:
        v["status"] = "CHECKS_INCOMPLETE"

    session.verification = v
    session.timestamp_end = datetime.now()
    return v


# ---------------------------------------------------------------------------
# Certificate generation
# ---------------------------------------------------------------------------
def _next_item_number() -> int:
    """Thread-safe sequential item number."""
    last = 0
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                last = int(f.read().strip())
        except (ValueError, IOError):
            pass
    nxt = last + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(nxt))
    return nxt


def generate_certificate(session: MerchandiseAuthSession) -> Dict[str, Any]:
    """Build the authentication certificate and blockchain hash."""
    # Item ID
    item_id = f"NEXUS-{datetime.now().year}-{_next_item_number():06d}"
    session.item_id = item_id

    # Composite SHA-256 hash from all images + metadata
    hasher = hashlib.sha256()
    for step in sorted(session.images.keys()):
        path = session.images[step]
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                hasher.update(f.read())
    hasher.update((session.extracted_data.get("sku") or "").encode())
    hasher.update(session.session_id.encode())
    hasher.update(str(session.timestamp_start).encode())

    blockchain_hash = hasher.hexdigest()
    session.blockchain_hash = blockchain_hash

    # Count captured images
    captured = sum(1 for v in session.images.values() if v and os.path.exists(v))

    certificate = {
        "status": session.verification["status"],
        "item_id": item_id,
        "session_id": session.session_id,
        "sku": session.extracted_data.get("sku"),
        "sku_lookup": fifa_database_lookup(session.extracted_data.get("sku")),
        "manufacturer": session.extracted_data.get("manufacturer"),
        "size": session.extracted_data.get("size"),
        "country": session.extracted_data.get("country"),
        "material": session.extracted_data.get("material"),
        "barcode": session.extracted_data.get("barcode"),
        "images_captured": captured,
        "images": {k: v for k, v in session.images.items()},
        "screening": {
            "location": "NEXUS Screening Station",
            "date": session.timestamp_start.strftime("%B %d, %Y"),
            "time": session.timestamp_start.strftime("%I:%M %p"),
            "screening_score": round(session.verification["confidence_score"], 1),
            "checks": {
                "sku_in_database": session.verification["sku_in_database"],
                "logo_captured": session.verification["logo_verified"],
                "tag_data_extracted": session.verification["tag_format_verified"],
                "uv_scan_captured": session.verification["uv_features_verified"],
            },
            "disclaimer": (
                "This is an automated screening record only. "
                "NEXUS does not provide professional authentication services. "
                "Results do not constitute a guarantee of authenticity."
            ),
        },
        "blockchain": {
            "hash": blockchain_hash,
            "verification_url": f"nexus.io/verify/{item_id}",
        },
    }

    session.certificate = certificate
    logger.info(f"Certificate generated: {item_id} — {session.verification['status']}")
    return certificate


# ---------------------------------------------------------------------------
# Convenience: full pipeline
# ---------------------------------------------------------------------------
def run_full_verification(session: MerchandiseAuthSession) -> Dict[str, Any]:
    """
    After all 5 images are captured, run OCR + barcode + verify + cert.
    Called by the UI after SCREEN 14 approve.
    """
    # Extract tag data from manufacturer tag image
    tag_img = session.images.get("step_2_manufacturer_tag")
    remote_paths = getattr(session, '_remote_paths', {})
    if tag_img and os.path.exists(tag_img):
        tag_data = extract_tag_data(
            tag_img, remote_path=remote_paths.get("step_2_manufacturer_tag")
        )
        session.extracted_data.update({k: v for k, v in tag_data.items() if v})

    # Decode barcode from hang tag
    hang_img = session.images.get("step_4_hang_tag")
    if hang_img and os.path.exists(hang_img):
        barcode = decode_barcode(hang_img)
        if barcode:
            session.extracted_data["barcode"] = barcode

    # Run verification scoring
    verify_merchandise(session)

    # Generate certificate
    cert = generate_certificate(session)

    return cert
