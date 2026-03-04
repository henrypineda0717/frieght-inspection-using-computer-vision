"""
Unit tests for detection filtering and statistics endpoints
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models import Container, Inspection, Frame, Detection
from app.services.history_service import HistoryService


class TestDetectionFiltering:
    """Test detection filtering functionality"""
    
    def test_get_detections_with_model_source_filter(self):
        """Test filtering detections by model_source"""
        # Create mock database session
        db = Mock(spec=Session)
        
        # Create mock detections
        mock_detections = [
            Mock(
                id=1,
                label="damage",
                model_source="damage",
                severity="high",
                confidence=0.9,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id=None,
                category=None,
                defect_type=None,
                legend=None
            ),
            Mock(
                id=2,
                label="container_id",
                model_source="id",
                severity=None,
                confidence=0.85,
                bbox_x=50,
                bbox_y=60,
                bbox_w=200,
                bbox_h=80,
                container_id="ABCD1234567",
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        # Setup mock query chain
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        # Create service and call method
        service = HistoryService(db)
        result = service.get_detections(model_source="damage")
        
        # Verify results
        assert result["total"] == 2
        assert result["page"] == 1
        assert result["page_size"] == 50
        assert len(result["items"]) == 2
    
    def test_get_detections_with_severity_filter(self):
        """Test filtering detections by severity"""
        db = Mock(spec=Session)
        
        mock_detections = [
            Mock(
                id=1,
                label="damage",
                model_source="damage",
                severity="high",
                confidence=0.9,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id=None,
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(severity="high")
        
        assert result["total"] == 1
        assert len(result["items"]) == 1
    
    def test_get_detections_with_container_id_filter(self):
        """Test filtering detections by container_id"""
        db = Mock(spec=Session)
        
        mock_detections = [
            Mock(
                id=2,
                label="container_id",
                model_source="id",
                severity=None,
                confidence=0.85,
                bbox_x=50,
                bbox_y=60,
                bbox_w=200,
                bbox_h=80,
                container_id="ABCD1234567",
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(container_id="ABCD1234567")
        
        assert result["total"] == 1
        assert len(result["items"]) == 1
    
    def test_get_detections_with_multiple_filters(self):
        """Test filtering detections with multiple filter combinations"""
        db = Mock(spec=Session)
        
        mock_detections = [
            Mock(
                id=1,
                label="damage",
                model_source="damage",
                severity="high",
                confidence=0.9,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id="ABCD1234567",
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(
            model_source="damage",
            severity="high",
            container_id="ABCD1234567"
        )
        
        assert result["total"] == 1
        assert len(result["items"]) == 1


class TestDetectionStatistics:
    """Test detection statistics and grouping"""
    
    def test_get_detection_statistics(self):
        """Test grouping detections by model_source"""
        db = Mock(spec=Session)
        
        # Mock the grouped query results
        mock_model_results = [
            Mock(model_source="general", count=10),
            Mock(model_source="damage", count=5),
            Mock(model_source="id", count=3)
        ]
        
        mock_severity_results = [
            Mock(severity="high", count=2),
            Mock(severity="medium", count=2),
            Mock(severity="low", count=1)
        ]
        
        # Setup mock query chain
        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # First call returns model source stats, second call returns severity stats
        mock_query.all.side_effect = [mock_model_results, mock_severity_results]
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detection_statistics()
        
        # Verify statistics
        assert result["total_detections"] == 18
        assert result["by_model_source"]["general"] == 10
        assert result["by_model_source"]["damage"] == 5
        assert result["by_model_source"]["id"] == 3
        assert result["by_severity"]["high"] == 2
        assert result["by_severity"]["medium"] == 2
        assert result["by_severity"]["low"] == 1
    
    def test_get_detection_statistics_with_inspection_filter(self):
        """Test grouping detections by model_source for specific inspection"""
        db = Mock(spec=Session)
        
        # Mock the grouped query results for specific inspection
        mock_model_results = [
            Mock(model_source="damage", count=3),
            Mock(model_source="id", count=1)
        ]
        
        mock_severity_results = [
            Mock(severity="high", count=1),
            Mock(severity="medium", count=2)
        ]
        
        # Setup mock query chain
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        
        # First call returns model source stats, second call returns severity stats
        mock_query.all.side_effect = [mock_model_results, mock_severity_results]
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detection_statistics(inspection_id=1)
        
        # Verify statistics for specific inspection
        assert result["total_detections"] == 4
        assert result["by_model_source"]["damage"] == 3
        assert result["by_model_source"]["id"] == 1
        assert result["by_severity"]["high"] == 1
        assert result["by_severity"]["medium"] == 2
    
    def test_get_detection_statistics_empty_results(self):
        """Test statistics calculation with no detections"""
        db = Mock(spec=Session)
        
        # Mock empty results
        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.side_effect = [[], []]  # Empty results for both queries
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detection_statistics()
        
        # Verify empty statistics
        assert result["total_detections"] == 0
        assert result["by_model_source"] == {}
        assert result["by_severity"] == {}
    
    def test_get_detection_statistics_only_one_model(self):
        """Test statistics when only one model has detections"""
        db = Mock(spec=Session)
        
        # Mock results with only general model
        mock_model_results = [
            Mock(model_source="general", count=15)
        ]
        
        mock_severity_results = []  # No severity data
        
        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.side_effect = [mock_model_results, mock_severity_results]
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detection_statistics()
        
        # Verify statistics
        assert result["total_detections"] == 15
        assert result["by_model_source"]["general"] == 15
        assert len(result["by_model_source"]) == 1
        assert result["by_severity"] == {}
    
    def test_get_inspection_report(self):
        """Test generating inspection report with model breakdown"""
        db = Mock(spec=Session)
        
        # Mock inspection
        mock_inspection = Mock(
            id=1,
            container_id="ABCD1234567",
            timestamp="2024-01-01T12:00:00",
            status="completed",
            stage="arrival",
            frames=[Mock(), Mock(), Mock()],  # 3 frames
            risk_score=0.5,
            contamination_index=0.3
        )
        
        # Mock query for inspection
        mock_inspection_query = MagicMock()
        mock_inspection_query.filter.return_value = mock_inspection_query
        mock_inspection_query.first.return_value = mock_inspection
        
        # Mock query for container IDs
        mock_container_query = MagicMock()
        mock_container_query.join.return_value = mock_container_query
        mock_container_query.filter.return_value = mock_container_query
        mock_container_query.distinct.return_value = mock_container_query
        mock_container_query.all.return_value = [("ABCD1234567",), ("EFGH7654321",)]
        
        # Setup db.query to return different mocks based on call
        db.query.side_effect = [
            mock_inspection_query,  # First call for inspection
            MagicMock(),  # For get_detection_statistics (model source query)
            MagicMock(),  # For get_detection_statistics (severity query)
            mock_container_query  # For container IDs query
        ]
        
        service = HistoryService(db)
        result = service.get_inspection_report(1)
        
        # Verify report structure
        assert result is not None
        assert result["inspection_id"] == 1
        assert result["container_id"] == "ABCD1234567"
        assert result["frame_count"] == 3
        assert "detection_statistics" in result
        assert "detected_container_ids" in result
        assert len(result["detected_container_ids"]) == 2
    
    def test_get_inspection_report_not_found(self):
        """Test inspection report when inspection doesn't exist"""
        db = Mock(spec=Session)
        
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_inspection_report(999)
        
        # Verify None is returned
        assert result is None
    
    def test_get_inspection_report_no_container_ids(self):
        """Test inspection report with no detected container IDs"""
        db = Mock(spec=Session)
        
        # Mock inspection
        mock_inspection = Mock(
            id=1,
            container_id="UNKNOWN",
            timestamp="2024-01-01T12:00:00",
            status="completed",
            stage="arrival",
            frames=[Mock()],
            risk_score=0.0,
            contamination_index=0.0
        )
        
        # Mock query for inspection
        mock_inspection_query = MagicMock()
        mock_inspection_query.filter.return_value = mock_inspection_query
        mock_inspection_query.first.return_value = mock_inspection
        
        # Mock query for container IDs (empty)
        mock_container_query = MagicMock()
        mock_container_query.join.return_value = mock_container_query
        mock_container_query.filter.return_value = mock_container_query
        mock_container_query.distinct.return_value = mock_container_query
        mock_container_query.all.return_value = []
        
        # Setup db.query to return different mocks
        db.query.side_effect = [
            mock_inspection_query,
            MagicMock(),  # For get_detection_statistics
            MagicMock(),  # For get_detection_statistics
            mock_container_query
        ]
        
        service = HistoryService(db)
        result = service.get_inspection_report(1)
        
        # Verify report with no container IDs
        assert result is not None
        assert result["detected_container_ids"] == []


