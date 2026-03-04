import re
import cv2
import numpy as np
from PIL import Image
import pillow_heif
from container_processor import ContainerProcessor
from backend.app.services.ocr_engine import OCREngine

class OCRProcessor:
    def __init__(self, detection_model_path, conf=0.5, verbose=False):
        self.detector = ContainerProcessor(detection_model_path, conf=conf)
        self.ocr = OCREngine()
        self.verbose = verbose

    def _load_image(self, image_path):
        """Loads standard formats (JPG/PNG) and HEIC into BGR OpenCV format."""
        try:
            if image_path.lower().endswith('.heic'):
                heif_file = pillow_heif.read_heif(image_path)
                image = Image.frombytes(
                    heif_file.mode, 
                    heif_file.size, 
                    heif_file.data,
                    "raw",
                )
                # Convert RGB (PIL) to BGR (OpenCV)
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                # Standard OpenCV load
                return cv2.imread(image_path)
        except Exception as e:
            if self.verbose:
                print(f"Error loading image {image_path}: {e}")
            return None

    def _crop_rotated(self, image, corners):
        """Standard perspective transform to get a flat crop of the container ID."""
        rect = np.zeros((4, 2), dtype="float32")
        s = corners.sum(axis=1)
        rect[0] = corners[np.argmin(s)]
        rect[2] = corners[np.argmax(s)]
        diff = np.diff(corners, axis=1)
        rect[1] = corners[np.argmin(diff)]
        rect[3] = corners[np.argmax(diff)]

        (tl, tr, br, bl) = rect
        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (max_width, max_height))

    def _parse_ocr_results(self, ocr_text_list):
        combined = ''.join(ocr_text_list).replace(' ', '')
        combined = re.sub(r'[^A-Za-z0-9]', '', combined).upper()
        
        match = re.search(r'([A-Z]{4})(\d{7})', combined)
        if match:
            container_id = match.group(1) + match.group(2)
        else:
            match = re.search(r'([A-Z]{4})(\d{6})', combined)
            container_id = match.group(1) + match.group(2) if match else None

        iso_type = None
        for item in ocr_text_list:
            item_clean = re.sub(r'[^A-Za-z0-9]', '', item).upper()
            if re.match(r'^\d{2}[A-Z]\d$', item_clean):
                iso_type = item_clean
                break
        return container_id, iso_type

    def _validate_check_digit(self, container_id):
        if not container_id or len(container_id) != 11:
            return False
        char_map = {
            'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17, 'H': 18, 'I': 19, 'J': 20,
            'K': 21, 'L': 23, 'M': 24, 'N': 25, 'O': 26, 'P': 27, 'Q': 28, 'R': 29, 'S': 30, 'T': 31,
            'U': 32, 'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38
        }
        try:
            total = 0
            for i in range(10):
                char = container_id[i].upper()
                val = int(char) if char.isdigit() else char_map[char]
                total += val * (2**i)
            calculated = (total % 11) % 10
            return calculated == int(container_id[10])
        except: return False

    def process_image(self, image_path, resize_width=640, return_all=False):
        # 1. Load original image (handles HEIC)
        img = self._load_image(image_path)
        if img is None:
            return {'success': False, 'error': 'Load failed'}

        # 2. Get detections relative to original image size
        _, corners_list = self.detector.process_image(
            img, resize_width=resize_width, return_all=True
        )

        annotated_img = img.copy()
        
        # Scaling UI elements based on image resolution
        h, w = img.shape[:2]
        font_scale = max(0.8, w / 1500)
        thickness = max(2, int(w / 400))
        
        containers = []
        if corners_list:
            for corners in corners_list:
                pts = corners.astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(annotated_img, [pts], True, (0, 255, 0), thickness)

                cropped = self._crop_rotated(img, corners)
                ocr_results = self.ocr.predict(cropped)
                ocr_texts = ocr_results[0].get('rec_texts', []) if ocr_results else []

                container_id, iso_type = self._parse_ocr_results(ocr_texts)

                if container_id:
                    # Draw visual label
                    x_min, y_min = pts[:, :, 0].min(), pts[:, :, 1].min()
                    label = f"{container_id} | {iso_type if iso_type else ''}"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                    
                    text_y = max(y_min - 10, th + 20)
                    cv2.rectangle(annotated_img, (x_min, int(text_y - th - 15)), 
                                 (x_min + tw, int(text_y + 10)), (0, 255, 0), -1)
                    cv2.putText(annotated_img, label, (x_min, int(text_y)), 
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)

                containers.append({
                    'container_id': container_id,
                    'iso_type': iso_type,
                    'check_digit_valid': self._validate_check_digit(container_id) if container_id and len(container_id)==11 else None,
                    'cropped': cropped
                })

        if not return_all: containers = containers[:1]
        
        return {
            'success': len(containers) > 0,
            'containers': containers,
            'image': img,
            'annotated_image': annotated_img
        }