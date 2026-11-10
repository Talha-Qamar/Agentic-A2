"""Trace context, metering and OpenTelemetry export (Arize Phoenix).

One trace id flows from the UI request -> API -> graph -> MCP servers -> audit log.
The id lives in a contextvar; MCP clients forward it as the ``X-Trace-Id`` header.
"""
from __future__ import annotations

import contextvars
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from .guardrails import mask_pii

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
meter_var: contextvars.ContextVar["Meter | None"] = contextvars.ContextVar("meter", default=None)
_tracer = None


def new_trace_id() -> str:
    return uuid.uuid4().hex


def current_trace_id() -> str:
    tid = trace_id_var.get()
    if not tid:
        tid = new_trace_id()
        trace_id_var.set(tid)
    return tid


@dataclass
class LLMCall:
    node: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    cost_usd: float
    fallback: bool = False
    error: str | None = None
    ts: float = field(default_factory=time.time)


@dataclass
class Meter:
    """Collects every LLM call of a run: tokens, latency and cost per node."""
    calls: list[LLMCall] = field(default_factory=list)

    def add(self, call: LLMCall) -> None:
        self.calls.append(call)

    @property
    def tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.calls)

    @property
    def cost(self) -> float:
        return round(sum(c.cost_usd for c in self.calls), 6)

    def by_node(self) -> dict:
        out: dict[str, dict] = {}
        for c in self.calls:
            d = out.setdefault(c.node, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "latency_s": 0.0})
            d["calls"] += 1
            d["input_tokens"] += c.input_tokens
            d["output_tokens"] += c.output_tokens
            d["cost_usd"] = round(d["cost_usd"] + c.cost_usd, 6)
            d["latency_s"] = round(d["latency_s"] + c.latency_s, 3)
        return out

    def dump(self) -> list[dict]:
        return [asdict(c) for c in self.calls]


@contextmanager
def metering():
    m = Meter()
    tok = meter_var.set(m)
    try:
        yield m
    finally:
        meter_var.reset(tok)


def record(call: LLMCall) -> None:
    m = meter_var.get()
    if m is not None:
        m.add(call)
    span_event("llm_call", {"node": call.node, "model": call.model, "input_tokens": call.input_tokens,
                            "output_tokens": call.output_tokens, "cost_usd": call.cost_usd, "latency_s": call.latency_s,
                            "fallback": call.fallback})


# ------------------------------------------------------------------ OpenTelemetry / Phoenix
def setup_tracing(service: str = "gigbid") -> None:
    """Export spans to Phoenix if PHOENIX_COLLECTOR_ENDPOINT is set. Safe to call many times."""
    global _tracer
    if _tracer is not None:
        return
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT")
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        provider = TracerProvider(resource=Resource.create({"service.name": service, "openinference.project.name": "gigbid"}))
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
            try:
                from openinference.instrumentation.langchain import LangChainInstrumentor
                LangChainInstrumentor().instrument(tracer_provider=provider)
            except Exception:  # noqa: BLE001
                pass
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service)
    except Exception:  # noqa: BLE001 - tracing must never break the app
        _tracer = False


@contextmanager
def span(name: str, attrs: dict | None = None):
    setup_tracing()
    if not _tracer:
        yield None
        return
    with _tracer.start_as_current_span(name) as s:
        s.set_attribute("gigbid.trace_id", current_trace_id())
        for k, v in (attrs or {}).items():
            s.set_attribute(k, mask_pii(str(v)) if isinstance(v, str) else v)
        yield s


def span_event(name: str, attrs: dict) -> None:
    try:
        from opentelemetry import trace
        s = trace.get_current_span()
        if s and s.is_recording():
            s.add_event(name, {k: (mask_pii(v) if isinstance(v, str) else v) for k, v in attrs.items() if v is not None})
    except Exception:  # noqa: BLE001
        pass


def phoenix_link(trace_id: str) -> str | None:
    base = os.environ.get("PHOENIX_PUBLIC_URL")
    return f"{base.rstrip('/')}/projects?traceId={trace_id}" if base else None
