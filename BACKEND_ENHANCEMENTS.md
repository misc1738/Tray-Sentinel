# Backend Enhancements - API Documentation

**Date:** March 23, 2026  
**Version:** Enhanced v0.2.0

## Overview

This document covers the new backend enhancements added to Tracey's Sentinel, including:
- Advanced Audit Logging with query capabilities
- Search & filtering for evidence and cases
- Rate limiting middleware
- Webhook support for event notifications
- Performance metrics collection & monitoring

---

## 1. Advanced Audit Logging

### Features

- **Comprehensive Event Logging**: Records all significant events (evidence intake, custody actions, verifications, etc.)
- **Flexible Querying**: Filter by event type, actor, resource, status, and time range
- **Compliance Reporting**: Generate compliance reports from audit trails
- **Actor Activity Tracking**: Monitor individual user/organization activity

### Endpoints

#### Query Audit Logs
```
GET /audit/logs
```
Query parameters:
- `event_type` (optional): Filter by event type
- `actor_user_id` (optional): Filter by user
- `status` (optional): Filter by status (SUCCESS, FAILURE, PARTIAL)
- `limit` (default: 50, max: 500): Number of results
- `offset` (default: 0): Pagination offset

Response:
```json
{
  "logs": [
    {
      "audit_id": "uuid",
      "event_type": "EVIDENCE_INTAKE",
      "actor_user_id": "detective_1",
      "actor_org_id": "LAPD",
      "resource_type": "evidence",
      "resource_id": "evidence_uuid",
      "action": "INTAKE",
      "details": {...},
      "status": "SUCCESS",
      "timestamp": "2026-03-23T10:30:00Z",
      "ip_address": "192.168.1.1"
    }
  ],
  "count": 10,
  "limit": 50,
  "offset": 0
}
```

#### Get Actor Activity
```
GET /audit/actor/{actor_user_id}
```
Query parameters:
- `days` (default: 30): Look back N days
- `limit` (default: 50): Number of results

Returns all actions performed by a specific user in the past N days.

#### Get Resource Audit Trail
```
GET /audit/resource/{resource_type}/{resource_id}
```

Returns complete audit trail for a specific resource (e.g., evidence, case).

#### Get Failed Actions
```
GET /audit/failed-actions
```
Query parameters:
- `days` (default: 7): Look back N days
- `limit` (default: 100): Number of results

Returns all failed or partial actions for alerting and investigation.

#### Compliance Report
```
GET /audit/compliance-report
```
Query parameters:
- `days` (default: 30): Report period

Returns:
```json
{
  "period_days": 30,
  "start_time": "2026-02-21T...",
  "event_summary": {
    "EVIDENCE_INTAKE": {
      "total": 150,
      "success": 148,
      "failure": 1,
      "partial": 1
    }
  },
  "org_activity": {
    "LAPD": 85,
    "FBI": 65
  }
}
```

---

## 2. Search & Filtering

### Features

- **Full-Text Search**: Find evidence by description, file name, acquisition method
- **Advanced Filtering**: Filter by case, date range, status
- **Related Evidence**: Discover related evidence in the same case
- **Search Statistics**: Monitor search index health

### Endpoints

#### Search Evidence
```
POST /search
```
Request:
```json
{
  "query": "DNA sample",
  "case_id": "case_123",
  "status": "active",
  "created_after": "2026-01-01T00:00:00Z",
  "limit": 50,
  "offset": 0
}
```

Response:
```json
{
  "results": [
    {
      "id": "evidence:uuid",
      "type": "evidence",
      "title": "evidence_uuid",
      "description": "DNA sample from victim...",
      "case_id": "case_123",
      "created_at": "2026-03-20T...",
      "relevance_score": 0.95
    }
  ],
  "total": 156,
  "limit": 50,
  "offset": 0
}
```

#### Get Case Evidence
```
GET /case/{case_id}/evidence
```

Returns all evidence items for a specific case with search metadata.

#### Get Related Evidence
```
GET /evidence/{evidence_id}/related?limit=10
```

