# Dashboard Service

**Version:** 2.0  
**Status:** ✅ Production Ready (Containerized)  
**Last Updated:** 2025-07-31

## Overview

The Dashboard Service is a custom-built analytics and visualization microservice designed to replace PowerBI integration in the Sentiment Pipeline project. It provides real-time sentiment monitoring, historical analytics, and advanced visualizations with enhanced capabilities beyond traditional BI tools, leveraging existing sentiment_analyzer API endpoints for data access.

## 🎯 Purpose

This service addresses limitations encountered with PowerBI by providing:
- **Custom Analytics**: Tailored visualizations and metrics specific to sentiment analysis
- **Real-time Updates**: Polling-based live data streaming with configurable refresh intervals
- **Cost Efficiency**: Eliminates PowerBI licensing costs and operational complexity
- **Enhanced Control**: Full customization of dashboards, alerts, and user experience
- **Better Integration**: Native integration with existing sentiment_analyzer API endpoints
- **Rapid Development**: Streamlit framework for fast deployment and iteration

## 🏗️ Architecture

```
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────────┐
│  Sentiment      │    │  Dashboard        │    │  Web Browser        │
│  Analyzer API   │◄───│  Service          │───►│  (Users)            │
│  (/events,      │    │  (Streamlit)      │    │                     │
│  /metrics)      │    └───────────────────┘    └─────────────────────┘
└─────────────────┘
```

### Key Components

- **Frontend Framework**: Streamlit (chosen for rapid development and deployment)
- **Backend API**: Existing sentiment_analyzer FastAPI endpoints
- **Data Access**: HTTP requests to `/events` and `/metrics` endpoints
- **Real-time Updates**: Streamlit auto-refresh and polling mechanisms
- **Caching**: Streamlit session state and @st.cache_data decorators
- **Authentication**: Integration with existing security systems

## 🚀 Features

### Core Functionality
- **Real-time Dashboards**: Live sentiment score monitoring using existing `/events` endpoint
- **Historical Analytics**: Time-series analysis using `/events` and `/metrics` endpoints
- **Interactive Visualizations**: Plotly-based charts with drill-down capabilities
- **Custom Alerts**: Configurable threshold-based notifications (optional)
- **Data Export**: CSV, JSON, and PDF report generation

### User Experience
- **Multi-page App**: Streamlit's native multi-page architecture
- **Responsive Design**: Mobile-friendly interface with Streamlit's built-in responsiveness
- **Interactive Widgets**: Streamlit's rich widget ecosystem for filtering and controls
- **Session Management**: User preferences stored in Streamlit session state
- **Real-time Updates**: Auto-refresh capabilities with configurable intervals

## 📊 Data Sources

The service integrates with existing sentiment_analyzer API endpoints:

### Primary Endpoints
- **`GET /events`**: Sentiment analysis results with filtering and pagination
  - Supports time range, source, sentiment label filtering
  - Cursor-based pagination for large datasets
  - Returns detailed SentimentResultDTO objects

- **`GET /metrics`**: Aggregated sentiment metrics
  - Time-bucketed aggregations (hour, day, week)
  - Source and label filtering
  - Returns SentimentMetricDTO objects for efficient dashboards

### Additional Endpoints
- **`POST /analyze`**: On-the-fly text analysis for demos/testing
- **`POST /analyze/bulk`**: Batch text analysis capabilities

## 🛠️ Development Setup

### Prerequisites
- Python 3.11+
- Access to running sentiment_analyzer service
- Docker and Docker Compose (optional)

### Quick Start

```powershell
# Navigate to dashboard service directory
cd sentiment_pipeline/dashboard_service

# Install dependencies
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start Streamlit development server
poetry run streamlit run src/dashboard_service/main.py

# Or using Docker
docker-compose up dashboard_service
```

### Environment Variables

