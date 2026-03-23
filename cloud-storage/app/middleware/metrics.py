import time

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "cloud_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "cloud_request_duration_seconds",
    "HTTP request duration",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_REQUESTS = Gauge(
    "cloud_active_requests",
    "Currently active requests",
)

UPLOAD_BYTES = Counter(
    "cloud_upload_bytes_total",
    "Total bytes uploaded",
)

QUOTA_EXCEEDED = Counter(
    "cloud_quota_exceeded_total",
    "Number of quota exceeded errors",
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        endpoint = request.url.path
        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            duration = time.perf_counter() - start
            ACTIVE_REQUESTS.dec()
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=status_code,
            ).inc()
            REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)

        return response


async def metrics_endpoint(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
