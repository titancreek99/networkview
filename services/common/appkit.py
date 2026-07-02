"""
appkit - tiny shared toolkit for every NetworkView Flask service.

Provides three things every app in the lab needs:

  1. JSON structured logging that fans out to stdout *and* to a shared
     /logs/<app>.log file (so the logviewer service can render it).
  2. A ControlStore backed by a shared /control/state.json file - the
     "control plane" the manager writes to and the apps read from
     (active backend version, feature flags, etc).
  3. make_app(): a Flask factory that wires request logging, /healthz,
     and /whoami into every service consistently.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request

APP_NAME = os.environ.get("APP_NAME", "app")
APP_VERSION = os.environ.get("APP_VERSION", "v1")
LOG_DIR = os.environ.get("LOG_DIR", "/logs")
CONTROL_FILE = os.environ.get("CONTROL_FILE", "/control/state.json")
HOSTNAME = socket.gethostname()


# --------------------------------------------------------------------------- #
# Structured logging
# --------------------------------------------------------------------------- #
class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "app": APP_NAME,
            "host": HOSTNAME,
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        if isinstance(record.args, dict):
            payload.update(record.args)  # allow logger.info("m", {"k": v})
        for key in ("event", "method", "path", "status", "duration_ms",
                    "upstream", "proto", "peer", "extra"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = JsonLineFormatter()
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    try:
        fileh = logging.FileHandler(os.path.join(LOG_DIR, f"{APP_NAME}.log"))
        fileh.setFormatter(fmt)
        logger.addHandler(fileh)
    except OSError:
        pass  # /logs not mounted - stdout only
    logger.propagate = False
    return logger


# --------------------------------------------------------------------------- #
# Control plane store (shared JSON file)
# --------------------------------------------------------------------------- #
DEFAULT_STATE = {
    "active_backend_version": "v1",
    "traffic": {"running": False, "rps": 2, "mix": ["https13", "http", "https12"]},
    "fault_injection": {"backend_latency_ms": 0, "backend_error_rate": 0.0},
}


class ControlStore:
    """Dead-simple JSON file store. Good enough for a single-host lab."""

    def __init__(self, path: str = CONTROL_FILE):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            self.write(DEFAULT_STATE)

    def read(self) -> dict:
        try:
            with open(self.path) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_STATE)

    def write(self, state: dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, self.path)  # atomic

    def update(self, patch: dict) -> dict:
        state = self.read()
        _deep_merge(state, patch)
        self.write(state)
        return state


def _deep_merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


# --------------------------------------------------------------------------- #
# Flask factory
# --------------------------------------------------------------------------- #
def make_app() -> tuple[Flask, logging.Logger]:
    app = Flask(APP_NAME)
    log = configure_logging()

    @app.before_request
    def _start_timer():
        g._t0 = time.time()

    @app.after_request
    def _log_request(resp):
        if request.path == "/healthz":
            return resp
        dur = round((time.time() - getattr(g, "_t0", time.time())) * 1000, 1)
        log.info("request", extra={
            "event": "http_request",
            "method": request.method,
            "path": request.path,
            "status": resp.status_code,
            "duration_ms": dur,
            "proto": request.headers.get("X-Forwarded-Proto", request.scheme),
            "peer": request.headers.get("X-Forwarded-For", request.remote_addr),
        })
        resp.headers["X-Served-By"] = f"{APP_NAME}/{HOSTNAME}"
        return resp

    @app.get("/healthz")
    def _healthz():
        return jsonify(status="ok", app=APP_NAME, host=HOSTNAME)

    @app.get("/whoami")
    def _whoami():
        return jsonify(app=APP_NAME, host=HOSTNAME, version=APP_VERSION)

    return app, log
