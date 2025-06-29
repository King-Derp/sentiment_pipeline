# Sentiment Analysis API - Usage Examples

This document provides comprehensive examples of how to use the Sentiment Analysis API endpoints.

## Base URL

```
http://localhost:8001
```

## Authentication

Currently, no authentication is required for API access. In production, consider implementing API keys or OAuth.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and service status |
| `/api/v1/sentiment/analyze` | POST | Analyze single text |
| `/api/v1/sentiment/analyze/bulk` | POST | Analyze multiple texts |
| `/api/v1/sentiment/events` | GET | Query stored sentiment results |
| `/api/v1/sentiment/metrics` | GET | Query aggregated metrics |

---

## 1. Health Check

### Request
```bash
curl -X GET "http://localhost:8001/health"
```

### Response
```json
{
  "status": "healthy",
  "service": "SentimentAnalyzerService",
  "version": "0.1.0",
  "timestamp": "2025-06-29T15:30:00.000Z",
  "powerbi_integration": "enabled",
  "debug_mode": false,
  "api_host": "0.0.0.0",
  "api_port": 8001
}
```

---

## 2. Single Text Analysis

### Request
```bash
curl -X POST "http://localhost:8001/api/v1/sentiment/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I absolutely love this new product! It exceeded all my expectations."
  }'
```

### Response
```json
{
  "label": "positive",
  "confidence": 0.9234,
  "scores": {
    "positive": 0.9234,
    "negative": 0.0421,
    "neutral": 0.0345
  },
  "model_version": "ProsusAI/finbert-v1.1"
}
```

### Python Example
```python
import requests
import json

url = "http://localhost:8001/api/v1/sentiment/analyze"
data = {
    "text": "The customer service was terrible and unhelpful."
}

response = requests.post(url, json=data)
result = response.json()

print(f"Sentiment: {result['label']}")
print(f"Confidence: {result['confidence']:.2%}")
print(f"Scores: {result['scores']}")
```

---

## 3. Bulk Text Analysis

### Request
```bash
curl -X POST "http://localhost:8001/api/v1/sentiment/analyze/bulk" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      {"text": "This is amazing! Best purchase ever."},
      {"text": "Not sure how I feel about this product."},
      {"text": "Completely disappointed with the quality."}
    ]
  }'
```

### Response
```json
[
  {
    "label": "positive",
    "confidence": 0.8956,
    "scores": {
      "positive": 0.8956,
      "negative": 0.0612,
      "neutral": 0.0432
    },
    "model_version": "ProsusAI/finbert-v1.1"
  },
  {
    "label": "neutral",
    "confidence": 0.7234,
    "scores": {
      "positive": 0.1823,
      "negative": 0.0943,
      "neutral": 0.7234
    },
    "model_version": "ProsusAI/finbert-v1.1"
  },
  {
    "label": "negative",
    "confidence": 0.8745,
    "scores": {
      "positive": 0.0456,
      "negative": 0.8745,
      "neutral": 0.0799
    },
    "model_version": "ProsusAI/finbert-v1.1"
  }
]
```

### JavaScript Example
```javascript
const analyzeTexts = async (texts) => {
  const response = await fetch('http://localhost:8001/api/v1/sentiment/analyze/bulk', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      texts: texts.map(text => ({ text }))
    })
  });
  
  const results = await response.json();
  return results;
};

// Usage
const texts = [
  "I love this product!",
  "It's okay, nothing special.",
  "Worst experience ever."
];

analyzeTexts(texts).then(results => {
  results.forEach((result, index) => {
    console.log(`Text ${index + 1}: ${result.label} (${(result.confidence * 100).toFixed(1)}%)`);
  });
});
```

---

## 4. Query Stored Events

### Basic Query
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/events"
```

### With Filters
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/events?source=reddit&sentiment_label=positive&limit=10"
```

### With Date Range
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/events?start_date=2025-06-01&end_date=2025-06-30&limit=50"
```

### With Pagination (Cursor-based)
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/events?cursor=eyJ0aW1lc3RhbXAiOiIyMDI1LTA2LTI5VDEyOjAwOjAwKzAwOjAwIiwiaWQiOjEyM30%3D&limit=20"
```

### Response
```json
[
  {
    "id": 1,
    "event_id": "12345",
    "occurred_at": "2025-06-29T12:00:00Z",
    "processed_at": "2025-06-29T12:05:00Z",
    "source": "reddit",
    "source_id": "r/technology",
    "sentiment_score": 0.85,
    "sentiment_label": "positive",
    "confidence": 0.92,
    "model_version": "ProsusAI/finbert-v1.1",
    "raw_text": "This new technology is revolutionary!"
  },
  {
    "id": 2,
    "event_id": "12346",
    "occurred_at": "2025-06-29T12:15:00Z",
    "processed_at": "2025-06-29T12:20:00Z",
    "source": "twitter",
    "source_id": "@user123",
    "sentiment_score": -0.67,
    "sentiment_label": "negative",
    "confidence": 0.78,
    "model_version": "ProsusAI/finbert-v1.1",
    "raw_text": "Not impressed with the latest update."
  }
]
```

