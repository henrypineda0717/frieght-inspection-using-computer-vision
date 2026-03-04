"""
Unit tests for DetectionCoordinator
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch

from app.services.detection_coordinator import DetectionCoordinator
from app.services.model_manager import ModelManager


class TestDetectionCoordinator:
    """Test suite for DetectionCoordinator class"""
    
    @pytest.fixture
    def mock_model_manager(self):
        """Create a mock ModelManager with all models available"""
        manager = Mock(spec=ModelManager)
        manager.is_model_available = Mock(return_value=True)
        
        # Create mock models
        manager.general_model = Mock()
        manager.damage_model = Mock()
        manager.id_model = Mock()
        
        return manager
    
    @pytest.fixture
    def coordinator(self, mock_model_manager):
        """Create DetectionCoordinator with mock ModelManager"""
        return DetectionCoordinator(mock_model_manager)
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample image for testing"""
        return np.zeros((640, 640, 3), dtype=np.uint8)
    
    def test_init(self, mock_model_manager):
        """Test DetectionCoordinator initialization"""
        coordinator = DetectionCoordinator(mock_model_manager)
        assert coordinator.model_manager == mock_model_manager
    
    def test_detect_all_with_all_models_available(self, coordinator, mock_model_manager, sample_image):
        """Test detect_all runs all available models"""
        # Mock _run_model to return sample detections
        with patch.object(coordinator, '_run_model') as mock_run_model:
            mock_run_model.side_effect = [
                [{'class_name': 'person', 'confidence': 0.9, 'model_source': 'general'}],
                [{'class_name': 'dent', 'confidence': 0.8, 'model_source': 'damage'}],
                [{'class_name': 'text', 'confidence': 0.7, 'model_source': 'id'}]
            ]
            
            detections = coordinator.detect_all(sample_image)
            
            # Verify all three models were called
            assert mock_run_model.call_count == 3
            
            # Verify all detections are returned
            assert len(detections) == 3
            assert detections[0]['model_source'] == 'general'
            assert detections[1]['model_source'] == 'damage'
            assert detections[2]['model_source'] == 'id'
    
    def test_detect_all_with_partial_models(self, coordinator, mock_model_manager, sample_image):
        """Test detect_all works when only some models are available"""
        # Only general and damage models available
        mock_model_manager.is_model_available = Mock(side_effect=lambda x: x in ['general', 'damage'])
        
        with patch.object(coordinator, '_run_model') as mock_run_model:
            mock_run_model.side_effect = [
                [{'class_name': 'person', 'confidence': 0.9, 'model_source': 'general'}],
                [{'class_name': 'dent', 'confidence': 0.8, 'model_source': 'damage'}]
            ]
            
            detections = coordinator.detect_all(sample_image)
            
            # Only two models should be called
            assert mock_run_model.call_count == 2
            assert len(detections) == 2
    
    def test_detect_all_handles_model_failure(self, coordinator, mock_model_manager, sample_image):
        """Test detect_all continues when a model fails"""
        with patch.object(coordinator, '_run_model') as mock_run_model:
            # First model succeeds, second fails, third succeeds
            mock_run_model.side_effect = [
                [{'class_name': 'person', 'confidence': 0.9, 'model_source': 'general'}],
                Exception("Model inference failed"),
                [{'class_name': 'text', 'confidence': 0.7, 'model_source': 'id'}]
            ]
            
            detections = coordinator.detect_all(sample_image)
            
            # Should have detections from successful models
            assert len(detections) == 2
            assert detections[0]['model_source'] == 'general'
            assert detections[1]['model_source'] == 'id'
    
    def test_run_model_tags_detections_correctly(self, coordinator, sample_image):
        """Test _run_model correctly tags detections with model source"""
        # Create a mock YOLO model with mock results
        mock_model = Mock()
        mock_model.names = {0: 'person', 1: 'car'}
        
        # Create mock Results object
        mock_result = Mock()
        mock_boxes = Mock()
        
        # Mock box data (2 detections)
        mock_boxes.xyxy = [
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([10, 20, 50, 80]))))),
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([100, 150, 200, 250])))))
        ]
        mock_boxes.conf = [
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=0.95)))),
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=0.85))))
        ]
        mock_boxes.cls = [
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=0)))),
            Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=1))))
        ]
        
        # Add __len__ to mock_boxes so it can be used in range()
        mock_boxes.__len__ = Mock(return_value=2)
        
        mock_result.boxes = mock_boxes
        mock_model.return_value = [mock_result]
        
        # Run the model
        detections = coordinator._run_model(mock_model, sample_image, 'general')
        
        # Verify detections
        assert len(detections) == 2
        
        # Check first detection
        assert detections[0]['class_name'] == 'person'
        assert detections[0]['confidence'] == 0.95
        assert detections[0]['bbox_x'] == 10
        assert detections[0]['bbox_y'] == 20
        assert detections[0]['bbox_w'] == 40
        assert detections[0]['bbox_h'] == 60
        assert detections[0]['model_source'] == 'general'
        
        # Check second detection
        assert detections[1]['class_name'] == 'car'
        assert detections[1]['confidence'] == 0.85
        assert detections[1]['bbox_x'] == 100
        assert detections[1]['bbox_y'] == 150
        assert detections[1]['bbox_w'] == 100
        assert detections[1]['bbox_h'] == 100
        assert detections[1]['model_source'] == 'general'
    
    def test_run_model_with_different_sources(self, coordinator, sample_image):
        """Test _run_model correctly applies different source tags"""
        mock_model = Mock()
        mock_model.names = {0: 'object'}
        
        # Create minimal mock result
        mock_result = Mock()
        mock_boxes = Mock()
        mock_boxes.xyxy = [Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0, 0, 10, 10])))))]
        mock_boxes.conf = [Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=0.9))))]
        mock_boxes.cls = [Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=0))))]
        mock_boxes.__len__ = Mock(return_value=1)  # Add __len__ for range()
        mock_result.boxes = mock_boxes
        mock_model.return_value = [mock_result]
        
        # Test with different sources
        general_detections = coordinator._run_model(mock_model, sample_image, 'general')
        assert general_detections[0]['model_source'] == 'general'
        
        damage_detections = coordinator._run_model(mock_model, sample_image, 'damage')
        assert damage_detections[0]['model_source'] == 'damage'
        
        id_detections = coordinator._run_model(mock_model, sample_image, 'id')
        assert id_detections[0]['model_source'] == 'id'
    
    def test_detect_all_preserves_all_detections(self, coordinator, mock_model_manager, sample_image):
        """Test that detect_all preserves all detections without deduplication"""
        with patch.object(coordinator, '_run_model') as mock_run_model:
            # Return multiple detections from each model
            mock_run_model.side_effect = [
                [
                    {'class_name': 'person', 'confidence': 0.9, 'model_source': 'general'},
                    {'class_name': 'car', 'confidence': 0.8, 'model_source': 'general'}
                ],
                [
                    {'class_name': 'dent', 'confidence': 0.85, 'model_source': 'damage'},
                    {'class_name': 'scratch', 'confidence': 0.75, 'model_source': 'damage'}
                ],
                [
                    {'class_name': 'text', 'confidence': 0.7, 'model_source': 'id'}
                ]
            ]
            
            detections = coordinator.detect_all(sample_image)
            
            # All 5 detections should be preserved
            assert len(detections) == 5
            
            # Verify order is preserved (general, then damage, then id)
            assert detections[0]['class_name'] == 'person'
            assert detections[1]['class_name'] == 'car'
            assert detections[2]['class_name'] == 'dent'
            assert detections[3]['class_name'] == 'scratch'
            assert detections[4]['class_name'] == 'text'