class TestFilteringCombinations:
    """Test various filter combinations"""
    
    def test_filter_by_model_source_and_severity(self):
        """Test filtering by both model_source and severity"""
        db = Mock(spec=Session)
        
        mock_detections = [
            Mock(
                id=1,
                label="damage",
                model_source="damage",
                severity="high",
                confidence=0.9,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id=None,
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(model_source="damage", severity="high")
        
        # Verify filter was applied
        assert result["total"] == 1
        assert len(result["items"]) == 1
        # Verify filter was called twice (once for model_source, once for severity)
        assert mock_query.filter.call_count >= 2
    
    def test_filter_by_inspection_id(self):
        """Test filtering detections by inspection_id"""
        db = Mock(spec=Session)
        
        mock_detections = [
            Mock(
                id=1,
                label="damage",
                model_source="damage",
                severity="medium",
                confidence=0.7,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id=None,
                category=None,
                defect_type=None,
                legend=None
            )
        ]
        
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(inspection_id=1)
        
        # Verify join was called for inspection relationship
        assert mock_query.join.call_count >= 2  # Join Frame and Inspection
        assert result["total"] == 1
    
    def test_filter_with_pagination(self):
        """Test filtering with pagination parameters"""
        db = Mock(spec=Session)
        
        # Create 100 mock detections
        mock_detections = [
            Mock(
                id=i,
                label="general",
                model_source="general",
                severity=None,
                confidence=0.8,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=150,
                container_id=None,
                category=None,
                defect_type=None,
                legend=None
            )
            for i in range(1, 21)  # Return 20 items for page 1
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_detections
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(page=1, page_size=20)
        
        # Verify pagination
        assert result["total"] == 100
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert len(result["items"]) == 20
        
        # Verify offset and limit were called
        mock_query.offset.assert_called_once_with(0)
        mock_query.limit.assert_called_once_with(20)
    
    def test_filter_no_results(self):
        """Test filtering that returns no results"""
        db = Mock(spec=Session)
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        db.query.return_value = mock_query
        
        service = HistoryService(db)
        result = service.get_detections(model_source="nonexistent")
        
        # Verify empty results
        assert result["total"] == 0
        assert len(result["items"]) == 0
        assert result["page"] == 1
        assert result["page_size"] == 50