Finds related evidence from the same case.

#### Search Statistics
```
GET /search/statistics
```

Returns:
```json
{
  "resources": {
    "evidence": {
      "count": 5000,
      "unique_cases": 250
    }
  },
  "total_cases": 250
}
```

---

## 3. Rate Limiting

### Features

- **Per-IP Rate Limiting**: 100 requests per minute per IP
- **Automatic Cleanup**: Old records cleaned up after 24 hours
- **Configurable Thresholds**: Easy to adjust limits in code

### Behavior

- **GET requests**: Exempt from rate limiting (keep API accessible)
- **POST/PUT/DELETE**: Limited to 100 requests per 60-second window
- **403 Response**: Exceeding limits returns "Rate limit exceeded"
- **Headers**: Response includes rate limit info:
  - `X-RateLimit-Limit: 100`
  - `X-RateLimit-Window: 60`

### Example

```
# First 100 POST requests within 60 seconds: ✅ 200 OK
POST /evidence/intake

# Request 101+: ❌ 429 Too Many Requests
{
  "detail": "Rate limit exceeded. Max 100 requests per minute."
}
```

---

## 4. Webhooks

### Features

- **Event-Driven Notifications**: Subscribe to specific events
- **Multiple Event Types**: INTAKE, CUSTODY_ACTION, ENDORSEMENT, VERIFICATION, REPORT_GENERATED, etc.
- **Delivery Tracking**: Monitor webhook delivery success/failure
- **Retry Logic**: Automatic retry on failures

### Event Types

```
evidence.intake
custody.action
endorsement.request
endorsement.complete
verification.result
report.generated
alert.created
incident.opened
incident.resolved
```

### Endpoints

#### Create Subscription
```
POST /webhooks/subscribe
```
Request:
```json
{
  "url": "https://events.example.com/sentinel",
  "events": ["evidence.intake", "custody.action"],
  "secret": "optional_signing_secret"
}
```

Response:
```json
{
  "subscription_id": "sub_uuid",
  "url": "https://events.example.com/sentinel",
  "events": ["evidence.intake", "custody.action"],
  "active": true,
  "created_at": "2026-03-23T..."
}
```

#### List Subscriptions
```
GET /webhooks/subscriptions?active_only=true
```

#### Delete Subscription
```
DELETE /webhooks/{subscription_id}
```

#### Toggle Subscription
```
PUT /webhooks/{subscription_id}/toggle?active=false
```

#### Delivery History
```
GET /webhooks/{subscription_id}/deliveries?limit=50
```

Response:
```json
{
  "subscription_id": "sub_uuid",
  "deliveries": [
    {
      "delivery_id": "uuid",
      "subscription_id": "sub_uuid",
      "event": "evidence.intake",
      "status_code": 200,
      "response_body": "{...}",
      "error_message": null,
      "delivered_at": "2026-03-23T10:30:15Z",
      "created_at": "2026-03-23T10:30:15Z"
    }
  ]
}
```

### Webhook Payload Format

```json
{
  "event": "evidence.intake",
  "timestamp": "2026-03-23T10:30:00Z",
  "subscription_id": "sub_uuid",
  "data": {
    "evidence_id": "ev_uuid",
    "case_id": "case_123",
    "file_name": "sample.bin",
    "sha256": "abcd1234...",
    "actor_user_id": "detective_1",
    "actor_org_id": "LAPD"
  },
  "signature": "optional_hmac_signature"
}
```

---

## 5. Performance Metrics

### Features

- **API Performance Tracking**: Latency, status codes, endpoint statistics
- **Slow Query Detection**: Identify performance bottlenecks
- **System Health Monitoring**: Overall system status
- **Custom Metric Recording**: Track application-specific metrics

### Endpoints

#### API Statistics
```
GET /metrics/api-statistics?hours=24
```

