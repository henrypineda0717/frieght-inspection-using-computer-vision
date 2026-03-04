"""
Unit tests for VideoProcessor
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch, call
import cv2

from app.services.video_processor import VideoProcessor
from app.services.detection_coordinator import DetectionCoordinator
from app.services.result_aggregator import ResultAggregator


class TestVideoProcessor:
    """Test suite for VideoProcessor class"""
    
    @pytest.fixture
    def mock_detection_coordinator(self):
        """Create a mock DetectionCoordinator"""
        coordinator = Mock(spec=DetectionCoordinator)
        coordinator.detect_all = Mock(return_value=[
            {
                'class_name': 'container',
                'confidence': 0.9,
                'bbox_x': 10,
                'bbox_y': 20,
                'bbox_w': 100,
                'bbox_h': 150,
                'model_source': 'general'
            }
        ])
        return coordinator
    
    @pytest.fixture
    def mock_result_aggregator(self):
        """Create a mock ResultAggregator"""
        aggregator = Mock(spec=ResultAggregator)
        aggregator.aggregate_detections = Mock(return_value=[
            {
                'class_name': 'container',
                'confidence': 0.9,
                'bbox_x': 10,
                'bbox_y': 20,
                'bbox_w': 100,
                'bbox_h': 150,
                'model_source': 'general',
                'container_id': None,
                'severity': None
            }
        ])
        return aggregator
    
    @pytest.fixture
    def video_processor(self, mock_detection_coordinator, mock_result_aggregator):
        """Create VideoProcessor with mocked dependencies"""
        return VideoProcessor(
            detection_coordinator=mock_detection_coordinator,
            result_aggregator=mock_result_aggregator,
            frame_sample_rate=1
        )
    
    @pytest.fixture
    def sample_frame(self):
        """Create a sample video frame"""
        return np.zeros((480, 640, 3), dtype=np.uint8)
    
    def test_init(self, mock_detection_coordinator, mock_result_aggregator):
        """Test VideoProcessor initialization"""
        processor = VideoProcessor(
            detection_coordinator=mock_detection_coordinator,
            result_aggregator=mock_result_aggregator,
            frame_sample_rate=2
        )
        
        assert processor.detection_coordinator == mock_detection_coordinator
        assert processor.result_aggregator == mock_result_aggregator
        assert processor.frame_sample_rate == 2
    
    def test_init_default_frame_sample_rate(self, mock_detection_coordinator, mock_result_aggregator):
        """Test VideoProcessor initialization with default frame_sample_rate"""
        processor = VideoProcessor(
            detection_coordinator=mock_detection_coordinator,
            result_aggregator=mock_result_aggregator
        )
        
        assert processor.frame_sample_rate == 1
    
    def test_model_colors_defined(self):
        """Test that model colors are properly defined"""
        assert VideoProcessor.MODEL_COLORS['general'] == (255, 0, 0)  # Blue
        assert VideoProcessor.MODEL_COLORS['damage'] == (0, 0, 255)   # Red
        assert VideoProcessor.MODEL_COLORS['id'] == (0, 255, 0)       # Green
    
    def test_format_label_general_detection(self, video_processor):
        """Test label formatting for general detections"""
        detection = {
            'class_name': 'container',
            'confidence': 0.856,
            'model_source': 'general',
            'severity': None,
            'container_id': None
        }
        
        label = video_processor._format_label(detection)
        assert label == "container (85.6%)"
    
    def test_format_label_damage_detection_with_severity(self, video_processor):
        """Test label formatting for damage detections with severity"""
        detection = {
            'class_name': 'dent',
            'confidence': 0.92,
            'model_source': 'damage',
            'severity': 'high',
            'container_id': None
        }
        
        label = video_processor._format_label(detection)
        assert label == "dent (92.0%) [high]"
    
    def test_format_label_id_detection_with_container_id(self, video_processor):
        """Test label formatting for ID detections with container ID"""
        detection = {
            'class_name': 'text',
            'confidence': 0.78,
            'model_source': 'id',
            'severity': None,
            'container_id': 'ABCD1234567'
        }
        
        label = video_processor._format_label(detection)
        assert label == "text (78.0%) [ABCD1234567]"
    
    def test_format_label_id_detection_with_unknown(self, video_processor):
        """Test label formatting for ID detections with UNKNOWN container ID"""
        detection = {
            'class_name': 'text',
            'confidence': 0.65,
            'model_source': 'id',
            'severity': None,
            'container_id': 'UNKNOWN'
        }
        
        label = video_processor._format_label(detection)
        assert label == "text (65.0%) [UNKNOWN]"
    
    def test_draw_detections_draws_all_boxes(self, video_processor, sample_frame):
        """Test that draw_detections draws bounding boxes for all detections"""
        detections = [
            {
                'class_name': 'container',
                'confidence': 0.9,
                'bbox_x': 10,
                'bbox_y': 20,
                'bbox_w': 100,
                'bbox_h': 150,
                'model_source': 'general',
                'severity': None,
                'container_id': None
            },
            {
                'class_name': 'dent',
                'confidence': 0.85,
                'bbox_x': 200,
                'bbox_y': 100,
                'bbox_w': 50,
                'bbox_h': 60,
                'model_source': 'damage',
                'severity': 'high',
                'container_id': None
            }
        ]
        
        with patch('cv2.rectangle') as mock_rectangle, \
             patch('cv2.putText') as mock_putText, \
             patch('cv2.getTextSize', return_value=((100, 20), 5)):
            
            result_frame = video_processor.draw_detections(sample_frame, detections)
            
            # Should draw 2 bounding boxes + 2 label backgrounds = 4 rectangles
            assert mock_rectangle.call_count == 4
            
            # Should draw 2 text labels
            assert mock_putText.call_count == 2
            
            # Verify result is a numpy array
            assert isinstance(result_frame, np.ndarray)
    
    def test_draw_detections_uses_correct_colors(self, video_processor, sample_frame):
        """Test that draw_detections uses correct colors for different model sources"""
        detections = [
            {
                'class_name': 'container',
                'confidence': 0.9,
                'bbox_x': 10,
                'bbox_y': 20,
                'bbox_w': 100,
                'bbox_h': 150,
                'model_source': 'general',
                'severity': None,
                'container_id': None
            },
            {
                'class_name': 'dent',
                'confidence': 0.85,
                'bbox_x': 200,
                'bbox_y': 100,
                'bbox_w': 50,
                'bbox_h': 60,
                'model_source': 'damage',
                'severity': 'high',
                'container_id': None
            },
            {
                'class_name': 'text',
                'confidence': 0.75,
                'bbox_x': 300,
                'bbox_y': 200,
                'bbox_w': 80,
                'bbox_h': 40,
                'model_source': 'id',
                'severity': None,
                'container_id': 'ABCD1234567'
            }
        ]
        
        with patch('cv2.rectangle') as mock_rectangle, \
             patch('cv2.putText'), \
             patch('cv2.getTextSize', return_value=((100, 20), 5)):
            
            video_processor.draw_detections(sample_frame, detections)
            
            # Extract colors used for bounding boxes (every other rectangle call)
            bbox_calls = [call for i, call in enumerate(mock_rectangle.call_args_list) if i % 2 == 0]
            
            # Check colors: general=blue, damage=red, id=green
            assert bbox_calls[0][0][3] == (255, 0, 0)  # Blue for general
            assert bbox_calls[1][0][3] == (0, 0, 255)  # Red for damage
            assert bbox_calls[2][0][3] == (0, 255, 0)  # Green for id
    
    def test_draw_detections_empty_list(self, video_processor, sample_frame):
        """Test draw_detections with empty detection list"""
        detections = []
        
        with patch('cv2.rectangle') as mock_rectangle, \
             patch('cv2.putText') as mock_putText:
            
            result_frame = video_processor.draw_detections(sample_frame, detections)
            
            # No rectangles or text should be drawn
            assert mock_rectangle.call_count == 0
            assert mock_putText.call_count == 0
            
            # Frame should still be returned
            assert isinstance(result_frame, np.ndarray)
    
    def test_process_video_invalid_path(self, video_processor):
        """Test process_video raises ValueError for invalid video path"""
        with pytest.raises(ValueError, match="Failed to open video file"):
            list(video_processor.process_video("nonexistent_video.mp4"))
    
    @patch('cv2.VideoCapture')
    def test_process_video_frame_sampling(
        self, 
        mock_video_capture_class,
        video_processor,
        mock_detection_coordinator,
        mock_result_aggregator,
        sample_frame
    ):
        """Test that process_video samples frames correctly"""
        # Create mock video capture
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: 10,
            cv2.CAP_PROP_FPS: 30.0
        }.get(prop, 0)
        
        # Simulate 10 frames
        mock_cap.read.side_effect = [
            (True, sample_frame.copy()) for _ in range(10)
        ] + [(False, None)]
        
        mock_video_capture_class.return_value = mock_cap
        
        # Process video with frame_sample_rate=1 (every frame)
        frames_processed = list(video_processor.process_video("test_video.mp4"))
        
        # Should process all 10 frames
        assert len(frames_processed) == 10
        
        # Each result should be a tuple of (frame, detections, frame_number)
        for i, (frame, detections, frame_num) in enumerate(frames_processed):
            assert isinstance(frame, np.ndarray)
            assert isinstance(detections, list)
            assert frame_num == i
    
    @patch('cv2.VideoCapture')
    def test_process_video_frame_sampling_rate_2(
        self,
        mock_video_capture_class,
        mock_detection_coordinator,
        mock_result_aggregator,
        sample_frame
    ):
        """Test that process_video respects frame_sample_rate parameter"""
        # Create processor with frame_sample_rate=2
        processor = VideoProcessor(
            detection_coordinator=mock_detection_coordinator,
            result_aggregator=mock_result_aggregator,
            frame_sample_rate=2
        )
        
        # Create mock video capture
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: 10,
            cv2.CAP_PROP_FPS: 30.0
        }.get(prop, 0)
        
        # Simulate 10 frames
        mock_cap.read.side_effect = [
            (True, sample_frame.copy()) for _ in range(10)
        ] + [(False, None)]
        
        mock_video_capture_class.return_value = mock_cap
        
        # Process video
        frames_processed = list(processor.process_video("test_video.mp4"))
        
        # Should process every 2nd frame: frames 0, 2, 4, 6, 8 = 5 frames
        assert len(frames_processed) == 5
        
        # Check frame numbers
        frame_numbers = [frame_num for _, _, frame_num in frames_processed]
        assert frame_numbers == [0, 2, 4, 6, 8]
    
    @patch('cv2.VideoCapture')
    def test_process_video_calls_detection_pipeline(
        self,
        mock_video_capture_class,
        video_processor,
        mock_detection_coordinator,
        mock_result_aggregator,
        sample_frame
    ):
        """Test that process_video calls detection coordinator and aggregator"""
        # Create mock video capture
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: 3,
            cv2.CAP_PROP_FPS: 30.0
        }.get(prop, 0)
        
        # Simulate 3 frames
        mock_cap.read.side_effect = [
            (True, sample_frame.copy()) for _ in range(3)
        ] + [(False, None)]
        
        mock_video_capture_class.return_value = mock_cap
        
        # Process video
        list(video_processor.process_video("test_video.mp4"))
        
        # Verify detection coordinator was called 3 times
        assert mock_detection_coordinator.detect_all.call_count == 3
        
        # Verify result aggregator was called 3 times
        assert mock_result_aggregator.aggregate_detections.call_count == 3
    
    @patch('cv2.VideoCapture')
    def test_process_video_releases_capture(
        self,
        mock_video_capture_class,
        video_processor,
        sample_frame
    ):
        """Test that process_video releases video capture after processing"""
        # Create mock video capture
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: 2,
            cv2.CAP_PROP_FPS: 30.0
        }.get(prop, 0)
        
        # Simulate 2 frames
        mock_cap.read.side_effect = [
            (True, sample_frame.copy()),
            (True, sample_frame.copy()),
            (False, None)
        ]
        
        mock_video_capture_class.return_value = mock_cap
        
        # Process video
        list(video_processor.process_video("test_video.mp4"))
        
        # Verify release was called
        mock_cap.release.assert_called_once()
