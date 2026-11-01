# Reliability report

Generated configuration and synthetic observations. Not live service reliability.

```json
{
  "services": [
    {
      "budget": {
        "allowed_bad_events": 10.0,
        "availability": 90.0,
        "bad_events": 1000,
        "burn_rate": 100.0,
        "consumption": 100.0,
        "remaining_bad_events": -990.0,
        "status": "observed"
      },
      "definition": {
        "alerts": [
          {
            "burn_rate": 14.4,
            "long_hours": 1,
            "name": "fast",
            "short_minutes": 5
          },
          {
            "burn_rate": 6.0,
            "long_hours": 6,
            "name": "slow",
            "short_minutes": 30
          }
        ],
        "days": 30,
        "good_query": "sum:public_api.good{*}.as_count()",
        "kind": "availability",
        "latency_threshold_ms": null,
        "name": "public-api",
        "target": 99.9,
        "total_query": "sum:public_api.total{*}.as_count()",
        "version": 1
      },
      "monitors": [
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "public-api: fast",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 14.4
            }
          },
          "query": "burn_rate(\"REF:public-api\").over(\"30d\").long_window(\"1h\").short_window(\"5m\") > 14.4",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:public-api:fast"
          ],
          "type": "slo alert"
        },
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "public-api: slow",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 6.0
            }
          },
          "query": "burn_rate(\"REF:public-api\").over(\"30d\").long_window(\"6h\").short_window(\"30m\") > 6.0",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:public-api:slow"
          ],
          "type": "slo alert"
        }
      ],
      "slo": {
        "name": "public-api",
        "query": {
          "denominator": "sum:public_api.total{*}.as_count()",
          "numerator": "sum:public_api.good{*}.as_count()"
        },
        "tags": [
          "managed-by:sloctl",
          "sloctl-id:public-api"
        ],
        "thresholds": [
          {
            "target": 99.9,
            "timeframe": "30d"
          }
        ],
        "type": "metric"
      }
    },
    {
      "budget": {
        "allowed_bad_events": 5.0,
        "availability": 90.0,
        "bad_events": 1000,
        "burn_rate": 200.0,
        "consumption": 200.0,
        "remaining_bad_events": -995.0,
        "status": "observed"
      },
      "definition": {
        "alerts": [
          {
            "burn_rate": 14.4,
            "long_hours": 1,
            "name": "fast",
            "short_minutes": 5
          },
          {
            "burn_rate": 6.0,
            "long_hours": 6,
            "name": "slow",
            "short_minutes": 30
          }
        ],
        "days": 30,
        "good_query": "sum:auth_api.good{*}.as_count()",
        "kind": "success",
        "latency_threshold_ms": null,
        "name": "auth-api",
        "target": 99.95,
        "total_query": "sum:auth_api.total{*}.as_count()",
        "version": 1
      },
      "monitors": [
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "auth-api: fast",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 14.4
            }
          },
          "query": "burn_rate(\"REF:auth-api\").over(\"30d\").long_window(\"1h\").short_window(\"5m\") > 14.4",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:auth-api:fast"
          ],
          "type": "slo alert"
        },
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "auth-api: slow",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 6.0
            }
          },
          "query": "burn_rate(\"REF:auth-api\").over(\"30d\").long_window(\"6h\").short_window(\"30m\") > 6.0",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:auth-api:slow"
          ],
          "type": "slo alert"
        }
      ],
      "slo": {
        "name": "auth-api",
        "query": {
          "denominator": "sum:auth_api.total{*}.as_count()",
          "numerator": "sum:auth_api.good{*}.as_count()"
        },
        "tags": [
          "managed-by:sloctl",
          "sloctl-id:auth-api"
        ],
        "thresholds": [
          {
            "target": 99.95,
            "timeframe": "30d"
          }
        ],
        "type": "metric"
      }
    },
    {
      "budget": {
        "allowed_bad_events": 50.0,
        "availability": 90.0,
        "bad_events": 1000,
        "burn_rate": 20.0,
        "consumption": 20.0,
        "remaining_bad_events": -950.0,
        "status": "observed"
      },
      "definition": {
        "alerts": [
          {
            "burn_rate": 14.4,
            "long_hours": 1,
            "name": "fast",
            "short_minutes": 5
          },
          {
            "burn_rate": 6.0,
            "long_hours": 6,
            "name": "slow",
            "short_minutes": 30
          }
        ],
        "days": 30,
        "good_query": "sum:background_processing.good{*}.as_count()",
        "kind": "success",
        "latency_threshold_ms": null,
        "name": "background-processing",
        "target": 99.5,
        "total_query": "sum:background_processing.total{*}.as_count()",
        "version": 1
      },
      "monitors": [
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "background-processing: fast",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 14.4
            }
          },
          "query": "burn_rate(\"REF:background-processing\").over(\"30d\").long_window(\"1h\").short_window(\"5m\") > 14.4",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:background-processing:fast"
          ],
          "type": "slo alert"
        },
        {
          "message": "Investigate the service error budget. See the service runbook.",
          "name": "background-processing: slow",
          "options": {
            "notify_no_data": false,
            "thresholds": {
              "critical": 6.0
            }
          },
          "query": "burn_rate(\"REF:background-processing\").over(\"30d\").long_window(\"6h\").short_window(\"30m\") > 6.0",
          "tags": [
            "managed-by:sloctl",
            "sloctl-id:background-processing:slow"
          ],
          "type": "slo alert"
        }
      ],
      "slo": {
        "name": "background-processing",
        "query": {
          "denominator": "sum:background_processing.total{*}.as_count()",
          "numerator": "sum:background_processing.good{*}.as_count()"
        },
        "tags": [
          "managed-by:sloctl",
          "sloctl-id:background-processing"
        ],
        "thresholds": [
          {
            "target": 99.5,
            "timeframe": "30d"
          }
        ],
        "type": "metric"
      }
    }
  ],
  "synthetic": true
}
```
