# Container Inspection System - Getting Started Guide

This guide provides step-by-step instructions to set up and run the AI-powered Container Inspection System.

## 🚀 Quick Start (Docker)

If you have Docker and Docker Compose installed, you can start the entire system with one command:

```bash
docker-compose -f docker/docker-compose.yml up --build
```

The application will be available at [http://localhost:8001](http://localhost:8001).

---

## 🛠️ Manual Installation

### Prerequisites
- **Python**: 3.8 or higher
- **OS**: Linux (tested on Ubuntu/Debian) or Windows
- **Disk Space**: ~2GB for models and dependencies

### 1. Clone & Set Up Environment
```bash
# Create and activate virtual environment
# Linux/macOS:
python3 -m venv .venv
source .venv/bin/activate

# Windows:
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install Dependencies
Install the required packages from the root directory:
```bash
pip install -r requirements.txt
```

### 3. Model Preparation
Ensure the following YOLO models are in place (the system will attempt to load them on startup):
- `models/yolov8n.pt` (General detection)
- `models/container_front.pt` (Damage/Front detection)
- `models/checkpoint_best_ema.pth` (RT-DETR model)

### 4. Configuration
Create a `.env` file in the `backend` directory (or use the one provided):
```bash
DATABASE_URL=sqlite:///./inspections.db
DEBUG=True
PORT=8001
```

### 5. Start the Application
Run the backend server from the root directory:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend  # Linux
set PYTHONPATH=%PYTHONPATH%;%cd%\backend      # Windows (CMD)

python backend/app/main.py
```
Alternatively, using uvicorn directly:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

## 🖥️ Using the Application

### 1. Dashboard (Live Analysis)
Navigate to **[http://localhost:8001](http://localhost:8001)**
- **Upload**: Drag and drop or click "Choose" to load an image or video.
- **Select Options**: Choose "Pre Wash" or "Post Wash" stage and "Exterior" or "Interior" view.
- **Analyze**: 
  - For **images**: Click "Analyze Image".
  - For **videos**: Click "Start Session" to begin real-time 25+ FPS analysis.
- **Save**: Click "Save to Database" to archive the results.

### 2. History Page
Navigate to **[http://localhost:8001/history.html](http://localhost:8001/history.html)**
- **Audit**: Review all past inspections with real-time statistics (Total Inspections, Unique Containers, etc.).
- **Details**: Click on any record to see full-frame overlays and specific defect detections.
- **Reports**: Download professional PDF reports for any inspection.
- **Maintenance**: Use the "Cleanup" button to remove orphaned container records.

---

## 🧪 Development & Testing

### Running Tests
```bash
pytest backend/tests
```

### API Documentation
Interactive documentation is available at:
- **Swagger UI**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **ReDoc**: [http://localhost:8001/redoc](http://localhost:8001/redoc)

---

## ❓ Troubleshooting

### Port Conflicts
If port 8001 is busy, change the port in `backend/app/config.py` or use the `--port` flag with uvicorn.

### GPU Acceleration
The system supports GPU acceleration (FP16). Ensure you have appropriate NVIDIA drivers and `torch` with CUDA support installed if you wish to use GPU.

### Database Issues
If the database seems inconsistent, you can run the migrations manually:
```bash
python backend/migrations/run_migrations.py
```

---
**MCS Robotics**  
*Support: support@mcsrobotics.com*
