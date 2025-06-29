# Sentiment Pipeline Deployment Guide

This guide covers deploying the Sentiment Analysis Pipeline using Docker and Docker Compose.

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB RAM available for containers (8GB+ for GPU)
- 10GB free disk space
- **For GPU support:** NVIDIA Container Runtime and compatible GPU

### 1. Environment Setup

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Configure environment variables:**
   Edit `.env` file with your specific values:
   ```bash
   # Database credentials
   PG_USER=your_db_user
   PG_PASSWORD=your_secure_password
   PG_DB=sentiment_pipeline_db
   
   # API Configuration
   SENTIMENT_API_PORT=8001
   DEBUG=false
   
   # Security (Production)
   ALLOWED_HOSTS=your-domain.com,localhost
   CORS_ORIGINS=https://your-frontend.com
   
   # PowerBI (Optional)
   POWERBI_PUSH_URL=https://api.powerbi.com/beta/...
   POWERBI_API_KEY=your_api_key
   ```

### 2. Deploy Services

```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f sentiment_analyzer
```

### 3. Verify Deployment

1. **Health Check:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **API Documentation:**
   - Development: http://localhost:8001/docs
   - Production: Docs disabled for security

3. **Test API:**
   ```bash
   curl -X POST "http://localhost:8001/api/v1/sentiment/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "I love this product!"}'
   ```

## 🚀 GPU Deployment (Optional)

For high-performance inference, you can enable GPU support:

### 1. Prerequisites for GPU

1. **Install NVIDIA Container Runtime:**
   ```bash
   # Ubuntu/Debian
   curl -s -L https://nvidia.github.io/nvidia-container-runtime/gpgkey | sudo apt-key add -
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-container-runtime/$distribution/nvidia-container-runtime.list | sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list
   sudo apt-get update
   sudo apt-get install nvidia-container-runtime
   
   # Restart Docker
   sudo systemctl restart docker
   ```

2. **Verify GPU access:**
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
   ```

### 2. Enable GPU in Configuration

1. **Update .env file:**
   ```bash
   # Enable GPU support
   USE_GPU=true
   
   # Increase resource limits for GPU
   GPU_MEMORY_LIMIT=8G
   GPU_CPU_LIMIT=4.0
   GPU_MEMORY_RESERVATION=4G
   GPU_CPU_RESERVATION=2.0
   ```

2. **Uncomment GPU settings in docker-compose.yml:**
   ```yaml
   sentiment_analyzer:
     # Uncomment this line:
     runtime: nvidia
     deploy:
       resources:
         reservations:
           # Uncomment these lines:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu]
   ```

### 3. Deploy with GPU

```bash
# Rebuild with GPU support
docker-compose build --no-cache sentiment_analyzer

# Deploy with GPU
docker-compose up -d

# Verify GPU usage
docker-compose exec sentiment_analyzer nvidia-smi
```

### 4. GPU Performance Benefits

- **CPU-only:** ~50-100 requests/minute
- **GPU-enabled:** ~200-500 requests/minute
- **Batch processing:** 5-10x faster with GPU
- **Model loading:** Faster initialization

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   TimescaleDB   │◄───┤ Sentiment API    │◄───┤  Client Apps    │
│   (Database)    │    │   (FastAPI)      │    │  (Frontend/BI)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │    PowerBI       │
                       │  (Optional)      │
                       └──────────────────┘
```

## 🔧 Configuration Details

### Database Configuration

- **Service:** `timescaledb`
- **Port:** 5433 (host) → 5432 (container)
- **Health Check:** Automatic with retries
- **Data Persistence:** Named volume `timescaledb_data`

### Sentiment API Configuration

- **Service:** `sentiment_analyzer_api`
- **Port:** 8001 (configurable via `SENTIMENT_API_PORT`)
- **Health Check:** `/health` endpoint
- **Resource Limits:** 4GB RAM, 2 CPU cores
- **Model Cache:** Persistent volume for HuggingFace models

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PG_USER` | Database username | - | ✅ |
| `PG_PASSWORD` | Database password | - | ✅ |
| `PG_DB` | Database name | `sentiment_pipeline_db` | ✅ |
| `SENTIMENT_API_PORT` | API port on host | `8001` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |
| `WORKERS` | Uvicorn workers | `1` | ❌ |
| `LOG_LEVEL` | Logging level | `info` | ❌ |
| `ALLOWED_HOSTS` | Trusted hosts | `localhost,127.0.0.1` | ❌ |
| `CORS_ORIGINS` | CORS allowed origins | `http://localhost:3000` | ❌ |
| `POWERBI_PUSH_URL` | PowerBI streaming URL | - | ❌ |
| `POWERBI_API_KEY` | PowerBI API key | - | ❌ |

