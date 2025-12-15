# Shield Tunneling Edge Platform - Deployment Guide

Complete guide for deploying the Edge Platform in production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Prerequisites

### Hardware Requirements

**Minimum (Development)**:
- CPU: 2 cores
- RAM: 2 GB
- Storage: 20 GB SSD
- Network: 100 Mbps Ethernet

**Recommended (Production)**:
- CPU: 4 cores
- RAM: 4 GB
- Storage: 50 GB SSD (for data retention)
- Network: 1 Gbps Ethernet
- UPS: For power redundancy

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Git (for deployment)
- curl (for health checks)

### Network Requirements

Access to:
- PLC system (OPC UA): `opc.tcp://192.168.1.10:4840`
- Guidance system (Modbus TCP): `192.168.1.100:502`
- Monitoring API (REST): `http://192.168.1.200:8080`
- Internet (for Docker images and cloud sync)

---

## Quick Start

### 1. Clone Repository

```bash
cd /opt
git clone <repository-url> shield-tunneling-icp
cd shield-tunneling-icp
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration
nano .env
```

Update the following:
```bash
MONITORING_API_TOKEN=your-actual-token-here
OPCUA_ENDPOINT=opc.tcp://192.168.1.10:4840
MODBUS_HOST=192.168.1.100
EDGE_UID=$(id -u)
EDGE_GID=$(id -g)
```
> **Note:** `EDGE_UID`/`EDGE_GID` ensure the container user matches your host account.
> This keeps bind-mounted configuration files (e.g., `edge/config/*.yaml`) readable
> even if your host `umask` defaults to `077`.

### 3. Configure Data Sources

```bash
# Edit sources configuration
nano edge/config/sources.yaml
```

Update endpoint URLs and enable/disable sources as needed.

### 4. Start Services

```bash
# Development mode
docker-compose up -d

# Production mode (with nginx)
docker-compose --profile production up -d

# With monitoring
docker-compose --profile production --profile monitoring up -d
```

### 5. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/api/v1/health

# View logs
docker-compose logs -f edge

# Check container status
docker-compose ps
```

---

## Production Deployment

### Step 1: System Preparation

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Directory Structure

```bash
# Create deployment directory
sudo mkdir -p /opt/shield-tunneling-icp
sudo chown $USER:$USER /opt/shield-tunneling-icp
cd /opt/shield-tunneling-icp

