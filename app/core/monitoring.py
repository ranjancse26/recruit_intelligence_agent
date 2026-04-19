import logging
import time
import json
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from collections import defaultdict
import threading

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost(self) -> float:
        return calculate_cost(self.prompt_tokens, self.completion_tokens, self.total_tokens)


def calculate_cost(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model: str = "gpt-4"
) -> float:
    pricing = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
        "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        "gpt-5-mini": {"prompt": 0.001, "completion": 0.0015},
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4o-mini-2024-07-18": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4-turbo": {"prompt": 0.005, "completion": 0.015},
        "gpt-4-turbo-2024-04-09": {"prompt": 0.005, "completion": 0.015},
        "gpt-3.5-turbo-0125": {"prompt": 0.0005, "completion": 0.0015},
        "gpt-3.5-turbo-1106": {"prompt": 0.001, "completion": 0.0015},
        "o1-preview": {"prompt": 0.01, "completion": 0.03},
        "o1-mini": {"prompt": 0.0011, "completion": 0.0044},
        "o1": {"prompt": 0.015, "completion": 0.06},
        "o3-mini": {"prompt": 0.0011, "completion": 0.0044},
        "o3-mini-high": {"prompt": 0.0011, "completion": 0.0044},
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-5-sonnet-20241022": {"prompt": 0.003, "completion": 0.015},
        "claude-3-5-sonnet-20240620": {"prompt": 0.003, "completion": 0.015},
        "claude-3-opus-20240229": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet-20240229": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        "claude-3-haiku-20240307": {"prompt": 0.00025, "completion": 0.00125},
        "claude-3-5-haiku": {"prompt": 0.0008, "completion": 0.0004},
        "claude-3-5-haiku-20241022": {"prompt": 0.0008, "completion": 0.0004},
        "claude-opus-4-20251114": {"prompt": 0.015, "completion": 0.075},
        "claude-sonnet-4-20251114": {"prompt": 0.003, "completion": 0.015},
        "claude-haiku-4-20251114": {"prompt": 0.0008, "completion": 0.0004},
        "gemini-1.5-pro": {"prompt": 0.00125, "completion": 0.005},
        "gemini-1.5-pro-002": {"prompt": 0.00125, "completion": 0.005},
        "gemini-1.5-flash": {"prompt": 0.000075, "completion": 0.0003},
        "gemini-1.5-flash-002": {"prompt": 0.000075, "completion": 0.0003},
        "gemini-1.5-flash-8b": {"prompt": 0.0000375, "completion": 0.00015},
        "gemini-1.5-flash-8b-001": {"prompt": 0.0000375, "completion": 0.00015},
        "gemini-2.0-pro-exp": {"prompt": 0.001, "completion": 0.005},
        "gemini-2.0-flash-exp": {"prompt": 0.0001, "completion": 0.0005},
        "gemini-2.0-flash": {"prompt": 0.0001, "completion": 0.0004},
        "gemini-1.0-pro": {"prompt": 0.00125, "completion": 0.005},
        "gemini-1.0-pro-002": {"prompt": 0.00125, "completion": 0.005},
        "gemini-1.0-ultra": {"prompt": 0.00125, "completion": 0.005},
        "mistral-large": {"prompt": 0.002, "completion": 0.006},
        "mistral-large-2411": {"prompt": 0.002, "completion": 0.006},
        "mistral-small": {"prompt": 0.0002, "completion": 0.0006},
        "mistral-small-2409": {"prompt": 0.0002, "completion": 0.0006},
        "mistral-nemo": {"prompt": 0.00015, "completion": 0.00015},
        "mistral-nemo-2407": {"prompt": 0.00015, "completion": 0.00015},
        "mixtral-8x7b": {"prompt": 0.00024, "completion": 0.00024},
        "mixtral-8x7b-instruct": {"prompt": 0.00024, "completion": 0.00024},
        "mixtral-8x22b": {"prompt": 0.00065, "completion": 0.00065},
        "mixtral-8x22b-instruct": {"prompt": 0.00065, "completion": 0.00065},
        "llama-3.1-405b": {"prompt": 0.0035, "completion": 0.0035},
        "llama-3.1-405b-instruct": {"prompt": 0.0035, "completion": 0.0035},
        "llama-3.1-70b": {"prompt": 0.0009, "completion": 0.0009},
        "llama-3.1-70b-instruct": {"prompt": 0.0009, "completion": 0.0009},
        "llama-3.1-8b": {"prompt": 0.0002, "completion": 0.0002},
        "llama-3.1-8b-instruct": {"prompt": 0.0002, "completion": 0.0002},
        "llama-3-70b": {"prompt": 0.0008, "completion": 0.0008},
        "llama-3-70b-instruct": {"prompt": 0.0008, "completion": 0.0008},
        "llama-3-8b": {"prompt": 0.0002, "completion": 0.0002},
        "llama-3-8b-instruct": {"prompt": 0.0002, "completion": 0.0002},
        "llama-2-70b": {"prompt": 0.0009, "completion": 0.0009},
        "llama-2-70b-chat": {"prompt": 0.0009, "completion": 0.0009},
        "llama-2-13b": {"prompt": 0.0002, "completion": 0.0002},
        "llama-2-13b-chat": {"prompt": 0.0002, "completion": 0.0002},
        "llama-2-7b": {"prompt": 0.0002, "completion": 0.0002},
        "llama-2-7b-chat": {"prompt": 0.0002, "completion": 0.0002},
        "command-r": {"prompt": 0.0003, "completion": 0.0006},
        "command-r-plus": {"prompt": 0.003, "completion": 0.015},
        "command-r-plus-08-2024": {"prompt": 0.003, "completion": 0.015},
        "command-r-08-2024": {"prompt": 0.0003, "completion": 0.0006},
        "ai21-jamba-1.5-large": {"prompt": 0.001, "completion": 0.005},
        "ai21-jamba-1.5-small": {"prompt": 0.0002, "completion": 0.0004},
        "j2-ultra": {"prompt": 0.003, "completion": 0.015},
        "j2-large": {"prompt": 0.0018, "completion": 0.009},
        "j2-mid": {"prompt": 0.0006, "completion": 0.003},
        "j2-light": {"prompt": 0.0004, "completion": 0.002},
        "j2-haiku": {"prompt": 0.0002, "completion": 0.001},
        "cohere-embed-multilingual-v3.0": {"prompt": 0.0001, "completion": 0.0},
        "cohere-embed-english-v3.0": {"prompt": 0.0001, "completion": 0.0},
        "cohere-embed-multilingual-v2.0": {"prompt": 0.0001, "completion": 0.0},
        "cohere-embed-english-v2.0": {"prompt": 0.0001, "completion": 0.0},
        "amazon-titan-embeddings-g1-text": {"prompt": 0.0001, "completion": 0.0},
        "amazon-titan-text-express": {"prompt": 0.0002, "completion": 0.00048},
        "amazon-titan-text-lite": {"prompt": 0.00015, "completion": 0.0002},
        "text-embedding-3-small": {"prompt": 0.00002, "completion": 0.0},
        "text-embedding-3-large": {"prompt": 0.00013, "completion": 0.0},
        "text-embedding-ada-002": {"prompt": 0.0001, "completion": 0.0},
        "text-embedding-ada-001": {"prompt": 0.0001, "completion": 0.0},
    }
    
    model_pricing = pricing.get(model, pricing["gpt-4"])
    
    if total_tokens > 0:
        prompt = total_tokens * model_pricing["prompt"] / 1000
        completion = 0
    else:
        prompt = prompt_tokens * model_pricing["prompt"] / 1000
        completion = completion_tokens * model_pricing["completion"] / 1000
    
    return prompt + completion


