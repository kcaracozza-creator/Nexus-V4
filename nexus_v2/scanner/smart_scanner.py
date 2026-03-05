#!/usr/bin/env python3
"""
NEXUS Smart Scanner - Adaptive Repositioning for Better Detection
==================================================================
When initial scan fails to detect set icon or has low confidence,
automatically repositions arm and retries.

Flow:
1. Standard scan position → detect
2. If low confidence → closeup position → retry
3. If still failing → angled position → retry
4. If all fail → flag for manual review

Patent Pending - Kevin Caracozza
"""

import requests
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# API URLs
SNARF_URL = "http://192.168.1.219:5001"   # DANIELSON unified
VISION_URL = "http://192.168.1.219:5001"  # DANIELSON unified
BROK_URL = "http://192.168.1.219:5001"    # DANIELSON unified

# Detection thresholds
MIN_SET_CONFIDENCE = 0.7      # Below this, retry with repositioning
MIN_NAME_CONFIDENCE = 0.6     # Card name confidence threshold
MAX_RETRIES = 3               # Maximum repositioning attempts


@dataclass
class ScanPosition:
    """Arm position preset for scanning"""
    name: str
    angles: List[int]           # [base, shoulder, elbow, wrist_roll, wrist_pitch, ...]
    description: str
    use_for: List[str]          # What failures this position helps with


# Arm positions for different scan scenarios
SCAN_POSITIONS = {
    "standard": ScanPosition(
        name="standard",
        angles=[90, 90, 90, 90, 90, 0, 0, 90],
        description="Default scanning position",
        use_for=["initial"]
    ),
    "closeup_set": ScanPosition(
        name="closeup_set",
        angles=[90, 60, 120, 90, 45, 0, 0, 90],  # Lower, closer to card
        description="Closeup for set icon detection",
        use_for=["set_icon", "small_text"]
    ),
    "angled_left": ScanPosition(
        name="angled_left",
        angles=[75, 70, 110, 90, 50, 0, 0, 90],  # Angled to reduce glare
        description="Angled to reduce foil glare",
        use_for=["foil", "holo", "glare"]
    ),
    "angled_right": ScanPosition(
        name="angled_right",
        angles=[105, 70, 110, 90, 50, 0, 0, 90],  # Opposite angle
        description="Opposite angle for stubborn glare",
        use_for=["foil", "holo", "glare"]
    ),
    "overhead": ScanPosition(
        name="overhead",
        angles=[90, 45, 135, 90, 30, 0, 0, 90],  # Higher up, straight down
        description="Overhead for warped cards",
        use_for=["warped", "bent"]
    ),
}

# Retry sequence based on failure type
RETRY_SEQUENCES = {
    "set_icon": ["closeup_set", "angled_left", "angled_right"],
    "card_name": ["closeup_set", "overhead"],
    "glare": ["angled_left", "angled_right", "overhead"],
    "default": ["closeup_set", "angled_left", "overhead"],
}


@dataclass
class ScanResult:
    """Result from a scan attempt"""
    success: bool
    card_name: Optional[str] = None
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    name_confidence: float = 0.0
    set_confidence: float = 0.0
    position_used: str = "standard"
    attempts: int = 1
    image_path: Optional[str] = None
    raw_response: Optional[Dict] = None
    failure_reason: Optional[str] = None


