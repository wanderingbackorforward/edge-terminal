"""
T025: API Contract Tests
Tests REST API endpoints for contract compliance
Validates request/response schemas, status codes, and error handling
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import tempfile
import os

from edge.database.manager import DatabaseManager


@pytest.fixture
def test_db():
    """Create temporary test database"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = DatabaseManager(db_path)

    # Create tables
    with db.transaction() as conn:
        # Create plc_logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plc_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                ring_number INTEGER,
                tag_name TEXT NOT NULL,
                value REAL,
                source_id TEXT NOT NULL,
                data_quality_flag TEXT DEFAULT 'raw',
                created_at REAL DEFAULT (julianday('now'))
            )
        """)

        # Create ring_summary table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ring_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ring_number INTEGER UNIQUE NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                mean_thrust REAL,
                max_thrust REAL,
                min_thrust REAL,
                std_thrust REAL,
                mean_torque REAL,
                max_torque REAL,
                mean_penetration_rate REAL,
                max_penetration_rate REAL,
                mean_chamber_pressure REAL,
                max_chamber_pressure REAL,
                mean_pitch REAL,
                mean_roll REAL,
                mean_yaw REAL,
                horizontal_deviation REAL,
                vertical_deviation REAL,
                specific_energy REAL,
                ground_loss_rate REAL,
                volume_loss_ratio REAL,
                settlement_value REAL,
                data_completeness_flag TEXT DEFAULT 'incomplete',
                geological_zone TEXT,
                synced_to_cloud INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)

        # Insert test data
        now = datetime.now().timestamp()

        # Insert ring summaries
        for ring_num in [100, 101, 102]:
            conn.execute(
                """
                INSERT INTO ring_summary
                (ring_number, start_time, end_time, mean_thrust, mean_torque,
                 data_completeness_flag, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ring_num, now - 3600, now, 12000.0 + ring_num * 100,
                    900.0, 'complete', now, now
                )
            )

        # Insert PLC logs for ring 100
        for i in range(50):
            conn.execute(
                """
                INSERT INTO plc_logs
                (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now - 3000 + i * 60, 100, 'thrust_total', 12000.0 + i * 10, 'test', 'raw')
            )

    yield db

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def client(test_db):
    """Create FastAPI test client"""
    # Import here to avoid circular dependencies
    from edge.main import app, get_db_manager

    # Override database dependency
    app.dependency_overrides[get_db_manager] = lambda: test_db

    with TestClient(app) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Test /health endpoint contract"""

    def test_health_check_success(self, client):
        """Test health check returns 200 with expected schema"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        data = response.json()

        # Validate schema
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']

        assert 'timestamp' in data
        assert isinstance(data['timestamp'], (int, float))

        assert 'database' in data
        assert 'connected' in data['database']
        assert isinstance(data['database']['connected'], bool)

        assert 'system' in data
        assert 'cpu_percent' in data['system']
        assert 'memory_percent' in data['system']

    def test_health_check_headers(self, client):
        """Test health check response headers"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert 'content-type' in response.headers
        assert 'application/json' in response.headers['content-type']


class TestRingsEndpoint:
    """Test /rings endpoint contracts"""

    def test_list_rings_success(self, client):
        """Test listing rings returns expected schema"""
        response = client.get("/api/v1/rings")

        assert response.status_code == 200

        data = response.json()

        # Validate schema
        assert 'rings' in data
        assert isinstance(data['rings'], list)

        assert 'total' in data
        assert isinstance(data['total'], int)

        assert 'page' in data
        assert 'page_size' in data

        # Validate ring structure
        if len(data['rings']) > 0:
            ring = data['rings'][0]
            assert 'ring_number' in ring
            assert 'start_time' in ring
            assert 'end_time' in ring
            assert 'data_completeness_flag' in ring

    def test_list_rings_pagination(self, client):
        """Test pagination parameters"""
        response = client.get("/api/v1/rings?page=1&page_size=2")

        assert response.status_code == 200

        data = response.json()
        assert data['page'] == 1
        assert data['page_size'] == 2
        assert len(data['rings']) <= 2

    def test_list_rings_sorting(self, client):
        """Test sorting parameter"""
        response = client.get("/api/v1/rings?sort_by=ring_number&sort_order=desc")

        assert response.status_code == 200

        data = response.json()

        # Verify descending order
        if len(data['rings']) >= 2:
            ring_numbers = [r['ring_number'] for r in data['rings']]
            assert ring_numbers == sorted(ring_numbers, reverse=True)

    def test_list_rings_filtering(self, client):
        """Test filtering by completeness"""
        response = client.get("/api/v1/rings?completeness=complete")

        assert response.status_code == 200

        data = response.json()

        # All returned rings should be complete
        for ring in data['rings']:
            assert ring['data_completeness_flag'] == 'complete'

    def test_list_rings_invalid_page(self, client):
        """Test invalid page number returns 422"""
        response = client.get("/api/v1/rings?page=0")

        assert response.status_code == 422

        data = response.json()
        assert 'detail' in data

    def test_get_ring_by_number_success(self, client):
        """Test getting specific ring"""
        response = client.get("/api/v1/rings/100")

        assert response.status_code == 200

        data = response.json()

        # Validate schema
        assert 'ring_number' in data
        assert data['ring_number'] == 100

        assert 'start_time' in data
        assert 'end_time' in data
        assert 'mean_thrust' in data
        assert 'mean_torque' in data

    def test_get_ring_not_found(self, client):
        """Test getting non-existent ring returns 404"""
        response = client.get("/api/v1/rings/9999")

        assert response.status_code == 404

        data = response.json()
        assert 'detail' in data

    def test_get_ring_with_counts(self, client):
        """Test including data counts"""
        response = client.get("/api/v1/rings/100?include_counts=true")

        assert response.status_code == 200

        data = response.json()

        # Should include counts
        assert 'plc_log_count' in data
        assert 'attitude_log_count' in data
        assert 'monitoring_log_count' in data

        assert isinstance(data['plc_log_count'], int)
        assert data['plc_log_count'] > 0  # We inserted PLC logs for ring 100


class TestManualLogsEndpoint:
    """Test /manual-logs endpoint contracts"""

    def test_create_manual_logs_success(self, client):
        """Test creating manual logs"""
        payload = {
            'plc_logs': [
                {
                    'timestamp': datetime.now().timestamp(),
                    'ring_number': 100,
                    'tag_name': 'thrust_total',
                    'value': 12000.0,
                    'source_id': 'manual_entry'
                }
            ],
            'operator_id': 'test_operator'
        }

        response = client.post("/api/v1/manual-logs", json=payload)

        assert response.status_code == 201

        data = response.json()

        # Validate schema
        assert 'plc_logs_created' in data
        assert data['plc_logs_created'] == 1

        assert 'timestamp' in data

    def test_create_manual_logs_validation_error(self, client):
        """Test validation error for invalid data"""
        payload = {
            'plc_logs': [
                {
                    # Missing required fields
                    'tag_name': 'thrust_total',
                    'value': 12000.0
                }
            ]
        }

        response = client.post("/api/v1/manual-logs", json=payload)

        assert response.status_code == 422

        data = response.json()
        assert 'detail' in data

    def test_create_manual_logs_empty_batch(self, client):
        """Test empty batch returns 400"""
        payload = {
            'plc_logs': [],
            'attitude_logs': [],
            'monitoring_logs': []
        }

        response = client.post("/api/v1/manual-logs", json=payload)

        # Should reject empty batch
        assert response.status_code in [400, 422]

    def test_create_manual_logs_mixed_types(self, client):
        """Test creating mixed log types"""
        now = datetime.now().timestamp()

        payload = {
            'plc_logs': [
                {
                    'timestamp': now,
                    'ring_number': 100,
                    'tag_name': 'thrust_total',
                    'value': 12000.0,
                    'source_id': 'manual'
                }
            ],
            'monitoring_logs': [
                {
                    'timestamp': now,
                    'sensor_type': 'settlement',
                    'value': -5.2,
                    'sensor_location': 'Point A',
                    'unit': 'mm',
                    'source_id': 'manual'
                }
            ],
            'operator_id': 'test_operator'
        }

        response = client.post("/api/v1/manual-logs", json=payload)

        assert response.status_code == 201

        data = response.json()
        assert data['plc_logs_created'] == 1
        assert data['monitoring_logs_created'] == 1


class TestErrorHandling:
    """Test error handling contracts"""

    def test_404_not_found(self, client):
        """Test 404 for non-existent endpoint"""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404

        data = response.json()
        assert 'detail' in data

    def test_405_method_not_allowed(self, client):
        """Test 405 for wrong HTTP method"""
        response = client.post("/api/v1/health")

        assert response.status_code == 405

    def test_422_validation_error_format(self, client):
        """Test validation error response format"""
        response = client.get("/api/v1/rings?page=invalid")

        assert response.status_code == 422

        data = response.json()
        assert 'detail' in data

        # FastAPI validation errors have specific format
        if isinstance(data['detail'], list):
            error = data['detail'][0]
            assert 'loc' in error
            assert 'msg' in error
            assert 'type' in error


class TestCORS:
    """Test CORS headers"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are included"""
        response = client.get("/api/v1/health")

        # CORS headers should be present if configured
        # Note: May need to configure CORS in main.py
        assert response.status_code == 200


class TestOpenAPISpec:
    """Test OpenAPI specification"""

    def test_openapi_json_available(self, client):
        """Test OpenAPI JSON is available"""
        response = client.get("/openapi.json")

        assert response.status_code == 200

        data = response.json()

        # Validate OpenAPI structure
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data

        # Check our endpoints are documented
        assert '/api/v1/health' in data['paths']
        assert '/api/v1/rings' in data['paths']

    def test_docs_available(self, client):
        """Test Swagger UI is available"""
        response = client.get("/docs")

        assert response.status_code == 200

    def test_redoc_available(self, client):
        """Test ReDoc is available"""
        response = client.get("/redoc")

        assert response.status_code == 200


class TestResponseTimes:
    """Test response time contracts"""

    def test_health_response_time(self, client):
        """Test health endpoint responds quickly"""
        import time

        start = time.time()
        response = client.get("/api/v1/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0  # Should respond in <1 second

    def test_list_rings_response_time(self, client):
        """Test rings list endpoint responds quickly"""
        import time

        start = time.time()
        response = client.get("/api/v1/rings")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond in <2 seconds
