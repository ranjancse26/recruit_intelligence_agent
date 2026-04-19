import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.monitoring import (
    setup_opentelemetry,
    structured_logger,
    cost_tracker,
    TracingContext,
    trace,
    trace_id_var,
    calculate_cost
)
from app.routes import router

ESTIMATED_PROMPT_TOKENS = 100
ESTIMATED_COMPLETION_TOKENS = 200


@asynccontextmanager
async def lifespan(app: FastAPI):
    otlp_endpoint = None
    
    structured_logger.info("Starting Recruit Intelligence Agent", version="1.0.0")
    
    try:
        setup_opentelemetry(
            service_name="recruit-intelligence-agent",
            otlp_endpoint=otlp_endpoint,
            log_level="INFO"
        )
        structured_logger.info("OpenTelemetry initialized")
    except Exception as e:
        structured_logger.warning(f"OpenTelemetry setup failed: {str(e)}")
    
    yield
    
    cost_summary = cost_tracker.get_summary()
    structured_logger.info("Shutting down", cost_summary=cost_summary)


app = FastAPI(
    title="Recruit Intelligence Agent",
    description="AI-powered recruitment assistant for screening candidates, answering hiring questions etc.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    trace_id_var.set(trace_id)
    
    start_time = time.time()
    
    structured_logger.info(
        f"Request: {request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        trace_id=trace_id
    )
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    
    structured_logger.info(
        f"Response: {response.status_code} from {request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms
    )
    
    model = "gpt-5-mini"
    cost = calculate_cost(ESTIMATED_PROMPT_TOKENS, ESTIMATED_COMPLETION_TOKENS, 0, model)
    cost_tracker.record(
        prompt_tokens=ESTIMATED_PROMPT_TOKENS,
        completion_tokens=ESTIMATED_COMPLETION_TOKENS,
        total_tokens=0,
        model=model
    )
    
    response.headers["X-Trace-ID"] = trace_id
    return response


app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "recruit-intelligence-agent"}


@app.get("/metrics/costs")
async def get_cost_summary():
    return cost_tracker.get_summary()