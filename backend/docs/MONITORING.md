# Monitoring and Metrics

This document describes the error logging and monitoring capabilities added to the multi-model YOLO integration.

## Error Logging

Comprehensive error logging has been added throughout the system with full stack traces and contextual information.

### Model Loading Errors

When models fail to load, the system logs:
- Model type (general, damage, id)
- Model file path
- Error type and message
- Full stack trace

Example log entry:
```
ERROR - Failed to load damage model from backend/Kaggle_CDD/best.pt: FileNotFoundError: Model file not found
```

### Inference Errors

When model inference fails, the system logs:
- Model type
- Error type and message
- Image shape (for debugging)
- Full stack trace

The system continues with remaining models for graceful degradation.

### OCR Errors

When OCR extraction fails, the system logs:
- Bounding box coordinates
- Error type and message
- Image shape
- Full stack trace

The system returns "UNKNOWN" as the container ID and continues processing.

### Database Errors

When database operations fail, the system logs:
- Operation type (persist_analysis, persist_video_analysis, upsert_container)
- Container ID or frame count
- Error type and message
- Full stack trace

Database transactions are rolled back on errors.

## Monitoring Metrics

The system collects comprehensive metrics for monitoring performance and reliability.

### Metrics Collected

1. **Model Loading Metrics**
   - Model status (loaded/failed) for each model
   - Load time for each model
   - Recorded at startup

2. **Inference Metrics**
   - Inference count per model
   - Average, min, max inference time per model
   - Total inference time per model
   - Recorded on each inference

3. **OCR Metrics**
   - Success count
   - Failure count
   - Success rate percentage
   - Average, min, max OCR time
   - Recorded on each OCR operation

4. **Detection Metrics**
   - Detection count per model source (general, damage, id)
   - Total detection count
   - Recorded on each detection

### Accessing Metrics

Metrics can be accessed via REST API endpoints:

#### Get All Metrics
```
GET /api/metrics
```

Returns all collected metrics including model status, inference times, OCR rates, and detection counts.

#### Get Model Metrics
```
GET /api/metrics/models
```

Returns model-specific metrics:
- Model loading status
- Model load times
- Inference statistics per model

#### Get OCR Metrics
```
GET /api/metrics/ocr
```

Returns OCR-specific metrics:
- Success/failure counts
- Success rate
- Timing statistics

#### Get Detection Metrics
```
GET /api/metrics/detections
```

Returns detection count metrics:
- Counts per model source
- Total detection count

#### Log Metrics Summary
```
POST /api/metrics/summary
```

Triggers a comprehensive metrics summary to be written to the application logs.

### Example Metrics Response

```json
{
  "startup_time": "2026-02-11T10:30:00.000Z",
  "models": {
    "model_status": {
      "general": true,
      "damage": true,
      "id": true
    },
    "model_load_time": {
      "general": 2.345,
      "damage": 1.876,
      "id": 1.654
    },
    "inference_stats": {
      "general": {
        "count": 150,
        "avg_time": 0.234,
        "min_time": 0.189,
        "max_time": 0.456,
        "total_time": 35.1
      },
      "damage": {
        "count": 150,
        "avg_time": 0.198,
        "min_time": 0.167,
        "max_time": 0.389,
        "total_time": 29.7
      },
      "id": {
        "count": 150,
        "avg_time": 0.156,
        "min_time": 0.134,
        "max_time": 0.298,
        "total_time": 23.4
      }
    }
  },
  "ocr": {
    "success_count": 45,
    "failure_count": 5,
    "total_count": 50,
    "success_rate": 90.0,
    "avg_time": 0.567,
    "min_time": 0.234,
    "max_time": 1.234
  },
  "detections": {
    "detection_counts": {
      "general": 234,
      "damage": 45,
      "id": 67
    },
    "total_detections": 346
  }
}
```

## Monitoring Best Practices

1. **Check Model Status at Startup**
   - Verify all models loaded successfully
   - Alert if any models failed to load

2. **Monitor Inference Times**
   - Track average inference times per model
   - Alert if times exceed thresholds (e.g., >3 seconds)

3. **Monitor OCR Success Rate**
   - Track OCR success rate over time
   - Alert if success rate drops below threshold (e.g., <70%)

4. **Monitor Detection Counts**
   - Track detection distribution across models
   - Identify anomalies in detection patterns

5. **Review Error Logs**
   - Regularly review error logs for patterns
   - Address recurring errors proactively

## Integration with Monitoring Tools

The metrics can be integrated with external monitoring tools:

1. **Prometheus**: Export metrics in Prometheus format
2. **Grafana**: Create dashboards for visualization
3. **CloudWatch**: Send metrics to AWS CloudWatch
4. **DataDog**: Send metrics to DataDog

Example integration (add to your monitoring setup):
```python
import requests

# Fetch metrics
response = requests.get("http://localhost:8000/api/metrics")
metrics = response.json()

# Send to monitoring service
# ... your monitoring integration code ...
```