### Python Example with Filtering
```python
import requests
from datetime import datetime, timedelta

# Query events from the last 24 hours with positive sentiment
end_date = datetime.now()
start_date = end_date - timedelta(days=1)

params = {
    'sentiment_label': 'positive',
    'start_date': start_date.isoformat(),
    'end_date': end_date.isoformat(),
    'source': 'reddit',
    'limit': 100
}

response = requests.get('http://localhost:8001/api/v1/sentiment/events', params=params)
events = response.json()

print(f"Found {len(events)} positive Reddit events in the last 24 hours")
for event in events[:5]:  # Show first 5
    print(f"- {event['sentiment_label']} ({event['confidence']:.2%}): {event['raw_text'][:50]}...")
```

---

## 5. Query Aggregated Metrics

### Basic Metrics Query
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/metrics"
```

### With Filters
```bash
curl -X GET "http://localhost:8001/api/v1/sentiment/metrics?source=reddit&metric_name=event_count&limit=20"
```

### Response
```json
[
  {
    "id": 1,
    "timestamp": "2025-06-29T12:00:00Z",
    "source": "reddit",
    "source_id": "r/technology",
    "label": "positive",
    "model_version": "ProsusAI/finbert-v1.1",
    "metric_name": "event_count",
    "metric_value": 45.0
  },
  {
    "id": 2,
    "timestamp": "2025-06-29T12:00:00Z",
    "source": "reddit",
    "source_id": "r/technology",
    "label": "negative",
    "model_version": "ProsusAI/finbert-v1.1",
    "metric_name": "event_count",
    "metric_value": 12.0
  }
]
```

---

## Error Handling

### Validation Error (422)
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "text"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Server Error (500)
```json
{
  "detail": "Analysis failed: Model not available"
}
```

### Rate Limiting (429)
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

---

## Advanced Usage Patterns

### 1. Batch Processing with Error Handling
```python
import requests
import time
from typing import List, Dict

def analyze_texts_with_retry(texts: List[str], max_retries: int = 3) -> List[Dict]:
    """Analyze texts with automatic retry on failure."""
    url = "http://localhost:8001/api/v1/sentiment/analyze/bulk"
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url, 
                json={"texts": [{"text": text} for text in texts]},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return []

# Usage
texts = ["Great product!", "Not bad", "Terrible experience"]
results = analyze_texts_with_retry(texts)
```

### 2. Streaming Results with Pagination
```python
import requests
from typing import Iterator, Dict

def stream_sentiment_events(source: str = None, limit: int = 100) -> Iterator[Dict]:
    """Stream all sentiment events using cursor-based pagination."""
    url = "http://localhost:8001/api/v1/sentiment/events"
    cursor = None
    
    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if source:
            params["source"] = source
            
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        events = response.json()
        if not events:
            break
            
        for event in events:
            yield event
            
        # Get cursor for next page (if available in response headers or last event)
        if len(events) < limit:
            break
        
        # Create cursor from last event (simplified)
        last_event = events[-1]
        cursor = f"{last_event['processed_at']}_{last_event['id']}"

# Usage
for event in stream_sentiment_events(source="reddit"):
    print(f"{event['sentiment_label']}: {event['raw_text'][:50]}...")
```

### 3. Real-time Monitoring
```python
import requests
import time
from datetime import datetime, timezone

def monitor_sentiment_stream(interval: int = 60):
    """Monitor sentiment analysis in real-time."""
    last_check = datetime.now(timezone.utc)
    
    while True:
        try:
            # Get recent events
            params = {
                'start_date': last_check.isoformat(),
                'limit': 1000
            }
            
            response = requests.get(
                'http://localhost:8001/api/v1/sentiment/events',
                params=params
            )
            events = response.json()
            
            if events:
                print(f"New events: {len(events)}")
                
                # Analyze sentiment distribution
                sentiment_counts = {}
                for event in events:
                    label = event['sentiment_label']
                    sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
                
                print(f"Sentiment distribution: {sentiment_counts}")
                last_check = datetime.now(timezone.utc)
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("Monitoring stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(interval)

# Usage
monitor_sentiment_stream(interval=30)  # Check every 30 seconds
```

---

## Best Practices

1. **Rate Limiting**: Respect rate limits and implement exponential backoff
2. **Error Handling**: Always handle HTTP errors and validation errors
3. **Timeouts**: Set appropriate timeouts for requests
4. **Batch Processing**: Use bulk endpoints for multiple texts
5. **Pagination**: Use cursor-based pagination for large datasets
6. **Monitoring**: Implement health checks and monitoring
7. **Caching**: Cache results when appropriate to reduce API calls

---

## OpenAPI Documentation

When running in debug mode, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

These interfaces provide:
- Interactive API testing
- Request/response schemas
- Authentication details
- Example requests and responses
