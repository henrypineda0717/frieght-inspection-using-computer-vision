"""Helper utilities for processing and drawing detections on realtime video frames."""
from typing import List, Dict, Any

import cv2
import numpy as np

MODEL_COLORS = {
    "General": (255, 0, 0),
    "Damage": (0, 0, 255),
    "Id": (0, 255, 0)
}

CLASS_COLORS = {
    "Cracks": (0, 0, 255),
    "Dents": (0, 165, 255),
    "Rust & Corrosion": (0, 69, 255),
    "Holes": (0, 0, 200),
    "Dust & Powder": (0, 215, 255),
    "Oil & Stains": (0, 255, 255),
    "Nails & Fasteners": (50, 205, 50),
    "Floor Structural Damage": (255, 0, 0),
}

DEFECT_MAP = {
    "crack": "Cracks",
    "dent": "Dents",
    "rust": "Rust & Corrosion",
    "corrosion": "Rust & Corrosion",
    "hole": "Holes",
    "dust": "Dust & Powder",
    "powder": "Dust & Powder",
    "oil": "Oil & Stains",
    "stain": "Oil & Stains",
    "nail": "Nails & Fasteners",
    "fastener": "Nails & Fasteners",
    "floor": "Floor Structural Damage",
    "floordamage": "Floor Structural Damage",
    "floor hole": "Holes",
    "floor dust": "Dust & Powder",
    "floor fungal": "Biological/Fungal",
}


def get_refined_class(raw_class: str) -> str:
    """Convert a raw detection label into the refined category used for coloring."""
    raw_lower = raw_class.lower()
    for pattern, refined in DEFECT_MAP.items():
        if pattern in raw_lower:
            return refined
    return raw_class


def draw_detection(frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
    """Draw bounding boxes, masks, and labels on a frame using the shared palette."""
    if not detections:
        return frame

    annotated = frame.copy()
    overlay = annotated.copy()
    alpha = 0.4

    for det in detections:
        raw_class = det.get("class_name", "")
        refined = get_refined_class(raw_class)

        color = CLASS_COLORS.get(refined)
        if color is None:
            model_src = det.get("model_source", "").capitalize()
            color = MODEL_COLORS.get(model_src, (255, 255, 255))

        x_min, y_min = 0, 0
        if det.get("corners") and len(det["corners"]) >= 3:
            corners_np = np.array(det["corners"]).reshape(-1, 2).astype(np.int32)
            pts = corners_np.reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(annotated, [pts], True, color, 2, cv2.LINE_AA)
            x_min = int(corners_np[:, 0].min())
            y_min = int(corners_np[:, 1].min())
        else:
            x, y, w, h = det.get("bbox_x", 0), det.get("bbox_y", 0), det.get("bbox_w", 0), det.get("bbox_h", 0)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            x_min, y_min = x, y

        label = f"{raw_class} ({det.get('confidence', 0) * 100:.1f}%)"
        if det.get("severity"):
            label += f" [{det['severity']}]"
        elif det.get("container_id"):
            label += f" [{det['container_id']}]"

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_x = x_min
        label_y = y_min - 10 if y_min - 10 > th else y_min + th + 10

        cv2.rectangle(
            annotated,
            (label_x, label_y - th - 5),
            (label_x + tw + 10, label_y + 5),
            color,
            -1
        )

        cv2.putText(
            annotated,
            label,
            (label_x + 5, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

    cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)
    return annotated