class CostTracker:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._costs: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_cost": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_requests": 0,
            "by_model": defaultdict(lambda: {"cost": 0.0, "requests": 0, "tokens": 0})
        })
        self._lock = threading.Lock()
    
    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        model: str = "gpt-4",
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ):
        with self._lock:
            cost = calculate_cost(prompt_tokens, completion_tokens, total_tokens, model)
            key = user_id or "default"
            
            self._costs[key]["total_cost"] += cost
            self._costs[key]["total_prompt_tokens"] += prompt_tokens
            self._costs[key]["total_completion_tokens"] += completion_tokens
            self._costs[key]["total_requests"] += 1
            
            self._costs[key]["by_model"][model]["cost"] += cost
            self._costs[key]["by_model"][model]["requests"] += 1
            self._costs[key]["by_model"][model]["tokens"] += total_tokens or (prompt_tokens + completion_tokens)
            
            return cost
    
    def get_summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            key = user_id or "default"
            
            if user_id:
                data = self._costs.get(key, {
                    "total_cost": 0.0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_requests": 0,
                    "by_model": {}
                })
                result = dict(data)
                result["by_model"] = {k: dict(v) for k, v in data.get("by_model", {}).items()}
                return result
            
            if not self._costs:
                return {
                    "default": {
                        "total_cost": 0.0,
                        "total_prompt_tokens": 0,
                        "total_completion_tokens": 0,
                        "total_requests": 0,
                        "by_model": {}
                    }
                }
            
            result = {}
            for k, v in self._costs.items():
                data = dict(v)
                data["by_model"] = {k2: dict(v2) for k2, v2 in v.get("by_model", {}).items()}
                result[k] = data
            return result
    
    def reset(self, user_id: Optional[str] = None):
        key = user_id or "default"
        with self._lock:
            if user_id:
                self._costs.pop(key, None)
            else:
                self._costs.clear()


