"""
Unit tests for ResultAggregator
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock

from app.services.result_aggregator import ResultAggregator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier


@pytest.fixture
def mock_ocr_processor():
    """Create a mock OCRProcessor"""
    mock = Mock(spec=OCRProcessor)
    return mock


@pytest.fixture
def mock_damage_classifier():
    """Create a mock DamageClassifier"""
    mock = Mock(spec=DamageClassifier)
    return mock


@pytest.fixture
def result_aggregator(mock_ocr_processor, mock_damage_classifier):
    """Create ResultAggregator with mocked dependencies"""
    return ResultAggregator(mock_ocr_processor, mock_damage_classifier)


@pytest.fixture
def sample_image():
    """Create a sample image for testing"""
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestResultAggregatorInit:
    """Test ResultAggregator initialization"""
    
    def test_init_stores_dependencies(self, mock_ocr_processor, mock_damage_classifier):
        """Test that __init__ stores OCRProcessor and DamageClassifier dependencies"""
        aggregator = ResultAggregator(mock_ocr_processor, mock_damage_classifier)
        
        assert aggregator.ocr_processor is mock_ocr_processor
        assert aggregator.damage_classifier is mock_damage_classifier


class TestAggregateDetections:
    """Test aggregate_detections method"""
    
    def test_enriches_id_detection_with_ocr(
        self, 
        result_aggregator, 
        mock_ocr_processor,
        sample_image
    ):
        """Test that ID detections are processed through OCR"""
        # Setup
        mock_ocr_processor.extract_container_id.return_value = "ABCD1234567"
        
        raw_detections = [{
            'class_name': 'container_id',
            'confidence': 0.95,
            'bbox_x': 100,
            'bbox_y': 200,
            'bbox_w': 300,
            'bbox_h': 50,
            'model_source': 'id'
        }]
        
        # Execute
        enriched = result_aggregator.aggregate_detections(sample_image, raw_detections)
        
        # Verify
        assert len(enriched) == 1
        assert enriched[0]['container_id'] == "ABCD1234567"
        assert enriched[0]['severity'] is None
        
        # Verify OCR was called with correct bbox
        mock_ocr_processor.extract_container_id.assert_called_once_with(
            sample_image,
            (100, 200, 300, 50)
        )
    
    def test_enriches_damage_detection_with_severity(
        self,
        result_aggregator,
        mock_damage_classifier,
        sample_image
    ):
        """Test that damage detections are classified with severity"""
        # Setup
        mock_damage_classifier.classify_severity.return_value = "high"
        
        raw_detections = [{
            'class_name': 'dent',
            'confidence': 0.85,
            'bbox_x': 50,
            'bbox_y': 100,
            'bbox_w': 200,
            'bbox_h': 150,
            'model_source': 'damage'
        }]
        
        # Execute
        enriched = result_aggregator.aggregate_detections(sample_image, raw_detections)
        
        # Verify
        assert len(enriched) == 1
        assert enriched[0]['severity'] == "high"
        assert enriched[0]['container_id'] is None
        
        # Verify classifier was called with correct parameters
        mock_damage_classifier.classify_severity.assert_called_once_with(
            0.85,
            'damage'
        )
    
    def test_general_detection_passes_through_unchanged(
        self,
        result_aggregator,
        sample_image
    ):
        """Test that general detections pass through without enrichment"""
        raw_detections = [{
            'class_name': 'person',
            'confidence': 0.75,
            'bbox_x': 10,
            'bbox_y': 20,
            'bbox_w': 100,
            'bbox_h': 200,
            'model_source': 'general'
        }]
        
        # Execute
        enriched = result_aggregator.aggregate_detections(sample_image, raw_detections)
        
        # Verify
        assert len(enriched) == 1
        assert enriched[0]['container_id'] is None
        assert enriched[0]['severity'] is None
        assert enriched[0]['class_name'] == 'person'
        assert enriched[0]['confidence'] == 0.75
    
    def test_processes_multiple_detections_from_different_models(
        self,
        result_aggregator,
        mock_ocr_processor,
        mock_damage_classifier,
        sample_image
    ):
        """Test processing detections from all three models"""
        # Setup
        mock_ocr_processor.extract_container_id.return_value = "TEST1234567"
        mock_damage_classifier.classify_severity.return_value = "medium"
        
        raw_detections = [
            {
                'class_name': 'person',
                'confidence': 0.80,
                'bbox_x': 10,
                'bbox_y': 20,
                'bbox_w': 100,
                'bbox_h': 200,
                'model_source': 'general'
            },
            {
                'class_name': 'scratch',
                'confidence': 0.65,
                'bbox_x': 150,
                'bbox_y': 100,
                'bbox_w': 80,
                'bbox_h': 60,
                'model_source': 'damage'
            },
            {
                'class_name': 'container_id',
                'confidence': 0.92,
                'bbox_x': 200,
                'bbox_y': 50,
                'bbox_w': 250,
                'bbox_h': 40,
                'model_source': 'id'
            }
        ]
        
        # Execute
        enriched = result_aggregator.aggregate_detections(sample_image, raw_detections)
        
        # Verify
        assert len(enriched) == 3
        
        # Check general detection
        assert enriched[0]['model_source'] == 'general'
        assert enriched[0]['container_id'] is None
        assert enriched[0]['severity'] is None
        
        # Check damage detection
        assert enriched[1]['model_source'] == 'damage'
        assert enriched[1]['severity'] == "medium"
        assert enriched[1]['container_id'] is None
        
        # Check ID detection
        assert enriched[2]['model_source'] == 'id'
        assert enriched[2]['container_id'] == "TEST1234567"
        assert enriched[2]['severity'] is None
    
    def test_preserves_all_original_fields(
        self,
        result_aggregator,
        sample_image
    ):
        """Test that all original detection fields are preserved"""
        raw_detections = [{
            'class_name': 'truck',
            'confidence': 0.88,
            'bbox_x': 50,
            'bbox_y': 60,
            'bbox_w': 300,
            'bbox_h': 400,
            'model_source': 'general'
        }]
        
        # Execute
        enriched = result_aggregator.aggregate_detections(sample_image, raw_detections)
        
        # Verify all original fields are present
        assert enriched[0]['class_name'] == 'truck'
        assert enriched[0]['confidence'] == 0.88
        assert enriched[0]['bbox_x'] == 50
        assert enriched[0]['bbox_y'] == 60
        assert enriched[0]['bbox_w'] == 300
        assert enriched[0]['bbox_h'] == 400
        assert enriched[0]['model_source'] == 'general'
    
    def test_handles_empty_detection_list(
        self,
        result_aggregator,
        sample_image
    ):
        """Test handling of empty detection list"""
        enriched = result_aggregator.aggregate_detections(sample_image, [])
        
        assert enriched == []


class TestSelectBestContainerId:
    """Test _select_best_container_id method"""
    
    def test_selects_highest_confidence_container_id(self, result_aggregator):
        """Test selection of highest confidence container ID"""
        id_detections = [
            {
                'container_id': 'ABCD1234567',
                'confidence': 0.75
            },
            {
                'container_id': 'EFGH7654321',
                'confidence': 0.92
            },
            {
                'container_id': 'IJKL1111111',
                'confidence': 0.68
            }
        ]
        
        best_id = result_aggregator._select_best_container_id(id_detections)
        
        assert best_id == 'EFGH7654321'
    
    def test_ignores_unknown_container_ids(self, result_aggregator):
        """Test that UNKNOWN container IDs are filtered out"""
        id_detections = [
            {
                'container_id': 'UNKNOWN',
                'confidence': 0.95
            },
            {
                'container_id': 'ABCD1234567',
                'confidence': 0.70
            }
        ]
        
        best_id = result_aggregator._select_best_container_id(id_detections)
        
        assert best_id == 'ABCD1234567'
    
    def test_returns_none_when_all_unknown(self, result_aggregator):
        """Test returns None when all container IDs are UNKNOWN"""
        id_detections = [
            {
                'container_id': 'UNKNOWN',
                'confidence': 0.85
            },
            {
                'container_id': 'UNKNOWN',
                'confidence': 0.92
            }
        ]
        
        best_id = result_aggregator._select_best_container_id(id_detections)
        
        assert best_id is None
    
    def test_returns_none_for_empty_list(self, result_aggregator):
        """Test returns None for empty detection list"""
        best_id = result_aggregator._select_best_container_id([])
        
        assert best_id is None
    
    def test_handles_single_valid_detection(self, result_aggregator):
        """Test handling of single valid detection"""
        id_detections = [
            {
                'container_id': 'TEST1234567',
                'confidence': 0.80
            }
        ]
        
        best_id = result_aggregator._select_best_container_id(id_detections)
        
        assert best_id == 'TEST1234567'
    
    def test_ignores_none_container_ids(self, result_aggregator):
        """Test that None container IDs are filtered out"""
        id_detections = [
            {
                'container_id': None,
                'confidence': 0.90
            },
            {
                'container_id': 'ABCD1234567',
                'confidence': 0.75
            }
        ]
        
        best_id = result_aggregator._select_best_container_id(id_detections)
        
        assert best_id == 'ABCD1234567'