# Create SSL directory (if using HTTPS)
mkdir -p deployment/ssl
```

### Step 3: SSL Certificates (Optional)

For HTTPS access:

```bash
# Using Let's Encrypt
sudo apt-get install certbot
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deployment/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem deployment/ssl/key.pem
sudo chown $USER:$USER deployment/ssl/*.pem

# Uncomment HTTPS server block in deployment/nginx.conf
```

### Step 4: Configure Services

```bash
# Copy and edit environment
cp .env.example .env
nano .env

# Configure data sources
nano edge/config/sources.yaml

# Configure thresholds
nano edge/config/thresholds.yaml

# Configure calibration
nano edge/config/calibration.yaml
```

### Step 5: Build and Deploy

```bash
# Build Docker image
docker-compose build

# Start services
docker-compose --profile production up -d

# Verify
docker-compose ps
docker-compose logs -f edge
```

### Step 6: Configure Systemd (Auto-start on Boot)

Create `/etc/systemd/system/shield-edge.service`:

```ini
[Unit]
Description=Shield Tunneling Edge Platform
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/shield-tunneling-icp
ExecStart=/usr/local/bin/docker-compose --profile production up -d
ExecStop=/usr/local/bin/docker-compose --profile production down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable shield-edge
sudo systemctl start shield-edge
sudo systemctl status shield-edge
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Logging level | INFO | No |
| `DB_PATH` | Database path | /app/data/edge.db | No |
| `MONITORING_API_TOKEN` | REST API token | - | Yes |
| `OPCUA_ENDPOINT` | OPC UA endpoint | - | Yes |
| `MODBUS_HOST` | Modbus host | - | Yes |
| `MODBUS_PORT` | Modbus port | 502 | No |

### Data Source Configuration

Edit `edge/config/sources.yaml`:

```yaml
sources:
  plc_main:
    type: opcua
    enabled: true
    endpoint_url: "opc.tcp://192.168.1.10:4840"
    # ... more configuration

  guidance_system:
    type: modbus
    enabled: true
    host: "192.168.1.100"
    # ... more configuration

  monitoring_api:
    type: rest
    enabled: true
    base_url: "http://192.168.1.200:8080/api/v1"
    # ... more configuration
```

### Resource Limits

Edit `docker-compose.yml` to adjust resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Maximum CPU cores
      memory: 2G       # Maximum memory
    reservations:
      cpus: '0.5'      # Guaranteed CPU
      memory: 512M     # Guaranteed memory
```

---

## Monitoring

### Health Checks

```bash
# Basic health
curl http://localhost:8000/api/v1/health

# Detailed health
curl http://localhost:8000/api/v1/health/detailed
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View edge service logs only
docker-compose logs -f edge

# View last 100 lines
docker-compose logs --tail=100 edge

# Application logs (inside container)
docker exec shield-edge tail -f /app/logs/edge.log
```

### Metrics

If monitoring profile is enabled:

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### Container Stats

```bash
# Real-time stats
docker stats shield-edge

# Resource usage
docker-compose top
```

---

## Backup and Recovery

### Database Backup

```bash
# Backup database
docker exec shield-edge sqlite3 /app/data/edge.db ".backup /app/data/edge_backup_$(date +%Y%m%d).db"

# Copy to host
docker cp shield-edge:/app/data/edge_backup_20251120.db ./backups/

# Automated backup script
cat > /opt/shield-tunneling-icp/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/shield-tunneling-icp/backups"
mkdir -p $BACKUP_DIR

docker exec shield-edge sqlite3 /app/data/edge.db ".backup /app/data/edge_backup_${DATE}.db"
docker cp shield-edge:/app/data/edge_backup_${DATE}.db $BACKUP_DIR/

# Keep only last 7 days
find $BACKUP_DIR -name "edge_backup_*.db" -mtime +7 -delete

echo "Backup completed: edge_backup_${DATE}.db"
EOF

chmod +x /opt/shield-tunneling-icp/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/shield-tunneling-icp/backup.sh") | crontab -
```

### Restore Database

```bash
# Stop service
docker-compose stop edge

# Copy backup to container
docker cp ./backups/edge_backup_20251120.db shield-edge:/app/data/edge_restore.db

# Restore
docker exec shield-edge sh -c "cp /app/data/edge_restore.db /app/data/edge.db"

# Restart service
docker-compose start edge
```

### Configuration Backup

```bash
# Backup configuration
tar -czf config_backup_$(date +%Y%m%d).tar.gz edge/config/

# Restore
tar -xzf config_backup_20251120.tar.gz
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs edge

# Check container status
docker-compose ps

# Verify configuration
docker-compose config

# Restart service
docker-compose restart edge
```

### Database Issues

```bash
# Check database integrity
docker exec shield-edge sqlite3 /app/data/edge.db "PRAGMA integrity_check;"

# Check WAL mode
docker exec shield-edge sqlite3 /app/data/edge.db "PRAGMA journal_mode;"

# Vacuum database
docker exec shield-edge sqlite3 /app/data/edge.db "VACUUM;"
```

### Network Connectivity

```bash
# Test OPC UA connection
docker exec shield-edge nc -zv 192.168.1.10 4840

# Test Modbus connection
docker exec shield-edge nc -zv 192.168.1.100 502

# Test REST API
docker exec shield-edge curl -I http://192.168.1.200:8080/api/v1/health
```

### High CPU/Memory Usage

```bash
# Check resource usage
docker stats shield-edge

# Check running processes
docker exec shield-edge ps aux

# Adjust resource limits in docker-compose.yml
```

### Data Not Collecting

```bash
# Check collector status
curl http://localhost:8000/api/v1/health/detailed

# Check data source configuration
docker exec shield-edge cat /app/edge/config/sources.yaml

# View collector logs
docker-compose logs -f edge | grep -i "collector"
```

---

## Maintenance

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose --profile production up -d

# Verify
docker-compose logs -f edge
```

### Data Cleanup

```bash
# Run cleanup script
docker exec shield-edge python /app/edge/scripts/cleanup_old_data.py --retention-days 90 --vacuum

# Automate (add to crontab, weekly on Sunday at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * 0 docker exec shield-edge python /app/edge/scripts/cleanup_old_data.py --retention-days 90 --vacuum") | crontab -
```

### Batch Ring Alignment

```bash
# Align specific rings
docker exec shield-edge python /app/edge/scripts/batch_align_rings.py --start-ring 100 --end-ring 200

# Align incomplete rings
docker exec shield-edge python /app/edge/scripts/batch_align_rings.py --incomplete-only
```

### Log Rotation

Configure log rotation in `/etc/logrotate.d/shield-edge`:

```
/opt/shield-tunneling-icp/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 tunnel tunnel
}
```

---

## Security Recommendations

1. **Change default passwords**
   - Update Grafana admin password
   - Use strong API tokens

2. **Enable HTTPS**
   - Configure SSL certificates
   - Force HTTPS in nginx

3. **Firewall configuration**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 8000/tcp  # Only if not using nginx
   sudo ufw enable
   ```

4. **Regular updates**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

5. **Backup encryption**
   ```bash
   # Encrypt backups
   gpg --encrypt --recipient your@email.com edge_backup.db
   ```

---

## Performance Tuning

### Database Optimization

```bash
# Increase cache size
docker exec shield-edge sqlite3 /app/data/edge.db "PRAGMA cache_size=-64000;"

# Analyze database
docker exec shield-edge sqlite3 /app/data/edge.db "ANALYZE;"
```

### Docker Optimization

In `docker-compose.yml`:

```yaml
services:
  edge:
    # Use host network for better performance (development only)
    # network_mode: host

    # Adjust shared memory
    shm_size: '256m'

    # Disable unnecessary features
    security_opt:
      - no-new-privileges:true
```

---

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review documentation: `/opt/shield-tunneling-icp/edge/README.md`
- Contact: [Your support contact]

---

**Last Updated**: 2025-11-20
**Version**: 1.0