class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.tracer = trace.get_tracer(name)
    
    def _format_message(
        self,
        message: str,
        level: LogLevel,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        trace_id = trace_id_var.get() or str(uuid.uuid4())
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.value,
            "message": message,
            "trace_id": trace_id,
            "service": "recruit-intelligence-agent",
        }
        
        if extra:
            log_entry["extra"] = extra
        
        return log_entry
    
    def _log(self, level: LogLevel, message: str, extra: Optional[Dict[str, Any]] = None):
        log_entry = self._format_message(message, level, extra)
        
        log_method = getattr(self.logger, level.value.lower())
        log_method(json.dumps(log_entry))
    
    def debug(self, message: str, **extra):
        self._log(LogLevel.DEBUG, message, extra)
    
    def info(self, message: str, **extra):
        self._log(LogLevel.INFO, message, extra)
    
    def warning(self, message: str, **extra):
        self._log(LogLevel.WARNING, message, extra)
    
    def error(self, message: str, **extra):
        self._log(LogLevel.ERROR, message, extra)
    
    def critical(self, message: str, **extra):
        self._log(LogLevel.CRITICAL, message, extra)
    
    def log_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None
    ):
        self.info(
            f"HTTP Request: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            params=params,
            body=body
        )
    
    def log_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        tokens: Optional[TokenUsage] = None
    ):
        extra = {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms
        }
        
        if tokens:
            extra["token_usage"] = asdict(tokens)
        
        self.info(
            f"HTTP Response: {status_code} from {method} {endpoint}",
            **extra
        )


def setup_opentelemetry(
    service_name: str = "recruit-intelligence-agent",
    otlp_endpoint: Optional[str] = None,
    log_level: str = "INFO"
):
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    trace.set_tracer_provider(provider)
    
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    )
    
    return trace.get_tracer(service_name)


class TracingContext:
    def __init__(self, tracer: Optional[trace.Tracer] = None):
        self.tracer = tracer or trace.get_tracer(__name__)
        self.current_span = None
    
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.current_span = self.tracer.start_span(name)
        
        if attributes:
            for key, value in attributes.items():
                self.current_span.set_attribute(key, str(value))
        
        trace_id = format(self.current_span.context.trace_id, '032x')
        trace_id_var.set(trace_id)
        
        return self.current_span
    
    def end_span(self, status: StatusCode = StatusCode.OK, message: str = ""):
        if self.current_span:
            self.current_span.set_status(Status(status, message))
            self.current_span.end()
            self.current_span = None
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        if self.current_span:
            self.current_span.add_event(name, attributes=attributes or {})
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.end_span(StatusCode.ERROR, str(exc_val))
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.end_span(StatusCode.ERROR, str(exc_val))
        return False

structured_logger = StructuredLogger("recruit-intelligence-agent")
cost_tracker = CostTracker()

class ModelCostBreakdown(BaseModel):
    cost: float
    requests: int
    tokens: int


class UserCostSummary(BaseModel):
    total_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_requests: int
    by_model: dict[str, ModelCostBreakdown]


class CostSummaryResponse(BaseModel):
    default: UserCostSummary