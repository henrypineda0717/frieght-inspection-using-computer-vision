import re
import cv2
import time
import numpy as np
from PIL import Image
import pillow_heif
from typing import Optional, Dict, Any, List

from app.services.model_manager import ModelManager
from app.utils.logger import get_logger
from app.utils.metrics import metrics_collector

logger = get_logger(__name__)

class OCRProcessor:
    """
    OCR Processor using PaddleOCR via ModelManager.
    Handles HEIC, perspective transforms, and ISO 6346 validation.
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        logger.info("OCRProcessor initialized")

    # ----------------------------------------------------------------------
    # Image loading and transformation
    # ----------------------------------------------------------------------
    def _load_image(self, image_path: str) -> Optional[np.ndarray]:
        """Load image (JPG, PNG, HEIC) into BGR OpenCV format."""
        try:
            if image_path.lower().endswith('.heic'):
                pillow_heif.register_heif_opener()
                image = Image.open(image_path)
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            return cv2.imread(image_path)
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None

    def _crop_rotated(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        Apply perspective transform to obtain a fronto-parallel crop of the region
        defined by four corners.
        """
        # Order corners: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        s = corners.sum(axis=1)
        rect[0] = corners[np.argmin(s)]  # top-left
        rect[2] = corners[np.argmax(s)]  # bottom-right
        diff = np.diff(corners, axis=1)
        rect[1] = corners[np.argmin(diff)]  # top-right
        rect[3] = corners[np.argmax(diff)]  # bottom-left

        tl, tr, br, bl = rect
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_width = max(int(width_a), int(width_b))

        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_height = max(int(height_a), int(height_b))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (max_width, max_height))

    # ----------------------------------------------------------------------
    # ISO 6346 check digit logic (unified)
    # ----------------------------------------------------------------------
    @staticmethod
    def _char_value(ch: str) -> int:
        """Convert ISO 6346 character to its numeric value."""
        if ch.isdigit():
            return int(ch)
        # Mapping per ISO 6346 (skipping 11,22,33)
        mapping = {
            'A':10, 'B':12, 'C':13, 'D':14, 'E':15, 'F':16, 'G':17, 'H':18, 'I':19,
            'J':20, 'K':21, 'L':23, 'M':24, 'N':25, 'O':26, 'P':27, 'Q':28, 'R':29,
            'S':30, 'T':31, 'U':32, 'V':34, 'W':35, 'X':36, 'Y':37, 'Z':38
        }
        return mapping.get(ch.upper(), 0)

    def _compute_check_digit_from_parts(self, owner_category: str, serial_number: str) -> int:
        """
        Compute ISO 6346 check digit from owner code (4 letters) and serial (6 digits).
        """
        if len(owner_category) != 4 or len(serial_number) != 6:
            raise ValueError("owner_category must be 4 chars, serial_number 6 digits")
        combined = owner_category + serial_number
        total = sum(self._char_value(ch) * (2 ** i) for i, ch in enumerate(combined))
        remainder = total % 11
        return remainder if remainder < 10 else 0

    def compute_check_digit(self, owner_category: str, serial_number: str) -> int:
        """Public wrapper for check digit computation."""
        return self._compute_check_digit_from_parts(owner_category, serial_number)

    def _validate_check_digit(self, container_id: str) -> bool:
        """Validate an 11-character container ID using ISO 6346 check digit."""
        if len(container_id) != 11:
            return False
        owner = container_id[:4]
        serial = container_id[4:10]
        try:
            expected = self._compute_check_digit_from_parts(owner, serial)
            return expected == int(container_id[10])
        except Exception:
            return False

    # ----------------------------------------------------------------------
    # OCR result parsing
    # ----------------------------------------------------------------------
    def _parse_ocr_results(self, ocr_text_list: List[str]) -> tuple[Optional[str], Optional[str]]:
        """
        Extract container ID and ISO type from OCR text lines.
        Returns (container_id, iso_type) where container_id may be None.
        """
        four_letter_tokens = []
        six_digit_tokens = []
        iso_type = None

        # First pass: gather candidate tokens
        for line in ocr_text_list:
            clean = re.sub(r'[^A-Za-z0-9 ]', '', line).upper()
            tokens = clean.split()
            for token in tokens:
                if re.fullmatch(r'[A-Z]{4}', token):
                    four_letter_tokens.append(token)
                elif re.fullmatch(r'\d{6}', token):
                    six_digit_tokens.append(token)

        # Second pass: look for ISO type (stop at first match)
        for line in ocr_text_list:
            clean = re.sub(r'[^A-Za-z0-9 ]', '', line).upper()
            tokens = clean.split()
            for token in tokens:
                if re.fullmatch(r'\d{2}[A-Z]\d', token) or re.fullmatch(r'\d{4}', token):
                    iso_type = token
                    break
            if iso_type:
                break

        # Build container ID if we have both parts
        container_id = None
        if four_letter_tokens and six_digit_tokens:
            try:
                owner = four_letter_tokens[0]
                serial = six_digit_tokens[0]
                check = self._compute_check_digit_from_parts(owner, serial)
                container_id = f"{owner}{serial}{check}"
            except ValueError:
                pass   # fallback: container_id remains None

        return container_id, iso_type

    def extract_id_from_crop(self, cropped_img: np.ndarray) -> Dict[str, Any]:
        """
        Run OCR on a cropped image and extract container information.
        Returns a dict with keys: container_id, iso_type, valid, confidence_info.
        """
        start_time = time.time()
        success = False
        result = {
            "container_id": "UNKNOWN",
            "iso_type": None,
            "valid": False,
            "confidence_info": []
        }

        try:
            ocr_engine = self.model_manager.get_ocr_engine()
            if ocr_engine is None:
                logger.error("No OCR engine available")
                return result

            # PaddleOCR returns list of results; each element contains 'rec_texts' and 'rec_scores'
            ocr_results = ocr_engine.predict(cropped_img)
            if ocr_results:
                ocr_texts = ocr_results[0].get('rec_texts', []) 
                print('ocr texts', ocr_texts)
            else:
                ocr_texts = []
            logger.debug(f"OCR texts: {ocr_texts}")
            

            container_id, iso_type = self._parse_ocr_results(ocr_texts)
            valid = self._validate_check_digit(container_id) if container_id else False

            result = {
                "container_id": container_id or "UNKNOWN",
                "iso_type": iso_type,
                "valid": valid,
                "confidence_info": ocr_texts
            }
            success = True
            return result

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return result
        finally:
            metrics_collector.record_ocr_result(success, time.time() - start_time)