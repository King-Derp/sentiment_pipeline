# Custom Dashboard Service - Product Requirements Document

**Version:** 1.1  
**Date:** 2025-07-31  
**Status:** Planning

## 1. Overview

The Custom Dashboard Service is a new microservice designed to replace PowerBI integration with a flexible, custom-built analytics and visualization platform. This service will provide real-time and historical sentiment analysis dashboards with enhanced capabilities beyond what PowerBI offers, leveraging existing sentiment_analyzer API endpoints for data access.

## 2. Business Requirements

### 2.1 Primary Goals
- **Replace PowerBI dependency** with a custom, more flexible solution
- **Provide real-time sentiment monitoring** with live updates
- **Enable advanced analytics** not possible with PowerBI limitations
- **Reduce operational costs** by eliminating PowerBI licensing
- **Improve user experience** with custom-tailored interfaces
- **Leverage existing infrastructure** by reusing sentiment_analyzer API endpoints

### 2.2 Success Metrics
- Dashboard load times < 2 seconds
- Real-time updates with < 5 second latency
- Support for 100+ concurrent users
- 99.9% uptime availability
- User satisfaction score > 8/10

## 3. Functional Requirements

### 3.1 Core Features

#### 3.1.1 Real-Time Dashboard
- Live sentiment score monitoring using existing `/events` endpoint
- Real-time event stream visualization
- Configurable refresh intervals (1s, 5s, 30s, 1m)
- Auto-refresh capabilities with Streamlit's built-in features

#### 3.1.2 Historical Analytics
- Time-series sentiment trend analysis using `/events` and `/metrics` endpoints
- Comparative period analysis (day-over-day, week-over-week)
- Custom date range selection leveraging existing filtering
- Drill-down capabilities by source, subreddit, time period

#### 3.1.3 Advanced Visualizations
- Interactive time-series charts with Streamlit/Plotly
- Sentiment distribution heatmaps
- Geographic sentiment mapping (if location data available)
- Word clouds from analyzed text
- Correlation analysis between different metrics

#### 3.1.4 Alerting & Notifications
- Configurable sentiment threshold alerts
- Email/Slack notifications for anomalies
- Custom alert rules based on multiple conditions
- Alert history and acknowledgment system

### 3.2 Data Features

#### 3.2.1 Data Sources
- **Primary**: Existing sentiment_analyzer API endpoints:
  - `GET /events` - Sentiment analysis results with filtering and pagination
  - `GET /metrics` - Aggregated sentiment metrics
  - `POST /analyze` - On-the-fly text analysis (for testing/demos)
  - `POST /analyze/bulk` - Bulk text analysis
- **Real-time**: Polling existing API endpoints for live updates
- **Caching**: Client-side caching with Streamlit session state

#### 3.2.2 Data Processing
- Leverage existing API filtering and pagination
- Client-side aggregation for custom time buckets
- Statistical analysis (moving averages, percentiles)
- Anomaly detection algorithms
- Data export capabilities (CSV, JSON, PDF reports)

### 3.3 User Interface Features

#### 3.3.1 Dashboard Management
- Multiple dashboard pages using Streamlit's multi-page app
- Customizable widget layouts with Streamlit columns/containers
- User preferences stored in session state
- Dashboard templates and presets

#### 3.3.2 Filtering & Search
- Advanced filtering using existing API parameters
- Date/time range pickers
- Source and sentiment label filters
- Saved filter presets in session state
- Quick filter shortcuts

## 4. Technical Requirements

### 4.1 Architecture
- **Frontend Framework:** Streamlit (chosen for fast deployment)
- **Backend API:** Reuse existing sentiment_analyzer FastAPI endpoints
- **Data Access:** HTTP requests to existing `/events` and `/metrics` endpoints
- **Real-time Updates:** Streamlit auto-refresh and polling
- **Caching:** Streamlit session state and @st.cache_data decorators

