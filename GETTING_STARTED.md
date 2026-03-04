# Container Inspection System - Getting Started Guide

Quick guide to get the Container Inspection System up and running.

## Prerequisites

- Python 3.8 or higher
- Windows OS (current setup)
- Web browser (Chrome, Edge, or Firefox)

## Installation Steps

### 1. Set Up Python Environment

Open PowerShell or Command Prompt and navigate to the project directory:

```cmd
cd E:\AntonProject\Code
```

Create and activate a virtual environment:

```cmd
python -m venv .venv
.venv\Scripts\Activate
```

### 2. Install Dependencies

Navigate to the backend folder and install required packages:

```cmd
cd backend
pip install -r requirements.txt
```

This will install FastAPI, YOLO models, and all necessary dependencies.

### 3. Start the Backend Server

From the `backend` directory, start the server:

```cmd
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

You should see output like:
```
INFO:     Started server process
✓ Database initialized
✓ Models loaded: 3/3
✓ Container Inspection System v2.0.0 started
INFO:     Application startup complete.
```

**Note**: If port 8001 is already in use, you'll see an error. Either:
- Stop the process using that port, or
- Use a different port (e.g., `--port 8002`) and update the frontend accordingly

## Accessing the Application

Once the backend is running, open your web browser and navigate to:

- **Live Analysis Page**: http://localhost:8001/
- **History Page**: http://localhost:8001/history.html

## Using the System

### Live Analysis Page

1. **Upload Media**: Click "Choose File" to upload an image or video
2. **Analyze**: Click "Analyze frame" to process the current frame
3. **Auto Mode**: Click "Auto: off" to enable automatic frame analysis
4. **Learning Mode**: Enable to save training data for custom models
5. **Inspection Stages**: Mark frames as "Pre wash" or "Post wash" to compare results

### History Page

1. View all past inspections
2. Search and filter by container ID, date, or status
3. Click on any inspection to view detailed results
4. Download reports or view archived images

## Configuration Options

### Analysis Settings (on Live Analysis page)

- **Damage sensitivity**: Adjust detection threshold (low/medium/high)
- **Dark spots**: Configure mold detection (auto/mold_only/off)
- **Vision backend**: Choose AI vision provider (auto/none/openai/llava)
- **GPT options**: Enable/disable GPT-powered analysis

### Inspection Stages

- **None**: Standard analysis without stage tracking
- **Pre wash**: Mark inspection before cleaning
- **Post wash**: Mark inspection after cleaning (shows resolved issues)

## Troubleshooting

### Port Already in Use

**Error**: `[winerror 10048] only one usage of each socket address is normally permitted`

**Solution**: 
```cmd
# Find process using the port
netstat -ano | findstr :8001

# Kill the process (replace <PID> with actual process ID)
taskkill /PID <PID> /F

# Or use a different port
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### Browser Shows "ERR_UNSAFE_PORT"

**Problem**: Some ports (like 6000) are blocked by browsers for security.

**Solution**: Use a safe port like 8001, 8002, or 8080.

### Backend Not Connecting

**Problem**: Frontend shows "Backend: not tested" or connection errors.

**Solution**:
1. Verify backend is running (check PowerShell window)
2. Check the port number matches in both backend and frontend
3. Try accessing http://localhost:8001/docs to verify API is working

### Models Not Loading

**Problem**: Backend fails to load YOLO models.

**Solution**:
1. Ensure model files exist in:
   - `models/yolov8n.pt` (general model)
   - `backend/Kaggle_CDD/container_damage_detection.pt` (damage model)
   - `backend/Container_id_Detection/best.pt` (ID model)
2. Check file paths in backend logs

## Stopping the Application

To stop the backend server:
1. Go to the PowerShell/Command Prompt window running the server
2. Press `Ctrl + C`
3. Deactivate the virtual environment: `deactivate`

## Advanced Features

### Learning Mode

Enable Learning Mode to train custom YOLO models:
1. Click "Learning: off" to enable
2. Draw bounding boxes on images
3. Select appropriate labels
4. Click "Train YOLO now" to train the model

### Report Generation

After analyzing a container:
1. Click "💾 Save to Database" to store results
2. Click "📄 Download Report" to generate a PDF report

### Pre/Post Wash Comparison

1. Analyze a container and mark as "Pre wash"
2. Analyze the same container after cleaning
3. Mark as "Post wash"
4. System automatically shows resolved issues

## API Documentation

For developers, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## Support

For issues or questions:
- Check backend logs in the PowerShell window
- Check browser console (F12) for frontend errors
- Review the detailed README files in `backend/` and `frontend/` folders

## System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB for models and dependencies
- **GPU**: Optional, but recommended for faster processing
- **Network**: Internet connection required for GPT features (optional)