```bash
# Sentiment Analyzer API Configuration
# For local development (when sentiment_analyzer runs locally)
SENTIMENT_API_BASE_URL=http://localhost:8001
# For containerized deployment (when both services run in Docker)
# SENTIMENT_API_BASE_URL=http://sentiment_analyzer:8001
SENTIMENT_API_TIMEOUT=30

# Dashboard Configuration
STREAMLIT_PORT=8501
STREAMLIT_HOST=0.0.0.0
DEBUG_MODE=true

# Authentication (if required)
AUTH_SECRET_KEY=your-secret-key
AUTH_ALGORITHM=HS256

# External Integrations (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## 📁 Project Structure

```
dashboard_service/
├── README.md                 # This file
├── prd.md                   # Product Requirements Document
├── todo.md                  # Development TODO list
├── pyproject.toml           # Python dependencies (Streamlit-focused)
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Service orchestration
├── .env.example            # Environment template
├── src/
│   └── dashboard_service/
│       ├── __init__.py
│       ├── main.py         # Streamlit app entry point
│       ├── config/         # Configuration management
│       ├── api/            # API client for sentiment_analyzer
│       ├── pages/          # Streamlit pages
│       ├── components/     # Reusable UI components
│       ├── services/       # Data services and business logic
│       └── utils/          # Utility functions
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests with API
│   └── e2e/              # End-to-end Streamlit tests
└── docs/                  # Additional documentation
    ├── api_integration.md # API integration guide
    ├── deployment.md     # Deployment guide
    └── user_guide.md     # User documentation
```

## 🧪 Testing

```powershell
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=dashboard_service

# Run specific test categories
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/e2e/

# Test Streamlit app
poetry run pytest tests/e2e/test_streamlit_app.py
```

## 🚀 Deployment

### Development
```powershell
# Start Streamlit development server
poetry run streamlit run src/dashboard_service/main.py

# With custom port
poetry run streamlit run src/dashboard_service/main.py --server.port 8501
```

### Containerized Deployment (Recommended)

```powershell
# Deploy entire sentiment pipeline stack (recommended)
cd f:\Coding\sentiment_pipeline
docker-compose up -d

# Or deploy just the dashboard service
docker-compose up -d dashboard_service

# Dashboard will be available at:
# http://localhost:8503 (containerized)

# Check service status
docker-compose ps

# View logs
docker-compose logs -f dashboard_service
```

### Local Development

```powershell
# Ensure sentiment_analyzer is running (locally or in Docker)
# Then start dashboard locally
cd dashboard_service
$env:SENTIMENT_API_BASE_URL="http://localhost:8001"
poetry run streamlit run src/dashboard_service/main.py --server.port 8502

