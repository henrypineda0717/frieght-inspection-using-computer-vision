# Detection Filtering and Statistics Endpoints

This document describes the new endpoints added for querying and filtering detections in the multi-model YOLO integration.

## Endpoints

### 1. GET /history/detections/

Query detections with flexible filtering options.

**Query Parameters:**
- `inspection_id` (optional, int): Filter detections by inspection ID
- `model_source` (optional, str): Filter by model source ("general", "damage", "id")
- `severity` (optional, str): Filter by severity level ("low", "medium", "high")
- `container_id` (optional, str): Filter by container ID
- `page` (optional, int, default=1): Page number for pagination
- `page_size` (optional, int, default=50, max=200): Number of items per page

**Response:**
```json
{
  "total": 100,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": 1,
      "label": "damage",
      "category": null,
      "confidence": 0.9,
      "bbox_x": 10,
      "bbox_y": 20,
      "bbox_w": 100,
      "bbox_h": 150,
      "severity": "high",
      "defect_type": null,
      "legend": null,
      "model_source": "damage",
      "container_id": null
    }
  ]
}
```

**Examples:**
```bash
# Get all damage detections
GET /history/detections/?model_source=damage

# Get high severity detections
GET /history/detections/?severity=high

# Get detections for a specific container
GET /history/detections/?container_id=ABCD1234567

# Combine multiple filters
GET /history/detections/?model_source=damage&severity=high&inspection_id=1
```

### 2. GET /history/detections/statistics

Get detection statistics grouped by model source and severity.

**Query Parameters:**
- `inspection_id` (optional, int): Get statistics for a specific inspection

**Response:**
```json
{
  "total_detections": 18,
  "by_model_source": {
    "general": 10,
    "damage": 5,
    "id": 3
  },
  "by_severity": {
    "high": 2,
    "medium": 2,
    "low": 1
  }
}
```

**Examples:**
```bash
# Get overall statistics
GET /history/detections/statistics

# Get statistics for a specific inspection
GET /history/detections/statistics?inspection_id=1
```

### 3. GET /history/{inspection_id}/report

Generate an inspection report with model breakdown.

**Path Parameters:**
- `inspection_id` (required, int): The inspection ID

**Response:**
```json
{
  "inspection_id": 1,
  "container_id": "ABCD1234567",
  "timestamp": "2024-01-01T12:00:00",
  "status": "completed",
  "stage": "arrival",
  "frame_count": 3,
  "detection_statistics": {
    "total_detections": 18,
    "by_model_source": {
      "general": 10,
      "damage": 5,
      "id": 3
    },
    "by_severity": {
      "high": 2,
      "medium": 2,
      "low": 1
    }
  },
  "detected_container_ids": ["ABCD1234567", "EFGH7654321"],
  "risk_score": 0.5,
  "contamination_index": 0.3
}
```

**Example:**
```bash
GET /history/1/report
```

## Use Cases

### 1. Filter by Model Source
Query all detections from a specific model:
```bash
# Get all damage detections
GET /history/detections/?model_source=damage

# Get all ID detections
GET /history/detections/?model_source=id

# Get all general detections
GET /history/detections/?model_source=general
```

### 2. Filter by Severity
Query damage detections by severity level:
```bash
# Get high severity damage
GET /history/detections/?severity=high

# Get medium severity damage
GET /history/detections/?severity=medium
```

### 3. Filter by Container ID
Query all detections associated with a specific container:
```bash
GET /history/detections/?container_id=ABCD1234567
```

### 4. Multiple Filter Combinations
Combine filters for precise queries:
```bash
# High severity damage for a specific inspection
GET /history/detections/?inspection_id=1&model_source=damage&severity=high

# All detections for a container in a specific inspection
GET /history/detections/?inspection_id=1&container_id=ABCD1234567
```

### 5. Detection Statistics
Get aggregated statistics:
```bash
# Overall system statistics
GET /history/detections/statistics

# Statistics for a specific inspection
GET /history/detections/statistics?inspection_id=1
```

### 6. Inspection Reports
Generate comprehensive reports with model breakdown:
```bash
GET /history/1/report
```

## Implementation Details

### Database Queries
- All queries use SQLAlchemy ORM with proper joins
- Filters are applied conditionally based on provided parameters
- Pagination is implemented using offset/limit
- Statistics use SQL GROUP BY for efficient aggregation

### Performance Considerations
- Index on `model_source` column for efficient filtering
- Foreign key relationships for container_id lookups
- Pagination limits maximum page size to 200 items
- Statistics queries use aggregation at database level

### Backward Compatibility
- All new endpoints are additive (no breaking changes)
- Existing endpoints continue to work as before
- New fields in responses are optional
