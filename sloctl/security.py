"""Redact active credential values from exported or displayed structures."""

import os
from typing import Any


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if k.lower()
                in {"dd-api-key", "dd-application-key", "api_key", "app_key", "token", "password"}
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for name in ("DD_API_KEY", "DD_APP_KEY"):
            secret = os.getenv(name)
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value
