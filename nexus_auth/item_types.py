"""
NEXUS Auth — Item Type Definitions
Every memorabilia category supported, with its own capture steps and scoring rules.
Add new types here, UI adapts automatically.
"""

# ---------------------------------------------------------------------------
# Capture step schema
# Each step: key, title, instruction, detail, skippable, run_ocr, uv_mode
# ---------------------------------------------------------------------------

_STEP_LOGO = {
    "key": "step_1_front",
    "num": 1,
    "title": "FRONT / PRIMARY FACE",
    "instruction": "Position item FRONT FACE in frame",
    "detail": "Capture the main identifying surface\nwhere signatures or branding appear",
    "review_question": "Is the front clearly visible and in focus?",
    "skippable": False,
    "run_ocr": False,
    "uv_mode": False,
}

_STEP_SIGNATURE = {
    "key": "step_2_signature",
    "num": 2,
    "title": "SIGNATURE / AUTOGRAPH",
    "instruction": "Position SIGNATURE area in frame",
    "detail": "Get close — fill the frame with the autograph\nMake sure ink is fully visible",
    "review_question": "Is the signature sharp and fully in frame?",
    "skippable": False,
    "run_ocr": True,
    "uv_mode": False,
}

_STEP_TAG = {
    "key": "step_3_tag",
    "num": 3,
    "title": "AUTHENTICATION TAG / LABEL",
    "instruction": "Locate any hologram, sticker, or COA tag\nPosition it in frame",
    "detail": "Official auth sticker, hologram, COA label,\nor manufacturer tag with serial number",
    "review_question": "Is the tag or hologram visible?",
    "skippable": True,
    "run_ocr": True,
    "uv_mode": False,
}

_STEP_DETAIL = {
    "key": "step_4_detail",
    "num": 4,
    "title": "DETAIL / SECONDARY FEATURE",
    "instruction": "Capture a secondary identifying detail",
    "detail": "",  # Overridden per item type
    "review_question": "Is the detail clearly captured?",
    "skippable": True,
    "run_ocr": False,
    "uv_mode": False,
}

_STEP_UV = {
    "key": "step_5_uv",
    "num": 5,
    "title": "UV SECURITY SCAN",
    "instruction": "Position item for UV scan\nUV lights activate automatically",
    "detail": "Detects UV-reactive ink, security threads,\nholograms, invisible watermarks",
    "review_question": "UV features visible?",
    "skippable": False,
    "run_ocr": False,
    "uv_mode": True,
}


def _build_steps(front_instr, front_detail, sig_detail, detail_instr, detail_detail):
    """Build the 5-step list for an item type with custom language."""
    steps = [
        {**_STEP_LOGO, "instruction": front_instr, "detail": front_detail},
        {**_STEP_SIGNATURE, "detail": sig_detail},
        {**_STEP_TAG},
        {**_STEP_DETAIL, "instruction": detail_instr, "detail": detail_detail},
        {**_STEP_UV},
    ]
    return steps


# ---------------------------------------------------------------------------
# Item Type Registry
# key: internal ID
# label: display name shown in UI
# icon: single emoji for visual pop
# category: grouping
# steps: 5-step capture workflow
# scoring: weights for verification scoring (must sum to 100)
# ---------------------------------------------------------------------------

