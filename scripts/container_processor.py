from ultralytics import YOLO
import cv2
import numpy as np

class ContainerProcessor:
    def __init__(self, model_path, conf=0.25):
        self.model = YOLO(model_path)
        self.conf = conf

    @staticmethod
    def resize_with_ratio(img, target_width=None, target_height=None):
        h, w = img.shape[:2]
        if target_height:
            ratio = target_height / float(h)
            dim = (int(w * ratio), target_height)
        else:
            ratio = target_width / float(w)
            dim = (target_width, int(h * ratio))
        return cv2.resize(img, dim, interpolation=cv2.INTER_AREA)

    @staticmethod
    def order_points(pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def get_container_corners(self, image, filter_method='largest'):
        """
        Returns ordered corners for detected containers (class ID 1).
        filter_method: 'largest'  – keep only the largest mask (by area)
                       'no_border' – keep only masks that do not touch the image border
                       'all'       – keep all (no filtering)
        """
        results = self.model.predict(source=image, conf=self.conf, save=False)
        if len(results) == 0:
            return []
        res = results[0]
        if res.masks is None or res.boxes is None:
            return []
        classes = res.boxes.cls.cpu().numpy().astype(int)
        masks = res.masks.data.cpu().numpy()
        img_h, img_w = image.shape[:2]
        container_indices = np.where(classes == 1)[0]
        all_corners = []
        mask_areas = []

        for idx in container_indices:
            mask = masks[idx]
            mask_resized = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
            binary_mask = (mask_resized > 0.5).astype(np.uint8)

            if filter_method == 'no_border':
                top_row = binary_mask[0, :].any()
                bottom_row = binary_mask[-1, :].any()
                left_col = binary_mask[:, 0].any()
                right_col = binary_mask[:, -1].any()
                if top_row or bottom_row or left_col or right_col:
                    continue

            mask_255 = (binary_mask * 255).astype(np.uint8)
            contours, _ = cv2.findContours(mask_255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            mask_areas.append(area)

            perimeter = cv2.arcLength(largest_contour, True)
            epsilon = 0.02 * perimeter
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            if len(approx) == 4:
                corners = approx.reshape(4, 2)
            else:
                hull = cv2.convexHull(largest_contour)
                approx = cv2.approxPolyDP(hull, epsilon, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2)
                else:
                    rect = cv2.minAreaRect(largest_contour)
                    corners = cv2.boxPoints(rect)
                    corners = np.int0(corners)
            corners = corners.astype(np.float32)
            ordered_corners = self.order_points(corners)
            all_corners.append(ordered_corners)

        if filter_method == 'largest' and all_corners:
            max_idx = np.argmax(mask_areas)
            return [all_corners[max_idx]]
        else:
            return all_corners

    def process_image(self, image_path, resize_width=None, return_all=False, filter_method='largest'):

        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Could not load image: {image_path}")
        orig_h, orig_w = img.shape[:2]

        # Resize for inference if requested
        if resize_width:
            img_resized = self.resize_with_ratio(img, target_width=resize_width)
            scale = resize_width / orig_w
        else:
            img_resized = img
            scale = 1.0

        corners_list = self.get_container_corners(img_resized, filter_method=filter_method)

        # Scale corners back to original image coordinates
        if scale != 1.0:
            corners_list = [corners / scale for corners in corners_list]

        if return_all:
            return img, corners_list
        else:
            return img, corners_list[0] if corners_list else None