"""
Unit tests for DamageClassifier component
Tests severity classification logic and threshold boundaries
"""
import pytest

from app.services.damage_classifier import DamageClassifier


class TestDamageClassifier:
    """Unit tests for DamageClassifier class"""
    
    def setup_method(self):
        """Create a fresh classifier instance for each test"""
        self.classifier = DamageClassifier()
    
    def test_severity_thresholds_constants(self):
        """Test that severity threshold constants are defined correctly"""
        assert DamageClassifier.SEVERITY_THRESHOLDS['high'] == 0.8
        assert DamageClassifier.SEVERITY_THRESHOLDS['medium'] == 0.5
        assert DamageClassifier.SEVERITY_THRESHOLDS['low'] == 0.0
    
    def test_high_severity_above_threshold(self):
        """Test high severity classification for confidence > 0.8"""
        # Test values above high threshold
        assert self.classifier.classify_severity(0.81, "damage") == 'high'
        assert self.classifier.classify_severity(0.9, "damage") == 'high'
        assert self.classifier.classify_severity(0.95, "damage") == 'high'
        assert self.classifier.classify_severity(1.0, "damage") == 'high'
    
    def test_high_severity_at_boundary(self):
        """Test that confidence exactly at 0.8 is not classified as high"""
        # At boundary (0.8) should be medium, not high (> 0.8 for high)
        assert self.classifier.classify_severity(0.8, "damage") == 'medium'
    
    def test_medium_severity_in_range(self):
        """Test medium severity classification for 0.5 <= confidence <= 0.8"""
        # Test values in medium range
        assert self.classifier.classify_severity(0.5, "damage") == 'medium'
        assert self.classifier.classify_severity(0.6, "damage") == 'medium'
        assert self.classifier.classify_severity(0.7, "damage") == 'medium'
        assert self.classifier.classify_severity(0.8, "damage") == 'medium'
    
    def test_low_severity_below_threshold(self):
        """Test low severity classification for confidence < 0.5"""
        # Test values below medium threshold
        assert self.classifier.classify_severity(0.0, "damage") == 'low'
        assert self.classifier.classify_severity(0.1, "damage") == 'low'
        assert self.classifier.classify_severity(0.3, "damage") == 'low'
        assert self.classifier.classify_severity(0.49, "damage") == 'low'
    
    def test_null_severity_for_general_model(self):
        """Test that non-damage detections return None"""
        # General model detections should return None
        assert self.classifier.classify_severity(0.9, "general") is None
        assert self.classifier.classify_severity(0.5, "general") is None
        assert self.classifier.classify_severity(0.1, "general") is None
    
    def test_null_severity_for_id_model(self):
        """Test that ID model detections return None"""
        # ID model detections should return None
        assert self.classifier.classify_severity(0.9, "id") is None
        assert self.classifier.classify_severity(0.5, "id") is None
        assert self.classifier.classify_severity(0.1, "id") is None
    
    def test_null_severity_for_unknown_model(self):
        """Test that unknown model sources return None"""
        # Unknown model sources should return None
        assert self.classifier.classify_severity(0.9, "unknown") is None
        assert self.classifier.classify_severity(0.9, "") is None
        assert self.classifier.classify_severity(0.9, "other") is None
    
    def test_default_model_source_parameter(self):
        """Test that model_source defaults to 'damage' when not specified"""
        # When model_source is not provided, it should default to "damage"
        assert self.classifier.classify_severity(0.9) == 'high'
        assert self.classifier.classify_severity(0.6) == 'medium'
        assert self.classifier.classify_severity(0.3) == 'low'
    
    def test_edge_case_confidence_values(self):
        """Test edge case confidence values"""
        # Test extreme values
        assert self.classifier.classify_severity(0.0, "damage") == 'low'
        assert self.classifier.classify_severity(1.0, "damage") == 'high'
        
        # Test values just above and below thresholds
        assert self.classifier.classify_severity(0.50001, "damage") == 'medium'
        assert self.classifier.classify_severity(0.49999, "damage") == 'low'
        assert self.classifier.classify_severity(0.80001, "damage") == 'high'
        assert self.classifier.classify_severity(0.79999, "damage") == 'medium'
    
    def test_multiple_classifications(self):
        """Test that classifier can be used multiple times"""
        # Verify classifier maintains consistent behavior across multiple calls
        results = [
            self.classifier.classify_severity(0.9, "damage"),
            self.classifier.classify_severity(0.6, "damage"),
            self.classifier.classify_severity(0.3, "damage"),
            self.classifier.classify_severity(0.9, "general"),
        ]
        
        assert results == ['high', 'medium', 'low', None]
