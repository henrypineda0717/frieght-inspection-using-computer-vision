"""
Damage Classifier Service

This module provides severity classification for damage detections based on
confidence scores from the damage detection model.
"""

from typing import Optional


class DamageClassifier:
    """
    Classifies damage severity based on confidence scores.
    
    Severity levels are determined by confidence thresholds:
    - high: confidence > 0.8
    - medium: 0.5 <= confidence <= 0.8
    - low: confidence < 0.5
    
    Only applies to detections from the damage model.
    """
    
    SEVERITY_THRESHOLDS = {
        'high': 0.8,
        'medium': 0.5,
        'low': 0.0
    }
    
    def classify_severity(self, confidence: float, model_source: str = "damage") -> Optional[str]:
        """
        Classify damage severity based on confidence score.
        
        Args:
            confidence: Detection confidence score (0.0 to 1.0)
            model_source: Source model that produced the detection
            
        Returns:
            Severity level ('high', 'medium', or 'low') for damage detections,
            None for non-damage detections
            
        Examples:
            >>> classifier = DamageClassifier()
            >>> classifier.classify_severity(0.85, "damage")
            'high'
            >>> classifier.classify_severity(0.65, "damage")
            'medium'
            >>> classifier.classify_severity(0.3, "damage")
            'low'
            >>> classifier.classify_severity(0.9, "general")
            None
        """
        # Return None for non-damage detections (Requirements 4.5)
        if model_source != "rt-detr":
            return None
        
        # Classify based on thresholds (Requirements 4.1, 4.2, 4.3, 4.4)
        if confidence > self.SEVERITY_THRESHOLDS['high']:
            return 'high'
        elif confidence >= self.SEVERITY_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'
