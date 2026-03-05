#!/usr/bin/env python3
"""
NEXUS Card Cropper
==================
Lightbox on. Dark rectangle. Four corners. Crop. Keep it pushing.

Input: Raw camera image (card on bright lightbox)
Output: Clean cropped card image, perspective-corrected

Then → art recognition → FAISS embedding

No bullshit. No stubs. No print("Complete!").
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List


class CardCropper:
    """
    Finds a dark card on a bright lightbox background.
    Crops it. Straightens it. Done.
    """

    def __init__(self, target_width: int = 745, target_height: int = 1040):
        """
        Standard card ratio ~2.5 x 3.5 inches
        Default output: 745 x 1040 pixels (high res for FAISS embedding)
        """
        self.target_width = target_width
        self.target_height = target_height

    def crop(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Main entry point. Give it a raw frame, get back a cropped card.
        Returns None if no card found.

        Args:
            image: BGR image from camera (numpy array)

        Returns:
            Cropped, perspective-corrected card image or None
        """
        corners = self._find_card_corners(image)
        if corners is None:
            return None

        cropped = self._perspective_transform(image, corners)
        return cropped

    def crop_from_file(self, image_path: str, output_path: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Convenience method - read file, crop, optionally save.
        """
        image = cv2.imread(image_path)
        if image is None:
            print(f"[CardCropper] Can't read: {image_path}")
            return None

        cropped = self.crop(image)

        if cropped is not None and output_path:
            cv2.imwrite(output_path, cropped)
            print(f"[CardCropper] Saved: {output_path}")

        return cropped

    def _find_card_corners(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Lightbox = bright. Card = dark rectangle.
        Find the dark rectangle. Return four corners.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # The lightbox is bright, the card is dark.
        # Threshold: anything significantly darker than the lightbox = card
        # Use adaptive threshold to handle uneven lighting
        # Also try Otsu's method and take the better result

        # Method 1: Otsu's threshold (inverted - dark objects become white)
        _, thresh_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Method 2: Adaptive threshold for uneven lightbox illumination
        thresh_adaptive = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 51, 10
        )

        # Try both, return whichever finds a better card
        corners_otsu = self._find_rectangle(thresh_otsu, image.shape)
        corners_adaptive = self._find_rectangle(thresh_adaptive, image.shape)

        # Score both results - prefer the one with better rectangularity
        if corners_otsu is not None and corners_adaptive is not None:
            score_otsu = self._rectangle_score(corners_otsu, image.shape)
            score_adaptive = self._rectangle_score(corners_adaptive, image.shape)
            return corners_otsu if score_otsu >= score_adaptive else corners_adaptive

        return corners_otsu if corners_otsu is not None else corners_adaptive

    def _find_rectangle(self, thresh: np.ndarray, image_shape: tuple) -> Optional[np.ndarray]:
        """
        Find the largest rectangular contour in a thresholded image.
        """
        img_h, img_w = image_shape[:2]
        img_area = img_h * img_w

        # Clean up threshold with morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Sort by area, largest first
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:10]:  # Check top 10 candidates
            area = cv2.contourArea(contour)

            # Card should be between 5% and 90% of image area
            if area < img_area * 0.05 or area > img_area * 0.90:
                continue

            # Approximate the contour to a polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

            # We want exactly 4 corners (rectangle)
            if len(approx) == 4:
                return self._order_corners(approx.reshape(4, 2))

            # If we got close but not exactly 4, try with looser epsilon
            if len(approx) >= 4 and len(approx) <= 6:
                approx = cv2.approxPolyDP(contour, 0.05 * peri, True)
                if len(approx) == 4:
                    return self._order_corners(approx.reshape(4, 2))

            # Last resort: minimum area bounding rectangle
            if len(approx) > 4:
                rect = cv2.minAreaRect(contour)
                box = cv2.boxPoints(rect)
                box = np.intp(box)

                # Verify the bounding rect is reasonably card-shaped
                w, h = rect[1]
                if w > 0 and h > 0:
                    ratio = max(w, h) / min(w, h)
                    # Standard card ratio is ~1.4 (3.5/2.5)
                    # Allow some tolerance: 1.1 to 1.8
                    if 1.1 <= ratio <= 1.8:
                        return self._order_corners(box.astype(np.float32))

        return None

    def _order_corners(self, corners: np.ndarray) -> np.ndarray:
        """
        Order corners: top-left, top-right, bottom-right, bottom-left.
        Consistent ordering is critical for perspective transform.
        """
        corners = corners.astype(np.float32)

        # Sort by sum (x+y): smallest = top-left, largest = bottom-right
        s = corners.sum(axis=1)
        tl = corners[np.argmin(s)]
        br = corners[np.argmax(s)]

        # Sort by difference (y-x): smallest = top-right, largest = bottom-left
        d = np.diff(corners, axis=1).flatten()
        tr = corners[np.argmin(d)]
        bl = corners[np.argmax(d)]

        return np.array([tl, tr, br, bl], dtype=np.float32)

    def _rectangle_score(self, corners: np.ndarray, image_shape: tuple) -> float:
        """
        Score how "card-like" a set of corners is.
        Higher = more card-like.
        """
        # Check aspect ratio
        w_top = np.linalg.norm(corners[1] - corners[0])
        w_bottom = np.linalg.norm(corners[2] - corners[3])
        h_left = np.linalg.norm(corners[3] - corners[0])
        h_right = np.linalg.norm(corners[2] - corners[1])

        avg_w = (w_top + w_bottom) / 2
        avg_h = (h_left + h_right) / 2

        if avg_w == 0 or avg_h == 0:
            return 0.0

        ratio = max(avg_w, avg_h) / min(avg_w, avg_h)

        # Ideal card ratio ~1.4
        ratio_score = 1.0 - abs(ratio - 1.4) / 1.4

        # Check parallelism (opposite sides should be similar length)
        w_parallel = 1.0 - abs(w_top - w_bottom) / max(w_top, w_bottom)
        h_parallel = 1.0 - abs(h_left - h_right) / max(h_left, h_right)

        # Check right angles
        angle_score = self._check_right_angles(corners)

        # Size relative to image (card should be a decent portion)
        area = cv2.contourArea(corners)
        img_area = image_shape[0] * image_shape[1]
        size_score = min(area / img_area / 0.3, 1.0)  # Ideal: card is ~30% of image

        return (ratio_score * 0.3 + w_parallel * 0.2 + h_parallel * 0.2 +
                angle_score * 0.2 + size_score * 0.1)

    def _check_right_angles(self, corners: np.ndarray) -> float:
        """Check how close to 90 degrees the corners are."""
        scores = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            p3 = corners[(i - 1) % 4]

            v1 = p2 - p1
            v2 = p3 - p1

            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                scores.append(0)
                continue

            cos_angle = np.dot(v1, v2) / (norm1 * norm2)
            cos_angle = np.clip(cos_angle, -1, 1)
            angle = np.degrees(np.arccos(cos_angle))

            # Perfect right angle = 90 degrees
            scores.append(1.0 - abs(angle - 90) / 90)

        return np.mean(scores)

    def _perspective_transform(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        Warp the card to a flat, straight rectangle.
        Fixes any angle or perspective distortion.
        """
        # Determine if card is portrait or landscape
        w_top = np.linalg.norm(corners[1] - corners[0])
        h_left = np.linalg.norm(corners[3] - corners[0])

        if w_top > h_left:
            # Card is landscape - rotate output to portrait
            dst_w = self.target_height
            dst_h = self.target_width
        else:
            dst_w = self.target_width
            dst_h = self.target_height

        # Destination corners
        dst = np.array([
            [0, 0],
            [dst_w - 1, 0],
            [dst_w - 1, dst_h - 1],
            [0, dst_h - 1]
        ], dtype=np.float32)

        # Compute perspective transform matrix
        matrix = cv2.getPerspectiveTransform(corners, dst)

        # Warp
        warped = cv2.warpPerspective(image, matrix, (dst_w, dst_h),
                                      flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_REPLICATE)

        # If it came out landscape, rotate to portrait
        if w_top > h_left:
            warped = cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return warped


class CardPipeline:
    """
    Full pipeline: Crop → Prep → Ready for FAISS embedding

    Usage:
        pipeline = CardPipeline()
        result = pipeline.process("raw_scan.jpg")
        if result is not None:
            cropped_image, embedding_ready = result
            # Send embedding_ready to FAISS
    """

    def __init__(self,
                 crop_width: int = 745,
                 crop_height: int = 1040,
                 embedding_size: int = 224):
        """
        Args:
            crop_width: Cropped card width (high res for storage)
            crop_height: Cropped card height
            embedding_size: Size for FAISS input (typically 224x224 for most models)
        """
        self.cropper = CardCropper(crop_width, crop_height)
        self.embedding_size = embedding_size

    def process(self, image_input) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Full pipeline.

        Args:
            image_input: filepath string OR numpy array (BGR)

        Returns:
            (cropped_full_res, embedding_ready) or None if no card found
            - cropped_full_res: 745x1040 high-res crop for storage/display
            - embedding_ready: 224x224 RGB normalized for FAISS/model input
        """
        # Load if filepath
        if isinstance(image_input, str):
            image = cv2.imread(image_input)
            if image is None:
                print(f"[CardPipeline] Can't read: {image_input}")
                return None
        else:
            image = image_input

        # Crop the card
        cropped = self.cropper.crop(image)
        if cropped is None:
            print("[CardPipeline] No card detected")
            return None

        # Prepare for embedding
        embedding_ready = self._prep_for_embedding(cropped)

        return cropped, embedding_ready

    def process_and_save(self, image_path: str, output_dir: str) -> Optional[dict]:
        """
        Process and save both versions.

        Returns dict with paths and metadata, or None.
        """
        result = self.process(image_path)
        if result is None:
            return None

        cropped, embedding_ready = result
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(image_path).stem

        # Save high-res crop
        crop_path = output_dir / f"{stem}_cropped.png"
        cv2.imwrite(str(crop_path), cropped)

        # Save embedding-ready version
        embed_path = output_dir / f"{stem}_embed.png"
        # Convert back from normalized float to uint8 for saving
        embed_save = (embedding_ready * 255).astype(np.uint8)
        embed_save = cv2.cvtColor(embed_save, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(embed_path), embed_save)

        return {
            'source': image_path,
            'cropped_path': str(crop_path),
            'embedding_path': str(embed_path),
            'crop_size': cropped.shape[:2],
            'embedding_size': embedding_ready.shape[:2],
        }

    def _prep_for_embedding(self, cropped: np.ndarray) -> np.ndarray:
        """
        Prepare cropped card for FAISS embedding model.
        - Resize to model input size (224x224)
        - Convert BGR to RGB
        - Normalize to 0-1 float
        """
        # Resize
        resized = cv2.resize(cropped, (self.embedding_size, self.embedding_size),
                             interpolation=cv2.INTER_AREA)

        # BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize to 0-1
        normalized = rgb.astype(np.float32) / 255.0

        return normalized


# =============================================================================
# BATCH PROCESSING - for scanning through folders of images
# =============================================================================

def batch_crop(input_dir: str, output_dir: str, extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')) -> dict:
    """
    Batch process a folder of card images.

    Args:
        input_dir: Folder of raw scans
        output_dir: Where to save cropped cards

    Returns:
        Stats dict
    """
    pipeline = CardPipeline()
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = [f for f in input_path.iterdir() if f.suffix.lower() in extensions]

    stats = {'total': len(files), 'success': 0, 'failed': 0, 'results': []}

    for f in files:
        result = pipeline.process_and_save(str(f), str(output_path))
        if result:
            stats['success'] += 1
            stats['results'].append(result)
        else:
            stats['failed'] += 1
            print(f"[FAILED] {f.name}")

    print(f"\n[BatchCrop] Done: {stats['success']}/{stats['total']} cards cropped")
    if stats['failed']:
        print(f"[BatchCrop] Failed: {stats['failed']} images")

    return stats


# =============================================================================
# TEST
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python card_cropper.py <image_path>              # Crop single card")
        print("  python card_cropper.py <image_path> <output_path> # Crop and save")
        print("  python card_cropper.py --batch <input_dir> <output_dir>  # Batch process")
        sys.exit(0)

    if sys.argv[1] == '--batch':
        if len(sys.argv) < 4:
            print("Usage: python card_cropper.py --batch <input_dir> <output_dir>")
            sys.exit(1)
        stats = batch_crop(sys.argv[2], sys.argv[3])
        print(f"\nResults: {stats['success']} cropped, {stats['failed']} failed")
    else:
        image_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None

        pipeline = CardPipeline()

        if output_path:
            result = pipeline.process_and_save(image_path, str(Path(output_path).parent))
            if result:
                print(f"Cropped: {result['cropped_path']}")
                print(f"Embedding ready: {result['embedding_path']}")
            else:
                print("No card detected")
        else:
            result = pipeline.process(image_path)
            if result:
                cropped, embedding = result
                print(f"Card found: {cropped.shape[1]}x{cropped.shape[0]}")
                print(f"Embedding ready: {embedding.shape}")
                # Display if possible
                cv2.imwrite("cropped_test.png", cropped)
                print("Saved: cropped_test.png")
            else:
                print("No card detected")
