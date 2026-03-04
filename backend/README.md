# Backend - Container Inspection System

## Overview

FastAPI-based backend application for container inspection with AI-powered analysis.

## Structure

```
backend/
├── app/
│   ├── api/          # API route handlers
│   ├── core/         # Core functionality
│   ├── models/       # Database ORM models
│   ├── schemas/      # Pydantic validation schemas
│   ├── services/     # Business logic layer
│   ├── utils/        # Utility functions
│   ├── config.py     # Configuration management
│   ├── database.py   # Database setup
│   └── main.py       # Application entry point
├── tests/            # Test suite
├── .env.example      # Environment variables template
└── requirements.txt  # Python dependencies
```

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Initialize Database

```bash
python -c "from app.database import init_db; init_db()"
```

### 4. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### Key Endpoints

#### Video Analysis
- `POST /api/analysis/analyze-video-realtime` - **NEW**: Optimized real-time video processing
  - Threaded pipeline for smooth 25+ FPS playback
  - ByteTrack for continuously updating bounding boxes
  - FP16 GPU acceleration support
  - See [REALTIME_QUICKSTART.md](../docs/REALTIME_QUICKSTART.md) for details
- `POST /api/analysis/analyze-video` - Standard video analysis
- `POST /api/analysis/analyze-frame-realtime` - Single frame analysis

#### Image Analysis
- `POST /api/analysis/` - Analyze single image

#### History & Reports
- `GET /api/history/` - Query inspection history
- `POST /api/analysis/generate-report` - Generate PDF report
- `POST /api/analysis/save-analysis` - Save analysis results

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_analysis.py -v
```

## Code Quality

```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

## Environment Variables

See `.env.example` for all available configuration options.

### Required
- `DATABASE_URL` - Database connection string

### Optional
- `OPENAI_API_KEY` - For GPT vision/text features
- `DEBUG` - Enable debug mode
- `USE_OPENAI_VISION` - Enable/disable OpenAI vision
- `USE_OPENAI_TEXT` - Enable/disable OpenAI text

## Architecture

### Layers

1. **API Layer** (`app/api/`) - HTTP request handling
2. **Service Layer** (`app/services/`) - Business logic
3. **Model Layer** (`app/models/`) - Database entities
4. **Schema Layer** (`app/schemas/`) - Data validation

### Key Components

- **Analysis Service**: YOLO detection, OCR, GPT integration
- **Persistence Service**: Database operations
- **Storage Service**: Image archiving
- **History Service**: Query past inspections
- **Real-time Video Processor**: Multi-threaded pipeline with ByteTrack tracking (NEW)
  - Separate threads for capture, inference, and display
  - Smooth 25+ FPS playback with continuously updating bounding boxes
  - FP16 GPU acceleration for 2x speedup
  - See [REALTIME_VIDEO_OPTIMIZATION.md](../docs/REALTIME_VIDEO_OPTIMIZATION.md)

## Development

### Adding New Endpoints

1. Create route handler in `app/api/`
2. Define schemas in `app/schemas/`
3. Implement business logic in `app/services/`
4. Add tests in `tests/`

### Database Migrations

For schema changes:
1. Update models in `app/models/`
2. Create migration script (if using Alembic)
3. Run migration

## Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Configure proper CORS origins
- [ ] Set up authentication
- [ ] Enable HTTPS
- [ ] Configure logging
- [ ] Set up monitoring

### Using Gunicorn

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Troubleshooting

### Database Issues

**Problem**: Database locked
**Solution**: Use PostgreSQL for production

**Problem**: Tables not created
**Solution**: Run `init_db()` or check migrations

### Import Errors

**Problem**: Module not found
**Solution**: Ensure PYTHONPATH includes project root

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
```

## Support

For issues or questions:
- Check main project README
- Review API documentation at `/docs`
- Check logs for error messages
