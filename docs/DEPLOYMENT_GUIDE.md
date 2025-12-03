# Production Deployment Guide

## Overview

This guide covers deploying the Conversational Memory System to production at scale.

---

## Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│   Load Balancer (nginx/ALB)     │
└──────┬──────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│         API Gateway / Rate Limiting           │
│         (Kong / AWS API Gateway)              │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│         FastAPI Application Servers           │
│      (Docker containers in Kubernetes)        │
│                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Instance │  │ Instance │  │ Instance │   │
│  │    1     │  │    2     │  │    3     │   │
│  └──────────┘  └──────────┘  └──────────┘   │
└──────┬───────────────┬─────────────────┬─────┘
       │               │                 │
       ▼               ▼                 ▼
┌─────────────┐ ┌──────────────┐ ┌─────────────┐
│   Redis     │ │  PostgreSQL  │ │   Worker    │
│   Cache     │ │   Database   │ │    Queue    │
│             │ │              │ │  (Celery)   │
└─────────────┘ └──────────────┘ └─────────────┘
```

---

## Prerequisites

### System Requirements

**Minimum (1K conversations/day):**
- 2 vCPUs, 4GB RAM
- 20GB SSD storage
- PostgreSQL 14+
- Redis 6+

**Recommended (10K conversations/day):**
- 4 vCPUs, 8GB RAM
- 100GB SSD storage
- PostgreSQL 14+ (managed service)
- Redis 6+ (managed service)

**Scale (100K+ conversations/day):**
- Kubernetes cluster (3+ nodes)
- Managed PostgreSQL with read replicas
- Redis Cluster
- CDN for static assets

---

## Installation

### 1. System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.9 python3-pip postgresql redis-server nginx

# macOS
brew install python@3.9 postgresql redis nginx

# Verify installations
python3 --version  # Should be 3.8+
psql --version     # Should be 12+
redis-cli --version
```

### 2. Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements_production.txt
```

**requirements_production.txt:**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
redis==5.0.1
pydantic==2.5.0
pydantic-settings==2.1.0
alembic==1.13.0
celery==5.3.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
prometheus-client==0.19.0
gunicorn==21.2.0
```

### 3. Database Setup

```bash
# Create database
sudo -u postgres psql

CREATE DATABASE memory_system;
CREATE USER memory_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE memory_system TO memory_user;

# Load schema
psql -U memory_user -d memory_system -f database_schema.sql

# Run migrations
alembic upgrade head
```

### 4. Redis Configuration

```bash
# Edit redis.conf
sudo nano /etc/redis/redis.conf

# Recommended settings
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
```

### 5. Application Configuration

Create `.env` file:

```bash
# Application
APP_ENV=production
DEBUG=False
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://memory_user:secure_password@localhost:5432/memory_system

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Caching
CACHE_TTL=3600  # 1 hour
CACHE_MAX_SIZE=10000

# Monitoring
ENABLE_METRICS=True
SENTRY_DSN=your-sentry-dsn
```

---

## Running the Application

### Development

```bash
# Single process
uvicorn production_api:app --reload --host 0.0.0.0 --port 8000
```

### Production (Single Server)

```bash
# Using Gunicorn with Uvicorn workers
gunicorn production_api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

### Production (Docker)

**Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements_production.txt .
RUN pip install --no-cache-dir -r requirements_production.txt

# Copy application
COPY . .

# Run
CMD ["gunicorn", "production_api:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://memory_user:password@db:5432/memory_system
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=memory_user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=memory_system
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:6
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Build and run:**
```bash
docker-compose up -d
docker-compose logs -f api
```

---

## Kubernetes Deployment

### Deployment Configuration

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: memory-api
  template:
    metadata:
      labels:
        app: memory-api
    spec:
      containers:
      - name: api
        image: your-registry/memory-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: url
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: memory-api-service
spec:
  selector:
    app: memory-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: memory-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: memory-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Deploy:**
```bash
kubectl apply -f deployment.yaml
kubectl get pods
kubectl get service memory-api-service
```

---

## Monitoring & Observability

### Prometheus Metrics

Add to `production_api.py`:

```python
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client import make_asgi_app

