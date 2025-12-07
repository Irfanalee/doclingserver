# DoclingServer - Production-Grade PDF Analysis Microservice

A containerized FastAPI microservice for AI-powered PDF document analysis using IBM's Docling library. Extracts text, tables, images, and generates structured markdown output with document intelligence.

## Features

### AI-Powered Document Analysis
- **Advanced Table Detection**: ML-based table extraction with structure preservation
- **OCR Capabilities**: Text extraction from scanned documents and images
- **Layout Understanding**: Intelligent document structure analysis (headers, paragraphs, lists)
- **Multi-format Export**: Markdown, JSON summaries, CSV tables, extracted images
- **Document Statistics**: Page counts, word counts, processing metrics

### Production-Grade API
- **FastAPI Framework**: Async-ready, auto-documented REST API
- **Health Probes**: Kubernetes-ready liveness and readiness endpoints
- **Structured Logging**: JSON-formatted logs for centralized monitoring
- **Error Handling**: Proper HTTP status codes and validation
- **CORS Support**: Configurable cross-origin resource sharing
- **File Validation**: Size limits, type checking, secure uploads

### Container Features
- **Multi-stage Build**: Optimized 1.84GB Docker image
- **Non-root User**: Security-hardened container execution
- **Volume Mounts**: Persistent storage for outputs and model cache
- **Resource Limits**: CPU/memory constraints for production deployment
- **Health Checks**: Built-in container health monitoring

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- 4GB+ available RAM
- 10GB+ disk space

### Run with Docker Compose

```bash
# Clone the repository
git clone <your-repo-url>
cd DoclingServer

# Copy environment template
cp .env.example .env

# Start the service
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
```

The API will be available at http://localhost:8000

### Run with Docker Only

```bash
# Build the image
docker build -t docling-server:local .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data/input:ro \
  -v $(pwd)/output:/app/data/output \
  --name docling-api \
  docling-server:local

# Check status
docker logs docling-api
```

## API Documentation

### Interactive API Docs
Once running, access the auto-generated Swagger documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### Health Check (Liveness Probe)
```bash
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2025-12-07T10:30:00Z",
  "version": "1.0.0"
}
```

#### Readiness Check (Kubernetes Readiness Probe)
```bash
GET /ready

Response:
{
  "status": "ready",
  "docling_ready": true,
  "storage_ready": true
}
```

#### Analyze PDF Document
```bash
POST /api/v1/analyze
Content-Type: multipart/form-data

Parameters:
  file: PDF file (max 100MB)

Example:
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@/path/to/document.pdf"

Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "processing_time_seconds": 12.34,
  "results": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "markdown_path": "/app/data/output/550e8400.../document.md",
    "summary_path": "/app/data/output/550e8400.../document_summary.json",
    "tables": [
      "/app/data/output/550e8400.../document_table_1.csv",
      "/app/data/output/550e8400.../document_table_2.csv"
    ],
    "images_dir": "/app/data/output/550e8400.../document_images"
  }
}
```

#### Root Information
```bash
GET /

Response:
{
  "service": "Document Analyzer API",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs",
  "health": "/health",
  "api": "/api/v1/analyze"
}
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
# Server Configuration
HOST=0.0.0.0              # Listen address
PORT=8000                 # HTTP port
WORKERS=1                 # Uvicorn workers (1 for development)
LOG_LEVEL=INFO            # Logging level (DEBUG, INFO, WARNING, ERROR)

# Storage Configuration
OUTPUT_DIR=/app/data/output     # Results directory
TEMP_DIR=/app/data/temp         # Temporary upload storage
MAX_FILE_SIZE_MB=100            # Maximum upload size

# Processing
DOCLING_CACHE_DIR=/app/.docling # Model cache directory

# CORS
CORS_ORIGINS=*                  # Allowed origins (* for all)
```

### Docker Compose Overrides

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'

services:
  api:
    environment:
      - LOG_LEVEL=DEBUG
    volumes:
      # Hot-reload for development
      - ./api_server.py:/app/api_server.py
      - ./document_analyzer.py:/app/document_analyzer.py
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

## Testing

### Automated Test Suite

Run the comprehensive test script:

```bash
chmod +x test/test_api.sh
./test/test_api.sh
```

Tests include:
- Container health check
- Health endpoint validation
- Readiness endpoint validation
- Root endpoint validation
- API documentation accessibility
- PDF analysis (with sample file)
- Invalid file type rejection
- Container log inspection

### Manual Testing

```bash
# Test with your own PDF
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@your-document.pdf" \
  | jq '.'

# Test error handling (invalid file)
echo "not a pdf" > test.txt
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@test.txt"
```

### Expected Response Times
- Small PDFs (< 10 pages): 5-15 seconds
- Medium PDFs (10-50 pages): 30-90 seconds
- Large PDFs (50+ pages): 2-5 minutes

## Development

### Local Development without Docker

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python api_server.py
```

### Hot-Reload Development

Uncomment volume mounts in `docker-compose.yml`:

```yaml
volumes:
  - ./api_server.py:/app/api_server.py
  - ./document_analyzer.py:/app/document_analyzer.py
```

Then restart:
```bash
docker-compose restart api
```

### Rebuild After Code Changes

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Directory Structure

```
DoclingServer/
├── api_server.py              # FastAPI application
├── document_analyzer.py       # Core PDF processing logic
├── requirements.txt           # Python dependencies (123 packages)
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Local orchestration
├── .env.example               # Configuration template
├── .dockerignore              # Docker build exclusions
├── .gitignore                 # Git exclusions
├── data/                      # Input PDFs directory (mounted read-only)
├── output/                    # Results directory (mounted read-write)
├── test/
│   └── test_api.sh           # Automated test script
└── KUBERNETES_DEPLOYMENT_GUIDE.md  # K8s deployment guide
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs api

