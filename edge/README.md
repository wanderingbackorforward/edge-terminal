# Shield Tunneling Edge Platform

Edge data infrastructure for real-time shield tunneling monitoring and control.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Data Pipeline](#data-pipeline)
- [Maintenance Scripts](#maintenance-scripts)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Overview

The Edge Platform provides:

- **Real-time Data Collection**: OPC UA, Modbus TCP, REST API collectors
- **Data Quality Pipeline**: Validation, calibration, interpolation, reasonableness checks
- **Ring-based Alignment**: Spatio-temporal aggregation of sensor data
- **Feature Engineering**: Derived indicators and ML-ready features
- **Local Storage**: SQLite with WAL mode for concurrent access
- **REST API**: Query interfaces for monitoring and integration
- **Cloud Synchronization**: Batch upload of ring summaries (Phase 2)

### Key Features

- ✅ High-frequency data collection (1 Hz, 86,400 samples/day/tag)
- ✅ <10ms ingestion latency
- ✅ Multi-protocol support (OPC UA, Modbus, REST)
- ✅ Comprehensive data quality pipeline
- ✅ Automatic ring boundary detection
- ✅ Time-lagged settlement association
- ✅ Background task scheduling
- ✅ Graceful error handling and recovery

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EDGE PLATFORM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   OPC UA     │  │  Modbus TCP  │  │   REST API   │          │
│  │  Collector   │  │  Collector   │  │  Collector   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┴──────────────────┘                  │
│                            │                                     │
│                   ┌────────▼────────┐                            │
│                   │ Data Quality    │                            │
│                   │    Pipeline     │                            │
│                   │ ┌─────────────┐ │                            │
│                   │ │ Threshold   │ │                            │
│                   │ │ Validation  │ │                            │
│                   │ └─────────────┘ │                            │
│                   │ ┌─────────────┐ │                            │
│                   │ │Interpolation│ │                            │
│                   │ └─────────────┘ │                            │
│                   │ ┌─────────────┐ │                            │
│                   │ │Reasonableness│ │                           │
│                   │ │   Checking  │ │                            │
│                   │ └─────────────┘ │                            │
│                   │ ┌─────────────┐ │                            │
│                   │ │ Calibration │ │                            │
│                   │ └─────────────┘ │                            │
│                   └────────┬────────┘                            │
│                            │                                     │
│                   ┌────────▼────────┐                            │
│                   │  Buffer Writer  │                            │
│                   │  (Batch Write)  │                            │
│                   └────────┬────────┘                            │
│                            │                                     │
│                   ┌────────▼────────┐                            │
│                   │  SQLite Database│                            │
│                   │   (WAL Mode)    │                            │
│                   │                 │                            │
│                   │ • plc_logs      │                            │
│                   │ • attitude_logs │                            │
│                   │ • monitoring_   │                            │
│                   │   logs          │                            │
│                   │ • ring_summary  │                            │
│                   └────────┬────────┘                            │
│                            │                                     │
│         ┌──────────────────┴────────────────┐                   │
│         │                                    │                   │
│  ┌──────▼────────┐                  ┌───────▼───────┐           │
│  │ Ring Alignment│                  │   REST API    │           │
│  │   Pipeline    │                  │   (FastAPI)   │           │
│  │               │                  │               │           │
│  │ • Detector    │                  │ • /rings      │           │
│  │ • Aggregators │                  │ • /manual-logs│           │
│  │ • Indicators  │                  │ • /health     │           │
│  │ • Settlement  │                  │               │           │
│  │ • Writer      │                  │               │           │
│  └───────────────┘                  └───────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- pip or uv package manager
- SQLite 3.35+ (with WAL support)

### Setup

```bash
# Navigate to edge directory
cd edge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data logs
```

## Configuration

### Data Sources

Edit `edge/config/sources.yaml` to configure data collectors:

```yaml
sources:
  plc_main:
    type: opcua
    enabled: true
    endpoint_url: "opc.tcp://192.168.1.10:4840"
    tags:
      - name: thrust_total
        unit: kN
      # ... more tags

  guidance_system:
    type: modbus
    enabled: true
    host: "192.168.1.100"
    port: 502
    registers:
      - name: pitch
        address: 100
        data_type: float32
      # ... more registers

  monitoring_api:
    type: rest
    enabled: true
    base_url: "http://192.168.1.200:8080/api/v1"
    endpoints:
      surface_settlement:
        path: "/sensors/settlement"
        poll_interval: 60
    authentication:
      type: bearer
      token_env_var: MONITORING_API_TOKEN
```

### Thresholds

Edit `edge/config/thresholds.yaml` to configure validation thresholds:

```yaml
thresholds:
  thrust_total:
    min: 0
    max: 30000
    warning_low: 5000
    warning_high: 25000
  # ... more thresholds
```

### Calibration

Edit `edge/config/calibration.yaml` for sensor calibration:

```yaml
calibrations:
  sensor_A123:
    type: linear
    offset: -2.5
    scale: 1.02
  # ... more calibrations
```

## Running the Application

### Development Mode

```bash
# Start the edge server
python -m edge.main

# Or with uvicorn for auto-reload
uvicorn edge.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Using uvicorn with workers
uvicorn edge.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or using gunicorn
gunicorn edge.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Environment Variables

```bash
export MONITORING_API_TOKEN="your-token-here"
export LOG_LEVEL="INFO"
export DB_PATH="data/edge.db"
```

## API Documentation

### Interactive Documentation

Once running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

### Key Endpoints

#### Health Check
```bash
GET /api/v1/health
```

Returns system health status, database connectivity, and resource usage.

#### List Rings
```bash
GET /api/v1/rings?page=1&page_size=20&sort_by=ring_number
```

Returns paginated list of ring summaries.

Query parameters:
- `page`: Page number (default: 1)
- `page_size`: Records per page (default: 20)
- `sort_by`: Sort field (default: ring_number)
- `sort_order`: asc/desc (default: desc)
- `completeness`: Filter by data completeness flag

#### Get Ring Details
```bash
GET /api/v1/rings/{ring_number}?include_counts=true
```

Returns detailed data for specific ring.

Query parameters:
- `include_counts`: Include raw data counts (default: false)

#### Submit Manual Logs
```bash
POST /api/v1/manual-logs

{
  "plc_logs": [...],
  "attitude_logs": [...],
  "monitoring_logs": [...],
  "operator_id": "operator_001"
}
```

Submit manual data entries.

## Data Pipeline

### Collection → Processing Flow

1. **Data Collection**
   - OPC UA: Subscription-based (1000ms interval)
   - Modbus: Polling-based (1.0s interval)
   - REST API: Polling-based (configurable per endpoint)

2. **Quality Pipeline**
   ```
   Raw Data → Threshold Validation → Interpolation →
   Reasonableness Check → Calibration → Quality Metrics
   ```

3. **Buffering**
   - Max buffer size: 10,000 records
   - Flush interval: 5 seconds
   - Flush threshold: 1,000 records
   - Overflow strategy: drop_oldest

4. **Database Write**
   - Batch inserts for performance
   - Transaction-based writes
   - WAL mode for concurrency

5. **Ring Alignment** (Background task, every 5 minutes)
   ```
   Detect Ring Boundaries → Aggregate PLC Data →
   Aggregate Attitude Data → Calculate Derived Indicators →
   Associate Settlement Data → Write Ring Summary
   ```

### Data Flow Diagram

```
Sensors → Collectors → Quality Pipeline → Buffer → Database
                                                       ↓
                                            Ring Alignment
                                                       ↓
                                              Ring Summaries
                                                       ↓
                                            Cloud Sync (Phase 2)
```

## Maintenance Scripts

### Batch Ring Alignment

Process multiple rings in batch:

```bash
# Align rings 100-200
python edge/scripts/batch_align_rings.py --start-ring 100 --end-ring 200

# Align specific rings
python edge/scripts/batch_align_rings.py --ring-list 100,101,105,110

# Re-align all rings (force reprocess)
python edge/scripts/batch_align_rings.py --all --force

# Align only incomplete rings
python edge/scripts/batch_align_rings.py --incomplete-only

# Dry run
python edge/scripts/batch_align_rings.py --start-ring 100 --end-ring 105 --dry-run
```

### Data Cleanup

Remove old data based on retention policies:

```bash
# Dry run to see what would be deleted
python edge/scripts/cleanup_old_data.py --dry-run

# Delete logs older than 90 days
python edge/scripts/cleanup_old_data.py --retention-days 90

# Delete synced data and vacuum
python edge/scripts/cleanup_old_data.py --delete-synced --vacuum

# Custom retention for different log types
python edge/scripts/cleanup_old_data.py --plc-retention 60 --monitoring-retention 180
```

## Testing

### Run All Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=edge --cov-report=html

# Run specific test module
pytest edge/tests/unit/test_threshold_validator.py

# Run integration tests
pytest edge/tests/integration/

# Run performance tests
pytest edge/tests/performance/
```

### Test Categories

- **Unit Tests** (`edge/tests/unit/`): Component-level tests
- **Integration Tests** (`edge/tests/integration/`): End-to-end pipeline tests
- **Performance Tests** (`edge/tests/performance/`): Latency and throughput tests
- **Contract Tests** (`edge/tests/contract/`): API contract validation

### Performance Targets

- ✅ <10ms per record ingestion latency
- ✅ >100 records/second throughput
- ✅ <2ms quality pipeline overhead per record

## Deployment

### Docker Deployment (Recommended)

```bash
# Build image
docker build -t shield-edge:latest -f edge/Dockerfile .

# Run container
docker run -d \
  --name shield-edge \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e MONITORING_API_TOKEN=your-token \
  shield-edge:latest
```

### Systemd Service

Create `/etc/systemd/system/shield-edge.service`:

```ini
[Unit]
Description=Shield Tunneling Edge Platform
After=network.target

[Service]
Type=simple
User=tunnel
WorkingDirectory=/opt/shield-tunneling-icp
ExecStart=/opt/shield-tunneling-icp/edge/venv/bin/uvicorn edge.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable shield-edge
sudo systemctl start shield-edge
sudo systemctl status shield-edge
```

### Monitoring

Monitor logs:

```bash
# Application logs
tail -f logs/edge.log

# Data collection logs
tail -f logs/data_collection.log

# Systemd logs (if using systemd)
sudo journalctl -u shield-edge -f
```

## Troubleshooting

### Common Issues

#### Database Locked Error

**Symptom**: `sqlite3.OperationalError: database is locked`

**Solution**:
- Ensure WAL mode is enabled (automatic in DatabaseManager)
- Check for long-running transactions
- Verify no external processes are locking the database

#### OPC UA Connection Failed

**Symptom**: `Failed to connect to OPC UA server`

**Solution**:
- Verify endpoint URL is correct
- Check network connectivity: `ping 192.168.1.10`
- Verify PLC is running and OPC UA server is enabled
- Check authentication credentials if required

#### High Memory Usage

**Symptom**: Process consuming excessive memory

**Solution**:
- Reduce buffer size in `sources.yaml`
- Lower flush threshold to write more frequently
- Check for memory leaks in custom code
- Monitor with: `ps aux | grep python`

#### Missing Data in Ring Summary

**Symptom**: Ring summary has NULL values for some fields

**Solution**:
- Check data completeness flag
- Verify sensors were recording during ring construction
- Check PLC logs: `SELECT COUNT(*) FROM plc_logs WHERE ring_number = 100`
- Review ring boundary detection logs

### Debug Mode

Enable debug logging:

```bash
# In code
export LOG_LEVEL=DEBUG

# Or in logging_config.py
setup_logging(log_level="DEBUG")
```

### Database Inspection

```bash
# Open database
sqlite3 data/edge.db

# Check table schemas
.schema plc_logs

# Count records
SELECT COUNT(*) FROM plc_logs;

# Check ring summaries
SELECT ring_number, data_completeness_flag FROM ring_summary;

# Exit
.quit
```

## Performance Optimization

### Database Tuning

```sql
-- Enable WAL mode (automatic)
PRAGMA journal_mode=WAL;

-- Increase cache size
PRAGMA cache_size=-64000;  -- 64MB

-- Synchronous mode
PRAGMA synchronous=NORMAL;
```

### Buffer Tuning

Adjust in `sources.yaml`:

```yaml
buffer:
  max_size: 10000      # Increase for higher throughput
  flush_interval: 5     # Decrease for lower latency
  flush_threshold: 1000 # Tune based on load
```

## License

Proprietary - Internal Use Only

## Support

For issues or questions:
- GitHub Issues: [Link to repo]
- Documentation: `/docs`
- Contact: [Your contact info]