# Dashboard will be available at:
# http://localhost:8502 (local development)
```

## 📈 Performance Targets

- **Load Time**: < 2 seconds for dashboard initialization
- **Real-time Latency**: < 5 seconds for live updates (via polling)
- **Concurrent Users**: Support for 100+ simultaneous users
- **Uptime**: 99.9% availability target
- **Memory Usage**: < 1GB RAM under normal load (Streamlit efficiency)

## 🔒 Security

- **API Authentication**: Secure communication with sentiment_analyzer API
- **HTTPS**: Encrypted connections for production deployment
- **Input Validation**: Comprehensive sanitization of user inputs
- **Session Security**: Secure session state management
- **Access Control**: Integration with existing authentication systems

## 📚 Documentation

- **[PRD](prd.md)**: Product Requirements Document with API integration details
- **[TODO](todo.md)**: Development task list with API endpoint mapping
- **API Integration**: Detailed guide for sentiment_analyzer endpoint usage
- **User Guide**: Comprehensive usage instructions (coming soon)

## 🤝 Contributing

### Development Workflow
1. Review the [PRD](prd.md) and [TODO](todo.md) documents
2. Understand existing API endpoints in sentiment_analyzer
3. Create feature branch from `main`
4. Implement Streamlit components with API integration
5. Test with live sentiment_analyzer API
6. Update documentation as needed
7. Submit pull request for review

### Code Standards
- Follow PEP8 style guidelines
- Use type hints throughout
- Write comprehensive docstrings
- Maintain test coverage > 80%
- Use Streamlit best practices for UI components

## 🐛 Troubleshooting

### Common Issues

**Dashboard won't start:**
- Check sentiment_analyzer API connectivity
- Verify environment variables
- Ensure Streamlit dependencies are installed
- Check port availability (default 8501)

**API connection errors:**
- Verify sentiment_analyzer service is running
- Check API base URL configuration
- Review network connectivity
- Monitor API response times

**Slow performance:**
- Check API response times
- Review Streamlit caching configuration
- Monitor concurrent user load
- Optimize data fetching frequency

**Real-time updates not working:**
- Verify API polling configuration
- Check auto-refresh settings
- Monitor network latency
- Review browser console for errors

### Getting Help

1. Check the [TODO](todo.md) for known issues
2. Review Streamlit and API logs
3. Test API endpoints directly
4. Consult the troubleshooting guide
5. Contact the development team

## 📋 Development Status

### ✅ **Completed Phases**

**Phase 1: Foundation (COMPLETE)**
- ✅ Streamlit app setup with multi-page architecture
- ✅ API client implementation with retry logic and error handling
- ✅ Basic dashboard functionality with real-time data
- ✅ Environment configuration and settings management

**Phase 2: Core Features (COMPLETE)**
- ✅ Real-time data integration with `/events` and `/metrics` endpoints
- ✅ Interactive Plotly visualizations (time-series, pie charts, bar charts)
- ✅ Advanced filtering capabilities (time range, source, sentiment)
- ✅ Caching with `@st.cache_data` for performance optimization

**Phase 3: Containerization (COMPLETE)**
- ✅ Multi-stage Dockerfile with production optimizations
- ✅ Docker Compose integration with service dependencies
- ✅ Container networking and inter-service communication
- ✅ Health checks and monitoring
- ✅ Environment variable management for container deployment

**Phase 4: Production Deployment (COMPLETE)**
- ✅ Production-ready containerized deployment
- ✅ Security configurations and host header handling
- ✅ Resource limits and non-root user execution
- ✅ Comprehensive logging and error handling
- ✅ API connectivity troubleshooting and resolution

### 🚀 **Future Enhancements**

**Phase 5: Advanced Features (Optional)**
- [ ] Export capabilities (CSV, JSON, PDF)
- [ ] Advanced filtering and search functionality
- [ ] Custom alerting and notification system
- [ ] User authentication and role-based access

**Phase 6: Testing & Optimization (Optional)**
- [ ] Integration tests for API connectivity
- [ ] Performance testing under load
- [ ] UI/UX improvements and accessibility
- [ ] Automated testing pipeline

## 📞 Support

- **Development Team**: [Contact Information]
- **Documentation**: Available in `/docs` directory
- **API Documentation**: sentiment_analyzer service `/docs` endpoint
- **Issue Tracking**: [Issue Tracker URL]
- **Slack Channel**: #dashboard-service

## 🔗 Related Services

- **Sentiment Analyzer**: Main API service providing data endpoints
- **TimescaleDB**: Underlying database (accessed via API)
- **PowerBI**: Legacy integration being replaced

---

**Status**: ✅ Production Ready (Containerized)  
**Current Version**: 2.0  
**Deployment**: Available at http://localhost:8503 (containerized) or http://localhost:8502 (local dev)  
**Last Updated**: 2025-07-31

## 🎉 **Ready for Use!**

The Dashboard Service is now **fully operational and production-ready**. Deploy the entire sentiment pipeline stack with:

```bash
cd f:\Coding\sentiment_pipeline
docker-compose up -d
```

Access the dashboard at **http://localhost:8503** to view live sentiment analysis data from your Reddit pipeline!