ITEM_TYPES = {

    # ── SIGNED APPAREL ─────────────────────────────────────────────────────
    "signed_jersey": {
        "label": "Signed Jersey",
        "icon": "🏈",
        "category": "Signed Apparel",
        "steps": _build_steps(
            front_instr="Position jersey FRONT in frame\nNumber and team name should be visible",
            front_detail="Show full front of jersey\nTeam name, number, logo",
            sig_detail="Ink signature on fabric\nGet close — fill frame with autograph",
            detail_instr="Capture MANUFACTURER TAG inside collar",
            detail_detail="Nike, Adidas, Fanatics, Mitchell & Ness\nSize, year, authenticity tags",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 35,
            "tag_captured": 20,
            "uv_captured": 25,
        },
    },

    "signed_hat": {
        "label": "Signed Hat / Cap",
        "icon": "🧢",
        "category": "Signed Apparel",
        "steps": _build_steps(
            front_instr="Position hat FRONT PANEL in frame",
            front_detail="Team logo and team branding visible",
            sig_detail="Signature on brim, crown, or side panel",
            detail_instr="Capture SIZE TAG and manufacturer label",
            detail_detail="New Era, '47 Brand, etc.\nSize sticker, official tags",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 35,
            "tag_captured": 20,
            "uv_captured": 25,
        },
    },

    "signed_shoe": {
        "label": "Signed Shoe / Cleat",
        "icon": "👟",
        "category": "Signed Apparel",
        "steps": _build_steps(
            front_instr="Position shoe SIDE PROFILE in frame",
            front_detail="Full shoe visible — model and colorway identifiable",
            sig_detail="Signature on tongue, side, or heel area",
            detail_instr="Capture SOLE and model label",
            detail_detail="Model number, size, manufacturer\nAuthenticity tag if present",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 35,
            "tag_captured": 20,
            "uv_captured": 25,
        },
    },

    # ── SIGNED EQUIPMENT ───────────────────────────────────────────────────
    "signed_helmet": {
        "label": "Signed Helmet",
        "icon": "⛑️",
        "category": "Signed Equipment",
        "steps": _build_steps(
            front_instr="Position helmet FRONT FACE-MASK VIEW in frame",
            front_detail="Full helmet visible — team colors, decals, face mask",
            sig_detail="Signature on shell — get close to autograph area",
            detail_instr="Capture INTERIOR LABEL and certification sticker",
            detail_detail="Riddell, Schutt, etc.\nModel, year, safety certifications",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 35,
            "tag_captured": 15,
            "uv_captured": 25,
        },
    },

    "signed_bat": {
        "label": "Signed Baseball Bat",
        "icon": "⚾",
        "category": "Signed Equipment",
        "steps": _build_steps(
            front_instr="Position bat BARREL in frame",
            front_detail="Show barrel brand stamp and model number",
            sig_detail="Signature on barrel or handle — fill frame",
            detail_instr="Capture KNOB END and manufacturer burn/stamp",
            detail_detail="Louisville Slugger, Rawlings, Marucci\nModel stamp, pro stock label",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 40,
            "tag_captured": 15,
            "uv_captured": 25,
        },
    },

    "signed_ball": {
        "label": "Signed Ball",
        "icon": "🏀",
        "category": "Signed Equipment",
        "steps": _build_steps(
            front_instr="Position ball with MANUFACTURER PANEL facing up",
            front_detail="Brand logo, official markings, league authentication visible",
            sig_detail="Signature panel — autograph centered in frame",
            detail_instr="Capture OFFICIAL STAMP panel (Rawlings, Spalding, etc.)",
            detail_detail="Commissioner signature, league designation\nOfficial authentication marks",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 40,
            "tag_captured": 15,
            "uv_captured": 25,
        },
    },

    "signed_puck": {
        "label": "Signed Hockey Puck",
        "icon": "🏒",
        "category": "Signed Equipment",
        "steps": _build_steps(
            front_instr="Position puck FLAT FACE UP in frame",
            front_detail="Official NHL/team markings on face visible",
            sig_detail="Signature on flat face — fill frame with puck",
            detail_instr="Capture EDGE STAMP and side markings",
            detail_detail="Official game puck markings\nInk-Jet printing, Vegum, Sher-Wood",
        ),
        "scoring": {
            "front_captured": 20,
            "signature_captured": 40,
            "tag_captured": 15,
            "uv_captured": 25,
        },
    },

    # ── TRADING CARDS ──────────────────────────────────────────────────────
    "signed_card": {
        "label": "Signed Trading Card",
        "icon": "🃏",
        "category": "Trading Cards",
        "steps": _build_steps(
            front_instr="Position card FRONT in frame\nFull card visible",
            front_detail="Player photo, team, year all visible\nCard centered in frame",
            sig_detail="Autograph on card face — sharp and in focus",
            detail_instr="Flip card — capture CARD BACK",
            detail_detail="Card back shows set info, card number\nAuthentication marks if present",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 40,
            "tag_captured": 15,
            "uv_captured": 20,
        },
    },

    "rookie_card": {
        "label": "Rookie Card",
        "icon": "⭐",
        "category": "Trading Cards",
        "steps": _build_steps(
            front_instr="Position card FRONT in frame — full card visible",
            front_detail="Rookie designation clearly visible\nPlayer photo, team name, year",
            sig_detail="Rookie logo or RC designation — close up\nAutograph if signed",
            detail_instr="Capture CARD BACK",
            detail_detail="Set name, card number, year on back\nAuthenticity marks",
        ),
        "scoring": {
            "front_captured": 35,
            "signature_captured": 25,
            "tag_captured": 15,
            "uv_captured": 25,
        },
    },

    "graded_card": {
        "label": "Graded / Slabbed Card",
        "icon": "💎",
        "category": "Trading Cards",
        "steps": _build_steps(
            front_instr="Position slab FRONT in frame\nAvoid glare on case",
            front_detail="PSA, BGS, SGC, or other grader label visible\nGrade number clearly readable",
            sig_detail="Grader label close-up — barcode and certification number",
            detail_instr="Flip slab — capture BACK",
            detail_detail="Back of slab shows grader's cert sticker\nBarcode for verification",
        ),
        "scoring": {
            "front_captured": 30,
            "signature_captured": 35,
            "tag_captured": 25,
            "uv_captured": 10,
        },
    },

    # ── PHOTOS & PRINTS ────────────────────────────────────────────────────
    "signed_photo": {
        "label": "Signed Photo / Lithograph",
        "icon": "🖼️",
        "category": "Photos & Prints",
        "steps": _build_steps(
            front_instr="Position photo FRONT in frame\nFull image visible",
            front_detail="Event, player, or subject clearly identifiable\nDate/caption visible if present",
            sig_detail="Autograph on photo — fill frame with signature area",
            detail_instr="Capture COA, edge markings, or print info",
            detail_detail="Edition number (e.g. 23/500), photographer credit\nAuthenticity hologram or sticker",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 40,
            "tag_captured": 20,
            "uv_captured": 15,
        },
    },

    # ── GAME-USED ──────────────────────────────────────────────────────────
    "game_worn": {
        "label": "Game-Worn / Game-Used",
        "icon": "🏆",
        "category": "Game-Used",
        "steps": _build_steps(
            front_instr="Position item FRONT in frame",
            front_detail="Full item visible — show wear, use marks\nTeam and player identifiers",
            sig_detail="LOA or authentication tag — fill frame\nPlayer name, game date if present",
            detail_instr="Capture WEAR EVIDENCE (scuffs, dirt, use)",
            detail_detail="Evidence of game use adds authenticity\nClose-up of wear marks",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 30,
            "tag_captured": 30,
            "uv_captured": 15,
        },
    },

    # ── MEMORABILIA ────────────────────────────────────────────────────────
    "championship_ring": {
        "label": "Championship Ring",
        "icon": "💍",
        "category": "Memorabilia",
        "steps": _build_steps(
            front_instr="Position ring FACE UP in frame\nTeam logo and championship year visible",
            front_detail="Year, team, player name on face\nGold/jewel detail visible",
            sig_detail="Capture INNER BAND engraving\nPlayer name, number, title",
            detail_instr="Capture SIDE PROFILE of ring",
            detail_detail="Side panels often show game scores or series wins\nCarat/material markings",
        ),
        "scoring": {
            "front_captured": 30,
            "signature_captured": 30,
            "tag_captured": 20,
            "uv_captured": 20,
        },
    },

    "ticket_stub": {
        "label": "Ticket Stub / Event Pass",
        "icon": "🎟️",
        "category": "Memorabilia",
        "steps": _build_steps(
            front_instr="Position ticket FRONT in frame — full stub visible",
            front_detail="Event name, date, seat info\nTeam logos and game details",
            sig_detail="Autograph if signed — or stub perforation close-up",
            detail_instr="Capture BACK of ticket",
            detail_detail="Barcode, terms, security printing\nWatermarks or security features on reverse",
        ),
        "scoring": {
            "front_captured": 30,
            "signature_captured": 25,
            "tag_captured": 20,
            "uv_captured": 25,
        },
    },

    "program": {
        "label": "Signed Program / Yearbook",
        "icon": "📰",
        "category": "Memorabilia",
        "steps": _build_steps(
            front_instr="Position COVER in frame",
            front_detail="Event/team/year on cover visible\nFull cover centered",
            sig_detail="Signature page — close-up of autograph",
            detail_instr="Capture SPINE and publication info",
            detail_detail="Publisher, year, edition number\nOfficial team or league branding",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 40,
            "tag_captured": 15,
            "uv_captured": 20,
        },
    },

    # ── OTHER ──────────────────────────────────────────────────────────────
    "other": {
        "label": "Other Collectible",
        "icon": "📦",
        "category": "Other",
        "steps": _build_steps(
            front_instr="Position item PRIMARY FACE in frame",
            front_detail="Main identifying surface of item",
            sig_detail="Signature or authentication mark — close-up",
            detail_instr="Capture any TAGS, LABELS, or SERIAL NUMBERS",
            detail_detail="Any manufacturer, authentication, or edition info",
        ),
        "scoring": {
            "front_captured": 25,
            "signature_captured": 35,
            "tag_captured": 20,
            "uv_captured": 20,
        },
    },
}


# ---------------------------------------------------------------------------
# Grouping helpers for UI
# ---------------------------------------------------------------------------

def get_categories():
    """Return ordered list of category names."""
    seen = []
    for item in ITEM_TYPES.values():
        cat = item["category"]
        if cat not in seen:
            seen.append(cat)
    return seen


def get_items_by_category():
    """Return dict of category -> list of (type_key, item_dict)."""
    result = {}
    for key, item in ITEM_TYPES.items():
        cat = item["category"]
        if cat not in result:
            result[cat] = []
        result[cat].append((key, item))
    return result


def get_item(type_key: str) -> dict:
    """Get item type definition by key. Returns 'other' if not found."""
    return ITEM_TYPES.get(type_key, ITEM_TYPES["other"])
