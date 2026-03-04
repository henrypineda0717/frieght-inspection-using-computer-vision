# Backend Restart Guide

## Changes Made

The OCR processor has been updated to properly extract ISO 6346 container IDs. The key fix was removing whitespace from OCR results before validation, as OCR engines sometimes add spaces between characters. The system now uses PaddleOCR v4 Mobile for superior text recognition accuracy.

## How to Restart the Backend

### Option 1: If running with uvicorn directly

```bash
# Stop the current server (Ctrl+C)
# Then restart:
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: If running with Python

```bash
# Stop the current server (Ctrl+C)
# Then restart:
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: If running as a service

```bash
# Restart the service (command depends on your setup)
sudo systemctl restart container-inspection
# or
pm2 restart container-inspection
```

## Verify the Changes

After restarting, you can verify the OCR is working by:

1. Upload an image with a container ID
2. Check the backend logs for OCR debug output (you'll see emoji indicators like 🔍, ✂️, 🤖, 📝, etc.)
3. The container ID should now be extracted and displayed in the frontend

## Expected Log Output

When processing an image with a container ID, you should see logs like:

```
INFO - 🔄 Aggregating X detections
INFO -    📊 ID detections: 1, Damage: 0, General: 5
INFO - 🆔 Processing ID detection at bbox: (x, y, w, h)
INFO - 🔍 Starting OCR extraction for bbox: (x, y, w, h)
INFO - ✂️  Cropped region shape: (h, w, 3)
INFO - 🤖 OCR engine loaded, running text detection...
INFO - 📝 OCR returned 1 text detections
INFO -    Detection 1: 'MSCU 1234567' (confidence: 0.85)
INFO - 🔤 Combined text (no space): 'MSCU 1234567'
INFO - 🧹 After removing whitespace: 'MSCU1234567'
INFO - ✅ Successfully extracted container ID: MSCU1234567
INFO -    Result: container_id = MSCU1234567
```

## Troubleshooting

### Container ID still shows as "UNKNOWN"

1. **Check if the ID model is detecting the container ID region**
   - Look for bounding boxes around the container ID in the image
   - If no bounding box, the ID detection model needs retraining

2. **Check the OCR logs**
   - Look for the emoji indicators in the logs
   - See what text the OCR is detecting
   - Verify the text matches ISO 6346 format (3 letters + U/J/Z + 7 digits)

3. **Check the container ID format**
   - Valid: MSCU1234567, TEMU9876543, ABCJ1234567
   - Invalid: ABCD1234567 (4 letters), MSC1234567 (only 2 letters)

### OCR is too slow

The OCR engine loads on first use and can take 5-10 seconds. Subsequent requests will be faster. To improve performance:

1. Enable GPU in config: `OCR_GPU: bool = True`
2. Reduce image size before OCR
3. Use a faster OCR engine

### Check digit warnings

You may see warnings like:
```
WARNING - Container ID MSCU1234567 has invalid check digit. Expected: 6, Got: 7
```

This means the OCR detected a container ID but the check digit doesn't match the ISO 6346 calculation. The system still returns the ID but logs a warning. This could indicate:
- OCR misread a digit
- The container ID is not a real ISO 6346 ID
- The check digit calculation needs adjustment

## Database Migration

The database has been updated with new ISO 6346 fields. If you haven't run the migration yet:

```bash
cd backend
python migrations/migration_002_add_iso6346_fields.py
```

Or run all migrations:

```bash
cd backend
python -m migrations.run_migrations upgrade
```