Response:
```json
{
  "period_hours": 24,
  "total_requests": 5432,
  "avg_response_time_ms": 145.3,
  "min_response_time_ms": 12,
  "max_response_time_ms": 3456,
  "error_count": 23,
  "by_endpoint": [
    {
      "endpoint": "/evidence/intake",
      "method": "POST",
      "request_count": 1200,
      "avg_response_time_ms": 245.5,
      "max_response_time_ms": 2345,
      "errors": 5
    }
  ],
  "by_status_code": {
    "200": 5200,
    "201": 180,
    "400": 18,
    "403": 5,
    "429": 29
  }
}
```

#### Slow Endpoints
```
GET /metrics/slow-endpoints?hours=24&threshold_ms=500&limit=20
```

Returns endpoints with response times > threshold.

#### System Health
```
GET /metrics/health
```

Response:
```json
{
  "status": "healthy",
  "error_rate_percent": 0.42,
  "requests_past_hour": 450,
  "avg_response_time_ms": 142
}
```

#### Metric History
```
GET /metrics/metric/{metric_name}?hours=24&limit=1000
```

Track custom measurements over time.

---

## Integration Examples

### Example 1: Track Evidence Intake Completion

```python
# Python client
import requests

url = "http://localhost:8000/audit/logs"
params = {
    "event_type": "EVIDENCE_INTAKE",
    "status": "SUCCESS",
    "days": 7
}

response = requests.get(url, params=params, headers={
    "Authorization": "Bearer token"
})

intakes = response.json()["logs"]
print(f"Evidence intakes completed: {len(intakes)}")
```

### Example 2: Monitor Slow API Endpoints

```python
# Identify performance issues
response = requests.get(
    "http://localhost:8000/metrics/slow-endpoints",
    params={"threshold_ms": 1000}
)

slow = response.json()["slow_endpoints"]
for endpoint in slow:
    print(f"{endpoint['endpoint']} took {endpoint['response_time_ms']}ms")
```

### Example 3: Search for Evidence by Case

```python
# Find all DNA evidence in case #123
response = requests.post(
    "http://localhost:8000/search",
    json={
        "query": "DNA",
        "case_id": "case_123"
    }
)

results = response.json()["results"]
for ev in results:
    print(f"Found: {ev['title']} ({ev['relevance_score']})")
```

### Example 4: Setup Webhook Notifications

```python
# Subscribe to evidence intake events
response = requests.post(
    "http://localhost:8000/webhooks/subscribe",
    json={
        "url": "https://myapp.example.com/sentinelevents",
        "events": ["evidence.intake", "custody.action"],
        "secret": "my_webhook_secret"
    }
)

subscription_id = response.json()["subscription_id"]
print(f"Webhook active: {subscription_id}")
```

---

## Database Schema

All enhancements use SQLite tables in the main database:

- `audit_logs` - Event audit trail
- `search_index` - Full-text search index
- `rate_limits` - Rate limit tracking
- `webhook_subscriptions` - Webhook endpoints
- `webhook_deliveries` - Delivery attempt history
- `metrics` - Performance metrics
- `api_performance` - API call metrics

Indexes optimized for rapid querying by timestamp, actor, resource, and status.

---

## Security Considerations

1. **Audit Logging**: All access attempts are logged
2. **Rate Limiting**: Prevents abuse and denial-of-service
3. **Webhook Secrets**: Optional HMAC signing for webhook integrity
4. **Access Control**: All endpoints respect existing RBAC framework
5. **Data Retention**: Metrics automatically cleaned up after 30 days

---

## Performance Impact

- **Audit Logging**: ~5ms per event (async-friendly)
- **Search Indexing**: ~10ms per evidence item
- **Metrics Recording**: ~1ms per request
- **Rate Limiting**: ~2ms per request
- **Webhook Dispatch**: Asynchronous (non-blocking)

---

## Future Enhancements

- [ ] Elasticsearch integration for larger datasets
- [ ] Custom metric dashboards
- [ ] Advanced SIEM integration
- [ ] Machine learning anomaly detection
- [ ] GraphQL API layer
- [ ] Real-time event streaming (WebSocket)
- [ ] Batch webhook retries with exponential backoff