class SmartScanner:
    """
    Smart scanner that automatically repositions arm for better detection.
    """

    def __init__(self):
        self.snarf_url = SNARF_URL
        self.vision_url = VISION_URL
        self.brok_url = BROK_URL
        self.current_position = "standard"
        self.scan_history = []  # Track what worked

    def move_arm(self, position_name: str) -> bool:
        """Move arm to named position."""
        if position_name not in SCAN_POSITIONS:
            logger.error(f"Unknown position: {position_name}")
            return False

        position = SCAN_POSITIONS[position_name]

        try:
            r = requests.post(
                f"{self.snarf_url}/api/arm/jog",
                json={"angles": position.angles},
                timeout=5
            )
            if r.status_code == 200:
                self.current_position = position_name
                logger.info(f"Moved to {position_name}: {position.description}")
                time.sleep(0.5)  # Let arm settle
                return True
        except Exception as e:
            logger.error(f"Arm move failed: {e}")

        return False

    def capture_and_detect(self) -> Dict[str, Any]:
        """Capture image and run detection."""
        try:
            # Trigger capture on Snarf
            r = requests.post(
                f"{self.snarf_url}/api/capture",
                json={"camera": "owleye", "lights": True},
                timeout=30
            )

            if r.status_code != 200:
                return {"error": "Capture failed", "status": r.status_code}

            capture_result = r.json()
            if not capture_result.get("success"):
                return {"error": "Capture unsuccessful", "result": capture_result}

            image_path = capture_result.get("image_path")

            # Send to Brok for OCR/identification
            r = requests.post(
                f"{self.brok_url}/api/identify",
                json={"image_path": image_path},
                timeout=30
            )

            if r.status_code == 200:
                result = r.json()
                result["image_path"] = image_path
                return result

            return {"error": "Identification failed", "status": r.status_code}

        except Exception as e:
            return {"error": str(e)}

    def analyze_result(self, result: Dict) -> tuple[bool, str]:
        """
        Analyze scan result to determine if retry is needed.
        Returns (needs_retry, failure_type)
        """
        if "error" in result:
            return True, "default"

        name_conf = result.get("name_confidence", result.get("confidence", 0))
        set_conf = result.get("set_confidence", 0)

        # Check set detection
        if set_conf < MIN_SET_CONFIDENCE:
            set_code = result.get("set_code", result.get("set", ""))
            if not set_code or set_code == "UNK":
                return True, "set_icon"

        # Check name detection
        if name_conf < MIN_NAME_CONFIDENCE:
            return True, "card_name"

        # Check for glare indicators (e.g., foil detected but low confidence)
        if result.get("foil") and name_conf < 0.8:
            return True, "glare"

        return False, ""

    def smart_scan(self) -> ScanResult:
        """
        Perform smart scan with automatic repositioning on failure.
        """
        attempts = 0
        last_failure = "default"
        tried_positions = ["standard"]

        # Start from standard position
        self.move_arm("standard")

        while attempts < MAX_RETRIES:
            attempts += 1
            logger.info(f"Scan attempt {attempts} from {self.current_position}")

            # Capture and detect
            result = self.capture_and_detect()

            # Check if successful
            needs_retry, failure_type = self.analyze_result(result)

            if not needs_retry:
                # Success!
                scan_result = ScanResult(
                    success=True,
                    card_name=result.get("name"),
                    set_code=result.get("set_code", result.get("set")),
                    set_name=result.get("set_name"),
                    name_confidence=result.get("name_confidence", result.get("confidence", 0)),
                    set_confidence=result.get("set_confidence", 0),
                    position_used=self.current_position,
                    attempts=attempts,
                    image_path=result.get("image_path"),
                    raw_response=result
                )

                # Track success for learning
                self.scan_history.append({
                    "position": self.current_position,
                    "success": True,
                    "card": scan_result.card_name
                })

                logger.info(f"Success! {scan_result.card_name} ({scan_result.set_code}) "
                           f"after {attempts} attempts")
                return scan_result

            # Failed - try repositioning
            last_failure = failure_type
            retry_sequence = RETRY_SEQUENCES.get(failure_type, RETRY_SEQUENCES["default"])

            # Find next position to try
            next_position = None
            for pos in retry_sequence:
                if pos not in tried_positions:
                    next_position = pos
                    break

            if next_position:
                logger.info(f"Retrying with {next_position} for {failure_type} issue")
                self.move_arm(next_position)
                tried_positions.append(next_position)
            else:
                # Exhausted all positions for this failure type
                logger.warning(f"Exhausted retry positions for {failure_type}")
                break

        # All retries failed
        scan_result = ScanResult(
            success=False,
            position_used=self.current_position,
            attempts=attempts,
            failure_reason=f"Failed after {attempts} attempts. Last issue: {last_failure}",
            raw_response=result
        )

        logger.warning(f"Scan failed after {attempts} attempts")
        return scan_result

    def scan_batch(self, count: int) -> List[ScanResult]:
        """Scan multiple cards with smart repositioning."""
        results = []
        for i in range(count):
            logger.info(f"Scanning card {i+1}/{count}")
            result = self.smart_scan()
            results.append(result)

            # Return to standard position between cards
            if self.current_position != "standard":
                self.move_arm("standard")

        return results

    def add_custom_position(self, name: str, angles: List[int],
                           description: str, use_for: List[str]):
        """Add a custom scan position (from teaching)."""
        SCAN_POSITIONS[name] = ScanPosition(
            name=name,
            angles=angles,
            description=description,
            use_for=use_for
        )
        logger.info(f"Added custom position: {name}")

    def get_position_stats(self) -> Dict[str, Dict]:
        """Get stats on which positions have been most successful."""
        stats = {}
        for entry in self.scan_history:
            pos = entry["position"]
            if pos not in stats:
                stats[pos] = {"success": 0, "total": 0}
            stats[pos]["total"] += 1
            if entry["success"]:
                stats[pos]["success"] += 1

        # Calculate success rates
        for pos in stats:
            total = stats[pos]["total"]
            if total > 0:
                stats[pos]["rate"] = stats[pos]["success"] / total
            else:
                stats[pos]["rate"] = 0

        return stats


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command line interface for smart scanner."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS Smart Scanner")
    parser.add_argument("--scan", action="store_true", help="Perform single smart scan")
    parser.add_argument("--batch", type=int, help="Scan N cards")
    parser.add_argument("--position", type=str, help="Move to position")
    parser.add_argument("--list-positions", action="store_true", help="List available positions")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    scanner = SmartScanner()

    if args.list_positions:
        print("\nAvailable scan positions:")
        for name, pos in SCAN_POSITIONS.items():
            print(f"  {name}: {pos.description}")
            print(f"    Angles: {pos.angles}")
            print(f"    Good for: {', '.join(pos.use_for)}")
        return

    if args.position:
        scanner.move_arm(args.position)
        return

    if args.batch:
        results = scanner.scan_batch(args.batch)
        success = sum(1 for r in results if r.success)
        print(f"\nBatch complete: {success}/{args.batch} successful")
        return

    if args.scan:
        result = scanner.smart_scan()
        if result.success:
            print(f"\nSuccess: {result.card_name} ({result.set_code})")
            print(f"Position: {result.position_used}, Attempts: {result.attempts}")
        else:
            print(f"\nFailed: {result.failure_reason}")
        return

    # Default: interactive mode
    print("NEXUS Smart Scanner")
    print("Commands: scan, batch N, pos NAME, list, stats, quit")

    while True:
        try:
            cmd = input("> ").strip().lower()
            if not cmd:
                continue

            if cmd == "quit" or cmd == "q":
                break
            elif cmd == "scan" or cmd == "s":
                result = scanner.smart_scan()
                if result.success:
                    print(f"  {result.card_name} ({result.set_code}) - {result.attempts} attempts")
                else:
                    print(f"  Failed: {result.failure_reason}")
            elif cmd.startswith("batch "):
                n = int(cmd.split()[1])
                results = scanner.scan_batch(n)
                success = sum(1 for r in results if r.success)
                print(f"  {success}/{n} successful")
            elif cmd.startswith("pos "):
                pos = cmd.split()[1]
                scanner.move_arm(pos)
            elif cmd == "list":
                for name in SCAN_POSITIONS:
                    print(f"  {name}")
            elif cmd == "stats":
                stats = scanner.get_position_stats()
                for pos, s in stats.items():
                    print(f"  {pos}: {s['success']}/{s['total']} ({s['rate']*100:.0f}%)")
            else:
                print("Unknown command")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    print("Goodbye!")


if __name__ == "__main__":
    main()