## 🔒 Security Considerations

### Production Security

1. **Environment Variables:**
   - Use strong, unique passwords
   - Never commit `.env` files to version control
   - Use secrets management in production

2. **Network Security:**
   - Configure `ALLOWED_HOSTS` for your domain
   - Restrict `CORS_ORIGINS` to trusted domains
   - Use HTTPS in production (reverse proxy)

3. **Container Security:**
   - API runs as non-root user (`appuser`)
   - Read-only volume mounts where possible
   - Resource limits prevent resource exhaustion

### Firewall Configuration

```bash
# Allow API port
sudo ufw allow 8001/tcp

# Allow database port (if external access needed)
sudo ufw allow 5433/tcp
```

## 📊 Monitoring & Logging

### Health Checks

- **Database:** `pg_isready` check every 10s
- **API:** HTTP health endpoint every 30s
- **Startup Grace Period:** 60s for API initialization

### Log Access

```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f sentiment_analyzer

# View last 100 lines
docker-compose logs --tail=100 sentiment_analyzer
```

### Metrics

The API provides health status including:
- Service version and uptime
- Database connection status
- PowerBI integration status
- Resource usage (via Docker stats)

## 🚀 Production Deployment

### Recommended Production Setup

1. **Reverse Proxy (Nginx/Traefik):**
   ```nginx
   server {
       listen 443 ssl;
       server_name api.yourdomain.com;
       
       location / {
           proxy_pass http://localhost:8001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Environment Overrides:**
   ```bash
   # Production environment
   DEBUG=false
   WORKERS=4
   LOG_LEVEL=warning
   ALLOWED_HOSTS=api.yourdomain.com
   CORS_ORIGINS=https://yourdomain.com
   ```

3. **Resource Scaling:**
   ```yaml
   # docker-compose.prod.yml
   services:
     sentiment_analyzer:
       deploy:
         resources:
           limits:
             memory: 8G
             cpus: '4.0'
         replicas: 2
   ```

### Backup Strategy

```bash
# Database backup
docker-compose exec timescaledb pg_dump -U $PG_USER $PG_DB > backup.sql

# Restore database
docker-compose exec -T timescaledb psql -U $PG_USER $PG_DB < backup.sql
```

## 🔧 Troubleshooting

### Common Issues

1. **Database Connection Failed:**
   ```bash
   # Check database status
   docker-compose logs timescaledb
   
   # Verify environment variables
   docker-compose config
   ```

2. **API Not Starting:**
   ```bash
   # Check API logs
   docker-compose logs sentiment_analyzer
   
   # Verify port availability
   netstat -tlnp | grep 8001
   ```

3. **Model Download Issues:**
   ```bash
   # Clear model cache
   docker volume rm sentiment_pipeline_sentiment_model_cache
   
   # Rebuild with fresh models
   docker-compose build --no-cache sentiment_analyzer
   ```

4. **PowerBI Integration Issues:**
   ```bash
   # Test PowerBI endpoint
   curl -X POST "$POWERBI_PUSH_URL" \
        -H "Content-Type: application/json" \
        -d '[{"text": "test", "sentiment": "positive"}]'
   ```

### Performance Tuning

1. **Database Optimization:**
   - Increase `shared_buffers` for TimescaleDB
   - Configure connection pooling
   - Regular VACUUM and ANALYZE

2. **API Optimization:**
   - Increase worker count for high load
   - Configure connection pooling
   - Enable response caching

3. **Resource Monitoring:**
   ```bash
   # Monitor resource usage
   docker stats
   
   # Check disk usage
   docker system df
   ```

## 📝 Maintenance

### Regular Tasks

1. **Update Images:**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

2. **Clean Up:**
   ```bash
   # Remove unused images
   docker image prune
   
   # Remove unused volumes
   docker volume prune
   ```

3. **Database Maintenance:**
   ```bash
   # Connect to database
   docker-compose exec timescaledb psql -U $PG_USER $PG_DB
   
   # Run maintenance queries
   VACUUM ANALYZE;
   ```

### Scaling

For high-traffic deployments:

1. **Horizontal Scaling:**
   - Use Docker Swarm or Kubernetes
   - Load balancer (HAProxy/Nginx)
   - Multiple API replicas

2. **Database Scaling:**
   - Read replicas for analytics
   - Connection pooling (PgBouncer)
   - Partitioning for large datasets

## 🆘 Support

For deployment issues:

1. Check logs: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test connectivity: Health check endpoints
4. Review documentation: API examples and PowerBI setup

---

**Next Steps:** After successful deployment, see `API_EXAMPLES.md` for usage examples and `POWERBI.md` for analytics setup.
