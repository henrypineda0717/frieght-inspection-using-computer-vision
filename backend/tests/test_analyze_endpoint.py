"""
Integration tests for the /analyze endpoint with multi-model support
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np
import cv2

from app.services.analysis_service import AnalysisService


@pytest.fixture
def sample_image_bytes():
    """Create a sample image for testing"""
    # Create a simple test image (100x100 BGR)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [255, 0, 0]  # Blue image
    
    # Encode to JPEG bytes
    success, encoded = cv2.imencode('.jpg', img)
    assert success
    return encoded.tobytes()


def test_analyze_image_multimodel_basic(sample_image_bytes):
    """
    Test the analyze_image_multimodel method.
    
    Validates:
    - Method accepts image bytes
    - Returns valid response structure
    - Response includes new multi-model fields
    """
    service = AnalysisService()
    
    # Mock the model manager to avoid loading actual models
    with patch.object(service.model_manager, 'load_models') as mock_load:
        mock_load.return_value = {'general': True, 'damage': True, 'id': True}
        
        # Mock detection coordinator to return sample detections
        with patch.object(service.detection_coordinator, 'detect_all') as mock_detect:
            mock_detect.return_value = [
                {
                    'class_name': 'container',
                    'confidence': 0.95,
                    'bbox_x': 10,
                    'bbox_y': 10,
                    'bbox_w': 50,
                    'bbox_h': 50,
                    'model_source': 'general'
                },
                {
                    'class_name': 'damage',
                    'confidence': 0.85,
                    'bbox_x': 20,
                    'bbox_y': 20,
                    'bbox_w': 30,
                    'bbox_h': 30,
                    'model_source': 'damage'
                },
                {
                    'class_name': 'id_text',
                    'confidence': 0.90,
                    'bbox_x': 30,
                    'bbox_y': 30,
                    'bbox_w': 40,
                    'bbox_h': 20,
                    'model_source': 'id'
                }
            ]
            
            # Mock result aggregator to return enriched detections
            with patch.object(service.result_aggregator, 'aggregate_detections') as mock_aggregate:
                mock_aggregate.return_value = [
                    {
                        'class_name': 'container',
                        'confidence': 0.95,
                        'bbox_x': 10,
                        'bbox_y': 10,
                        'bbox_w': 50,
                        'bbox_h': 50,
                        'model_source': 'general',
                        'severity': None,
                        'container_id': None
                    },
                    {
                        'class_name': 'damage',
                        'confidence': 0.85,
                        'bbox_x': 20,
                        'bbox_y': 20,
                        'bbox_w': 30,
                        'bbox_h': 30,
                        'model_source': 'damage',
                        'severity': 'high',
                        'container_id': None
                    },
                    {
                        'class_name': 'id_text',
                        'confidence': 0.90,
                        'bbox_x': 30,
                        'bbox_y': 30,
                        'bbox_w': 40,
                        'bbox_h': 20,
                        'model_source': 'id',
                        'severity': None,
                        'container_id': 'ABCD1234567'
                    }
                ]
                
                # Mock _select_best_container_id
                with patch.object(service.result_aggregator, '_select_best_container_id') as mock_select:
                    mock_select.return_value = 'ABCD1234567'
                    
                    # Call the method using asyncio.run
                    import asyncio
                    result = asyncio.run(service.analyze_image_multimodel(
                        image_data=sample_image_bytes,
                        damage_sensitivity='medium',
                        inspection_stage='pre'
                    ))
                    
                    # Verify response structure
                    assert 'container_id' in result
                    assert 'status' in result
                    assert 'detections' in result
                    assert 'timestamp' in result
                    assert 'risk_score' in result
                    
                    # Verify container ID was extracted
                    assert result['container_id'] == 'ABCD1234567'
                    
                    # Verify status is alert due to high severity damage
                    assert result['status'] == 'alert'
                    
                    # Verify detections are formatted correctly
                    detections = result['detections']
                    assert len(detections) == 3
                    
                    # Check each detection has required fields
                    for det in detections:
                        assert 'label' in det
                        assert 'confidence' in det
                        assert 'bbox' in det
                        assert 'model_source' in det
                        assert det['model_source'] in ['general', 'damage', 'id']
                    
                    # Verify damage detection has severity
                    damage_det = next(d for d in detections if d['model_source'] == 'damage')
                    assert damage_det['severity'] == 'high'
                    
                    # Verify ID detection has container_id
                    id_det = next(d for d in detections if d['model_source'] == 'id')
                    assert id_det['container_id'] == 'ABCD1234567'


def test_analyze_image_multimodel_no_damage(sample_image_bytes):
    """
    Test analyze_image_multimodel with no damage detections.
    
    Validates that status is 'ok' when no high severity damage is found.
    """
    service = AnalysisService()
    
    with patch.object(service.model_manager, 'load_models') as mock_load:
        mock_load.return_value = {'general': True, 'damage': False, 'id': True}
        
        with patch.object(service.detection_coordinator, 'detect_all') as mock_detect:
            mock_detect.return_value = [
                {
                    'class_name': 'container',
                    'confidence': 0.95,
                    'bbox_x': 10,
                    'bbox_y': 10,
                    'bbox_w': 50,
                    'bbox_h': 50,
                    'model_source': 'general'
                }
            ]
            
            with patch.object(service.result_aggregator, 'aggregate_detections') as mock_aggregate:
                mock_aggregate.return_value = [
                    {
                        'class_name': 'container',
                        'confidence': 0.95,
                        'bbox_x': 10,
                        'bbox_y': 10,
                        'bbox_w': 50,
                        'bbox_h': 50,
                        'model_source': 'general',
                        'severity': None,
                        'container_id': None
                    }
                ]
                
                with patch.object(service.result_aggregator, '_select_best_container_id') as mock_select:
                    mock_select.return_value = None
                    
                    import asyncio
                    result = asyncio.run(service.analyze_image_multimodel(
                        image_data=sample_image_bytes
                    ))
                    
                    # Verify status is ok (no damage)
                    assert result['status'] == 'ok'
                    
                    # Verify container_id defaults to UNKNOWN
                    assert result['container_id'] == 'UNKNOWN'
                    
                    # Verify risk score is 0
                    assert result['risk_score'] == 0


def test_format_detections_for_api():
    """
    Test the _format_detections_for_api method.
    
    Validates that internal detection format is correctly converted to API format.
    """
    service = AnalysisService()
    
    internal_detections = [
        {
            'class_name': 'damage',
            'confidence': 0.85,
            'bbox_x': 10,
            'bbox_y': 20,
            'bbox_w': 30,
            'bbox_h': 40,
            'model_source': 'damage',
            'severity': 'high',
            'container_id': None
        },
        {
            'class_name': 'id_text',
            'confidence': 0.90,
            'bbox_x': 50,
            'bbox_y': 60,
            'bbox_w': 70,
            'bbox_h': 80,
            'model_source': 'id',
            'severity': None,
            'container_id': 'ABCD1234567'
        }
    ]
    
    formatted = service._format_detections_for_api(internal_detections)
    
    assert len(formatted) == 2
    
    # Check first detection (damage)
    assert formatted[0]['label'] == 'damage'
    assert formatted[0]['confidence'] == 0.85
    assert formatted[0]['bbox'] == {'x': 10, 'y': 20, 'w': 30, 'h': 40}
    assert formatted[0]['model_source'] == 'damage'
    assert formatted[0]['severity'] == 'high'
    assert formatted[0]['container_id'] is None
    
    # Check second detection (ID)
    assert formatted[1]['label'] == 'id_text'
    assert formatted[1]['confidence'] == 0.90
    assert formatted[1]['bbox'] == {'x': 50, 'y': 60, 'w': 70, 'h': 80}
    assert formatted[1]['model_source'] == 'id'
    assert formatted[1]['severity'] is None
    assert formatted[1]['container_id'] == 'ABCD1234567'


def test_calculate_risk_score():
    """
    Test the _calculate_risk_score method.
    
    Validates risk score calculation based on damage severity.
    """
    service = AnalysisService()
    
    # Test with no damage
    assert service._calculate_risk_score([]) == 0
    
    # Test with low severity damage
    low_damage = [
        {'severity': 'low'},
        {'severity': 'low'}
    ]
    assert service._calculate_risk_score(low_damage) == 10  # 2 * 5
    
    # Test with medium severity damage
    medium_damage = [
        {'severity': 'medium'},
        {'severity': 'medium'}
    ]
    assert service._calculate_risk_score(medium_damage) == 30  # 2 * 15
    
    # Test with high severity damage
    high_damage = [
        {'severity': 'high'},
        {'severity': 'high'}
    ]
    assert service._calculate_risk_score(high_damage) == 60  # 2 * 30
    
    # Test with mixed severity
    mixed_damage = [
        {'severity': 'high'},
        {'severity': 'medium'},
        {'severity': 'low'}
    ]
    assert service._calculate_risk_score(mixed_damage) == 50  # 30 + 15 + 5
    
    # Test that score caps at 100
    many_high = [{'severity': 'high'}] * 10
    assert service._calculate_risk_score(many_high) == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])




def test_analyze_video_endpoint_exists():
    """
    Test that the /analyze-video endpoint exists and is accessible.
    
    Validates:
    - Endpoint is registered
    - Endpoint accepts POST requests
    - Endpoint requires video file parameter
    """
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Test that endpoint exists (should fail without video file)
    response = client.post('/api/analyze/analyze-video')
    
    # Should return 422 (validation error) because video file is required
    assert response.status_code == 422
    
    # Verify error message mentions missing video field
    error_detail = response.json()
    assert 'detail' in error_detail

