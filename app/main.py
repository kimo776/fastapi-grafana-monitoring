import time
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI(title="TableCRM DevOps Test", version="1.0.0")

REQUEST_COUNT = Counter("http_requests_total","Total HTTP requests",["method","path","status"])
REQUEST_ERRORS = Counter("http_request_errors_total","Total HTTP errors",["method","path","exception"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds","Request latency seconds",
                            ["method","path"], buckets=(0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0,2.0,5.0))
INPROGRESS = Gauge("inprogress_requests","In-progress HTTP requests")

class MetricsMW(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter(); INPROGRESS.inc()
        try:
            resp = await call_next(request)
            dur = time.perf_counter() - start
            REQUEST_LATENCY.labels(request.method, request.url.path).observe(dur)
            REQUEST_COUNT.labels(request.method, request.url.path, str(resp.status_code)).inc()
            return resp
        except Exception as exc:
            dur = time.perf_counter() - start
            REQUEST_LATENCY.labels(request.method, request.url.path).observe(dur)
            REQUEST_COUNT.labels(request.method, request.url.path, "500").inc()
            REQUEST_ERRORS.labels(request.method, request.url.path, exc.__class__.__name__).inc()
            return JSONResponse({"detail":"internal error"}, status_code=500)
        finally:
            INPROGRESS.dec()

app.add_middleware(MetricsMW)

@app.get("/healthz")
def healthz(): return {"status":"ok"}

@app.get("/echo")
def echo(msg: Optional[str]="hello"): return {"echo": msg}

@app.get("/boom")
def boom(): raise RuntimeError("boom")

@app.get("/metrics")
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
