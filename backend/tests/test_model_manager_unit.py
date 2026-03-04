"""
Unit tests for ModelManager component
Tests model loading, OCR lazy initialization, and error handling
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.services.model_manager import ModelManager


class TestModelManager:
    """Unit tests for ModelManager class"""
    
    def setup_method(self):
        """Reset singleton before each test"""
        ModelManager._instance = None
    
    def test_singleton_pattern(self):
        """Test that ModelManager follows singleton pattern"""
        manager1 = ModelManager()
        manager2 = ModelManager()
        assert manager1 is manager2, "ModelManager should be a singleton"
    
    def test_initialization(self):
        """Test ModelManager initialization"""
        manager = ModelManager()
        assert manager.general_model is None
        assert manager.damage_model is None
        assert manager.id_model is None
        assert manager._ocr_engine is None
    
    def test_load_models_success(self):
        """Test successful model loading with valid paths"""
        manager = ModelManager()
        
        with patch('app.services.model_manager.YOLO') as mock_yolo:
            mock_yolo.return_value = MagicMock()
            status = manager.load_models()
            
            # All models should load successfully
            assert status['general'] == True
            assert status['damage'] == True
            assert status['id'] == True
            assert manager.general_model is not None
            assert manager.damage_model is not None
            assert manager.id_model is not None
    
    def test_load_models_partial_failure(self):
        """Test graceful handling when some models fail to load"""
        manager = ModelManager()
        
        def mock_yolo_side_effect(path):
            # Simulate damage model failing to load
            if 'Kaggle_CDD' in str(path):
                raise Exception("Model file not found")
            return MagicMock()
        
        with patch('app.services.model_manager.YOLO', side_effect=mock_yolo_side_effect):
            status = manager.load_models()
            
            # General and ID models should succeed, damage should fail
            assert status['general'] == True
            assert status['damage'] == False
            assert status['id'] == True
            assert manager.general_model is not None
            assert manager.damage_model is None
            assert manager.id_model is not None
    
    def test_load_models_all_failure(self):
        """Test graceful handling when all models fail to load"""
        manager = ModelManager()
        
        with patch('app.services.model_manager.YOLO', side_effect=Exception("Model error")):
            status = manager.load_models()
            
            # All models should fail gracefully
            assert status['general'] == False
            assert status['damage'] == False
            assert status['id'] == False
            assert manager.general_model is None
            assert manager.damage_model is None
            assert manager.id_model is None
    
    def test_is_model_available(self):
        """Test model availability checking"""
        manager = ModelManager()
        
        # Initially no models available
        assert manager.is_model_available('general') == False
        assert manager.is_model_available('damage') == False
        assert manager.is_model_available('id') == False
        
        # Set models manually
        manager.general_model = MagicMock()
        manager.damage_model = MagicMock()
        
        assert manager.is_model_available('general') == True
        assert manager.is_model_available('damage') == True
        assert manager.is_model_available('id') == False
    
    def test_is_model_available_invalid_type(self):
        """Test handling of invalid model type"""
        manager = ModelManager()
        assert manager.is_model_available('invalid') == False
    
    def test_lazy_ocr_loading_success(self):
        """Test lazy OCR engine initialization on first call"""
        manager = ModelManager()
        
        with patch('app.services.model_manager.PaddleOCR') as mock_paddle:
            mock_ocr = MagicMock()
            mock_paddle.return_value = mock_ocr
            
            # First call should initialize OCR
            ocr1 = manager.get_ocr_engine()
            assert ocr1 is mock_ocr
            assert manager._ocr_engine is mock_ocr
            mock_paddle.assert_called_once_with(lang='en')
            
            # Second call should return cached instance
            ocr2 = manager.get_ocr_engine()
            assert ocr2 is mock_ocr
            assert ocr1 is ocr2
            # PaddleOCR should still only be called once
            mock_paddle.assert_called_once()
    
    def test_lazy_ocr_loading_failure(self):
        """Test graceful handling of OCR initialization failure"""
        manager = ModelManager()
        
        with patch('app.services.model_manager.PaddleOCR', side_effect=Exception("OCR init failed")):
            # Should return None instead of raising exception
            ocr = manager.get_ocr_engine()
            assert ocr is None
            assert manager._ocr_engine is None
    
    def test_lazy_ocr_loading_failure_retry(self):
        """Test that OCR initialization is retried on subsequent calls after failure"""
        manager = ModelManager()
        
        # First call fails
        with patch('app.services.model_manager.PaddleOCR', side_effect=Exception("OCR init failed")):
            ocr1 = manager.get_ocr_engine()
            assert ocr1 is None
        
        # Second call succeeds
        with patch('app.services.model_manager.PaddleOCR') as mock_paddle:
            mock_ocr = MagicMock()
            mock_paddle.return_value = mock_ocr
            
            ocr2 = manager.get_ocr_engine()
            assert ocr2 is mock_ocr
            assert manager._ocr_engine is mock_ocr