### 4.2 Performance Requirements
- Support 100+ concurrent users
- Dashboard load time < 2 seconds
- Real-time update latency < 5 seconds (via polling)
- 99.9% uptime availability
- Horizontal scaling capability

### 4.3 Security Requirements
- Authentication integration with existing system
- Role-based access control (RBAC)
- HTTPS encryption for all communications
- Input validation and sanitization
- Audit logging for sensitive operations

### 4.4 Integration Requirements
- **API Integration**: Direct HTTP calls to sentiment_analyzer endpoints
- **Backward compatibility**: Maintain PowerBI integration during transition
- **Export capabilities**: CSV, JSON, PDF report generation
- **Extensibility**: Easy addition of new visualizations and metrics

## 5. User Experience Requirements

### 5.1 Usability
- Intuitive Streamlit web interface
- Responsive design with Streamlit's mobile support
- Interactive widgets and controls
- Contextual help and tooltips

### 5.2 Accessibility
- Streamlit's built-in accessibility features
- High contrast mode support
- Keyboard navigation support
- Screen reader compatibility

## 6. Deployment & Operations

### 6.1 Deployment
- Docker containerization
- Integration with existing docker-compose setup
- Environment-based configuration
- Streamlit server configuration

### 6.2 Monitoring & Logging
- Streamlit built-in metrics
- Application performance monitoring
- Error tracking and alerting
- User activity logging

## 7. Migration Strategy

### 7.1 Transition Plan
1. **Phase 1:** Build core Streamlit dashboard using existing APIs
2. **Phase 2:** Implement real-time polling features
3. **Phase 3:** Add advanced analytics and visualizations
4. **Phase 4:** User acceptance testing
5. **Phase 5:** Gradual migration from PowerBI
6. **Phase 6:** PowerBI deprecation

### 7.2 Risk Mitigation
- Maintain PowerBI integration during transition
- Leverage existing, tested API endpoints
- Streamlit's rapid development cycle for quick iterations
- Rollback procedures in case of issues

## 8. API Endpoint Utilization

### 8.1 Existing Endpoints to Leverage
- **`GET /events`**: Primary data source for sentiment results
  - Supports filtering by time range, source, sentiment label
  - Cursor-based pagination for large datasets
  - Returns detailed sentiment analysis results
  
- **`GET /metrics`**: Aggregated metrics for dashboard summaries
  - Time-bucketed aggregations
  - Source and label filtering
  - Efficient for overview dashboards
  
- **`POST /analyze`**: Real-time text analysis for demos/testing
  - On-the-fly sentiment analysis
  - Useful for interactive features
  
- **`POST /analyze/bulk`**: Batch analysis capabilities
  - Multiple text analysis in single request
  - Useful for bulk operations

### 8.2 API Enhancement Needs
- **WebSocket support** (future enhancement for true real-time updates)
- **Additional aggregation endpoints** (if needed for specific visualizations)
- **Export endpoints** (if direct API export is preferred over client-side)

## 9. Success Criteria

### 9.1 Technical Success
- All functional requirements implemented using existing APIs
- Performance targets met with Streamlit architecture
- Security requirements satisfied
- Successful integration with existing systems

### 9.2 Business Success
- User adoption rate > 90%
- Reduced operational costs vs PowerBI
- Improved user satisfaction scores
- Enhanced analytical capabilities utilized

## 10. Timeline

### 10.1 Development Phases (Accelerated with Streamlit)
- **Week 1:** Core Streamlit app setup and API integration
- **Week 2:** Basic visualizations and filtering
- **Week 3:** Advanced analytics and real-time features
- **Week 4:** Testing, refinement, and deployment
- **Week 5-6:** User acceptance testing and migration

### 10.2 Milestones
- MVP dashboard functional with existing API integration
- Real-time polling updates working
- User acceptance testing complete
- Production deployment successful
- PowerBI migration complete

---

**Document Control:**
- **Author:** Development Team
- **Reviewers:** Product Owner, Technical Lead
- **Approval:** Pending
- **Next Review:** 2025-08-07
