"""
Result Aggregator - enriches raw detections with OCR and severity data
"""
from typing import List, Dict, Any, Optional
import numpy as np

from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResultAggregator:
    """
    Combines detections from all models and enriches them with metadata.
    
    This class processes raw detections from the DetectionCoordinator and:
    - Applies OCR to ID model detections to extract container IDs
    - Applies severity classification to damage model detections
    - Selects the best container ID when multiple are detected
    """
    
    def __init__(self, ocr_processor: OCRProcessor, damage_classifier: DamageClassifier):
        """
        Initialize ResultAggregator with dependencies.
        
        Args:
            ocr_processor: OCRProcessor instance for container ID extraction
            damage_classifier: DamageClassifier instance for severity classification
        """
        self.ocr_processor = ocr_processor
        self.damage_classifier = damage_classifier
        logger.info("ResultAggregator initialized")
    
    def aggregate_detections(
        self, 
        image: np.ndarray, 
        raw_detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich detections with OCR and severity data.
        
        Processes each detection based on its model_source:
        - ID detections: Extract container ID via OCR
        - Damage detections: Classify severity based on confidence
        - General detections: Pass through unchanged
        
        Args:
            image: Original image as numpy array (for OCR cropping)
            raw_detections: List of raw detection dictionaries from DetectionCoordinator
            
        Returns:
            List of enriched detection dictionaries with additional fields:
                - container_id: For ID detections (or None)
                - severity: For damage detections (or None)
        """
        enriched_detections = []
        
        logger.info(f"Aggregating {len(raw_detections)} detections")
        
        # Count detections by model source
        id_count = sum(1 for d in raw_detections if d['model_source'] == 'id')
        damage_count = sum(1 for d in raw_detections if d['model_source'] == 'Damage')
        general_count = sum(1 for d in raw_detections if d['model_source'] == 'General')
        
        logger.info(f"   ID detections: {id_count}, Damage: {damage_count}, General: {general_count}")
        
        for detection in raw_detections:
            enriched = detection.copy()
            #print(enriched)
            
            # Initialize optional fields
            enriched['severity'] = None
            
            model_source = detection['model_source']
            
            # Apply severity classification to damage detections
            if model_source == 'Damage':
                confidence = detection['confidence']
                severity = self.damage_classifier.classify_severity(confidence, model_source)
                enriched['severity'] = severity
                logger.debug(f"Damage detection enriched with severity: {severity}")
            
            enriched_detections.append(enriched)
        
        logger.info(f"[AGGREGATOR] Enriched {len(enriched_detections)} detections")
        return enriched_detections
    
    def _select_best_container_id(self, id_detections: List[Dict[str, Any]]) -> Optional[str]:
        """
        Select highest confidence container ID from multiple detections.
        
        When multiple container IDs are detected in a single frame, this method
        selects the one with the highest confidence score. Only considers
        detections with valid container IDs (not "UNKNOWN").
        
        Args:
            id_detections: List of ID detection dictionaries with container_id field
            
        Returns:
            Best container ID string, or None if no valid IDs found
        """
        # Filter for valid container IDs (not UNKNOWN)
        valid_detections = [
            d for d in id_detections 
            if d.get('container_id') and d['container_id'] != 'UNKNOWN'
        ]
        
        if not valid_detections:
            logger.debug("No valid container IDs found")
            return None
        
        # Sort by confidence (descending) and select highest
        best_detection = max(valid_detections, key=lambda d: d['confidence'])
        best_container_id = best_detection['container_id']
        
        logger.info(f"Selected best container ID: {best_container_id} "
                   f"(confidence: {best_detection['confidence']:.2f})")
        
        return best_container_id