# Metrics
requests_total = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
processing_time = Histogram('processing_time_seconds', 'Time to process conversation')
active_conversations = Gauge('active_conversations', 'Number of conversations being processed')

# Mount metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### Grafana Dashboard

Key metrics to monitor:
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate
- Cache hit rate
- Database connection pool usage
- Memory usage
- CPU usage

### Logging

Configure structured logging:

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName
        }
        return json.dumps(log_obj)

# Configure
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)
```

---

## Performance Optimization

### 1. Database Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM memory_items WHERE user_id = 'user_001';

-- Create indexes
CREATE INDEX CONCURRENTLY idx_memory_items_user_retention 
ON memory_items(user_id, retention_level);

-- Partition large tables
CREATE TABLE memory_items_2024_01 PARTITION OF memory_items
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Vacuum regularly
VACUUM ANALYZE memory_items;
```

### 2. Caching Strategy

```python
# Cache frequently accessed data
@cache.cached(ttl=3600, key_prefix='user_profile')
async def get_user_profile(user_id: str):
    # Expensive database query
    return profile

# Invalidate on update
async def update_user_profile(user_id: str, data: dict):
    await db.update(user_id, data)
    await cache.delete(f'user_profile:{user_id}')
```

### 3. Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

---

## Scaling Strategies

### Horizontal Scaling

**1,000 conversations/day → 1 server**
- 1 API instance
- Shared PostgreSQL
- Shared Redis

**10,000 conversations/day → 3-5 servers**
- 3-5 API instances (load balanced)
- Managed PostgreSQL
- Redis with persistence

**100,000 conversations/day → 10-20 servers**
- 10-20 API instances (auto-scaling)
- PostgreSQL with read replicas
- Redis Cluster
- CDN for static content

**1,000,000+ conversations/day → Multi-region**
- Kubernetes cluster across regions
- Multi-master PostgreSQL
- Redis Cluster with sharding
- Message queue for async processing

### Cost Estimation

**Small (1K/day):**
- Single server: $20-50/month
- Managed DB: $20/month
- Total: ~$50/month

**Medium (10K/day):**
- Load balancer: $20/month
- API servers (3x): $150/month
- Managed DB: $100/month
- Redis: $30/month
- Total: ~$300/month

**Large (100K/day):**
- Kubernetes: $500/month
- Managed DB: $500/month
- Redis Cluster: $200/month
- CDN: $100/month
- Total: ~$1,500/month

---

## Security Checklist

- [ ] Enable HTTPS/TLS
- [ ] Implement rate limiting
- [ ] Use secure API keys
- [ ] Enable database encryption at rest
- [ ] Set up firewall rules
- [ ] Regular security audits
- [ ] Implement CORS properly
- [ ] Sanitize user inputs
- [ ] Use prepared statements
- [ ] Regular backups
- [ ] Enable audit logging
- [ ] Monitor for anomalies

---

## Backup & Recovery

### Database Backups

```bash
# Daily backup
pg_dump -U memory_user memory_system > backup_$(date +%Y%m%d).sql

# Restore
psql -U memory_user memory_system < backup_20241202.sql

# Automated with cron
0 2 * * * /usr/local/bin/backup_db.sh
```

### Redis Persistence

```bash
# Enable AOF and RDB
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
```

---

## Troubleshooting

### High Latency

1. Check database slow queries
2. Verify cache hit rate
3. Monitor network latency
4. Check connection pool usage

### Memory Issues

1. Review cache size
2. Check for memory leaks
3. Optimize database queries
4. Increase server RAM

### Database Connection Issues

1. Check connection pool settings
2. Verify max_connections in PostgreSQL
3. Monitor active connections
4. Use connection pooling

---

## Maintenance Tasks

### Daily
- Monitor error logs
- Check system health
- Review performance metrics

### Weekly
- Analyze slow queries
- Review cache hit rates
- Check disk usage
- Update security patches

### Monthly
- Database maintenance (VACUUM)
- Review and optimize indexes
- Capacity planning review
- Security audit

