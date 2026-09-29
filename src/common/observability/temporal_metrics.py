"""Prometheus metrics for Temporal workers.

The Temporal SDK exposes its own metrics (workflow/activity task latencies,
schedule-to-start latency, poller counts, ...) through a Prometheus scrape
endpoint. Those are the series the community dashboards at
https://github.com/temporalio/dashboards expect, so a worker only has to
start that endpoint; nothing here counts anything by hand.

Usage: build one Runtime per process and pass it to every Client.

    client = await Client.connect("localhost:7233", runtime=build_temporal_runtime())

Env:
    TEMPORAL_METRICS_ADDR   host:port to serve /metrics on (default 0.0.0.0:9464).
                            Set it to an empty string to disable the endpoint.
"""

import os

from temporalio.runtime import PrometheusConfig, Runtime, TelemetryConfig

DEFAULT_METRICS_ADDR = "0.0.0.0:9464"


def build_temporal_runtime(bind_address: str | None = None) -> Runtime:
    """Return a Runtime that serves SDK metrics in Prometheus format.

    `bind_address` overrides TEMPORAL_METRICS_ADDR. With no address (empty
    string) the default Runtime is returned and no port is opened.
    """
    if bind_address is None:
        bind_address = os.getenv("TEMPORAL_METRICS_ADDR", DEFAULT_METRICS_ADDR)
    if not bind_address:
        return Runtime.default()
    return Runtime(
        telemetry=TelemetryConfig(metrics=PrometheusConfig(bind_address=bind_address))
    )
