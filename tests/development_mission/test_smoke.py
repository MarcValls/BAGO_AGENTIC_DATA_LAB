import pytest
from src.observability.otel_bridge import normalize_otlp_http_endpoint

def test_normalize_endpoint_success():
    # Test standard endpoint normalization
    assert normalize_otlp_http_endpoint("http://localhost:4318") == "http://localhost:4318/v1/traces"
    # Test endpoint that already has the path
    assert normalize_otlp_http_endpoint("http://localhost:4318/v1/traces") == "http://localhost:4318/v1/traces"
    # Test endpoint with trailing slash
    assert normalize_otlp_http_endpoint("http://localhost:4318/") == "http://localhost:4318/v1/traces"

def test_normalize_endpoint_empty():
    # Test that empty or whitespace strings raise ValueError
    with pytest.raises(ValueError, match="OTLP endpoint is required"):
        normalize_otlp_http_endpoint("")
    with pytest.raises(ValueError, match="OTLP endpoint is required"):
        normalize_otlp_http_endpoint("   ")