# Common issues:
# - Port 8000 already in use: Change PORT in .env
# - Out of memory: Increase Docker memory limit to 4GB+
# - Permission errors: Check output/ directory permissions
```

### "Service not ready" error

```bash
# Wait for model initialization (can take 30-60 seconds on first start)
docker-compose logs -f api

# Check readiness
curl http://localhost:8000/ready
```

### Large PDFs timeout

```bash
# Increase timeout in docker-compose.yml:
healthcheck:
  timeout: 30s  # Increase from 10s

# Or use async processing (planned for Week 2)
```

### Out of disk space

```bash
# Clean up old job outputs
rm -rf output/*

# Prune Docker cache
docker system prune -a
```

## Performance Tuning

### Resource Allocation

Adjust in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'      # More CPUs = faster processing
      memory: 8G     # More memory = larger PDFs
    reservations:
      cpus: '2'
      memory: 4G
```

### Model Caching

First run downloads ML models (~500MB). Subsequent runs use cached models from the persistent volume `docling-cache`.

### Concurrent Processing

Increase workers for parallel requests:

```bash
# In .env
WORKERS=4  # Handle 4 concurrent requests
```

**Note**: Each worker uses ~2GB RAM. Total memory = WORKERS × 2GB.

## Production Deployment

### Container Registry

```bash
# Tag for registry
docker tag docling-server:local yourusername/docling-server:v1.0.0

# Push to Docker Hub
docker push yourusername/docling-server:v1.0.0

# Or push to private registry
docker tag docling-server:local registry.example.com/docling-server:v1.0.0
docker push registry.example.com/docling-server:v1.0.0
```

### Kubernetes Deployment

See [KUBERNETES_DEPLOYMENT_GUIDE.md](KUBERNETES_DEPLOYMENT_GUIDE.md) for:
- Deployment manifests
- Persistent volume configuration
- Horizontal pod autoscaling
- GPU support (planned)
- Monitoring setup

### Security Considerations

- **Non-root execution**: Container runs as UID 1000
- **Read-only input**: Data directory mounted read-only
- **Size limits**: MAX_FILE_SIZE_MB prevents resource exhaustion
- **CORS configuration**: Restrict CORS_ORIGINS in production
- **No authentication**: Add API keys/OAuth for production use

## Architecture

### Tech Stack
- **Python 3.11**: Runtime environment
- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **Docling**: Document analysis library (IBM Watson)
- **PyTorch**: ML model backend
- **PyMuPDF**: PDF processing
- **Pandas**: Table data manipulation

### Processing Pipeline
1. File upload validation (type, size)
2. Temporary storage in TEMP_DIR
3. Docling document conversion (ML models)
4. Table extraction → CSV files
5. Image extraction → images directory
6. Markdown conversion → .md file
7. Summary generation → JSON file
8. Results returned with job ID
9. Temporary file cleanup

### Data Flow
```
Client → POST /api/v1/analyze
  ↓
FastAPI validation
  ↓
Save to /app/data/temp/{job_id}_{filename}
  ↓
DocumentAnalyzer.analyze()
  ↓
Docling ML models (table detection, OCR, layout)
  ↓
Export results to /app/data/output/{job_id}/
  ↓
Return job metadata + file paths
  ↓
Cleanup temp file
```

## Monitoring

### Container Health
```bash
# Check container status
docker ps --filter name=docling-api

# Check health probe
docker inspect --format='{{.State.Health.Status}}' docling-api
```

### Application Logs
```bash
# Follow logs
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail 100 api

# JSON log parsing
docker-compose logs api | jq '.'
```

### Metrics (Planned)
Future releases will include:
- Prometheus metrics endpoint (`/metrics`)
- Request counts and latencies
- Processing time histograms
- Error rates

## Roadmap

### Week 2: Kubernetes & Monitoring
- Deploy to local K8s (minikube/kind)
- Horizontal pod autoscaling
- Prometheus + Grafana dashboards
- Persistent volume claims

### Week 3: Async Processing
- Redis job queue
- Separate API and worker pods
- Job status polling endpoint
- Webhook callbacks

### Week 4: GPU Support
- NVIDIA GPU deployment variant
- CUDA-optimized Dockerfile
- Performance benchmarking
- Cost analysis (CPU vs GPU)

### Future Enhancements
- API key authentication
- Rate limiting
- Multi-tenant isolation
- S3/GCS storage backends
- Webhook notifications
- Batch processing API

## Contributing

### Code Style
- Follow PEP 8 conventions
- Type hints for all functions
- Docstrings for public APIs

### Testing
- Add tests for new features
- Run test suite before commits
- Update test/test_api.sh if adding endpoints

## License

[Add your license here]

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/DoclingServer/issues)
- **Documentation**: See `/docs` endpoint when running
- **Docling Library**: https://github.com/DS4SD/docling

## Acknowledgments

- **Docling**: IBM Research's document understanding library
- **FastAPI**: Modern Python web framework
- **PyTorch**: Deep learning platform

---

**Version**: 1.0.0
**Last Updated**: 2025-12-07
**Docker Image Size**: 1.84GB
**Python Version**: 3.11
**Production Ready**: ✅ Local Docker | ⏳ Kubernetes (Week 2)
