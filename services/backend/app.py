"""
backend - tier 3. The only service that talks to the database.

Serves a tiny "orders" API. Reflects the active version + injected faults from
the control plane so the manager can demonstrate blue/green version switching
and fault injection (latency / errors) that you can watch in the logs, LB
stats and packet captures.
"""
import os
import random
import time

import psycopg2
from flask import jsonify, request
from psycopg2.extras import RealDictCursor

import sys
sys.path.insert(0, "/app")
from common.appkit import make_app, ControlStore, APP_VERSION, HOSTNAME

app, log = make_app()
control = ControlStore()

DB_DSN = os.environ.get(
    "DB_DSN",
    "host=db port=5432 dbname=orders user=app password=app",
)


def db_conn():
    return psycopg2.connect(DB_DSN, cursor_factory=RealDictCursor)


def init_db(retries: int = 30):
    """Wait for Postgres then ensure schema + seed data exist."""
    for attempt in range(retries):
        try:
            with db_conn() as conn, conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id       SERIAL PRIMARY KEY,
                        customer TEXT NOT NULL,
                        item     TEXT NOT NULL,
                        amount   NUMERIC(10,2) NOT NULL,
                        created  TIMESTAMPTZ DEFAULT now()
                    );
                """)
                cur.execute("SELECT count(*) AS c FROM orders;")
                if cur.fetchone()["c"] == 0:
                    cur.executemany(
                        "INSERT INTO orders (customer, item, amount) VALUES (%s,%s,%s)",
                        [("acme", "widget", 9.99), ("globex", "gadget", 19.5),
                         ("initech", "gizmo", 4.25)],
                    )
                conn.commit()
            log.info("db ready", extra={"event": "db_init", "extra": {"attempt": attempt}})
            return
        except psycopg2.OperationalError as exc:
            log.info("waiting for db", extra={"event": "db_wait",
                     "extra": {"attempt": attempt, "err": str(exc)[:120]}})
            time.sleep(2)
    log.error("db never came up", extra={"event": "db_fail"})


def apply_faults():
    """Honor manager-injected latency/error faults from the control plane."""
    faults = control.read().get("fault_injection", {})
    lat = int(faults.get("backend_latency_ms", 0) or 0)
    if lat:
        time.sleep(lat / 1000.0)
    if random.random() < float(faults.get("backend_error_rate", 0.0) or 0.0):
        return True
    return False


@app.get("/api/orders")
def orders():
    if apply_faults():
        log.error("injected fault", extra={"event": "fault"})
        return jsonify(error="injected backend fault"), 503
    active = control.read().get("active_backend_version", "v1")
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders ORDER BY id;")
        rows = cur.fetchall()
    # v2 enriches each order with a computed field, so version switches are visible.
    if active == "v2":
        for r in rows:
            r["amount_with_tax"] = round(float(r["amount"]) * 1.2, 2)
    log.info("served orders", extra={"event": "orders",
             "extra": {"count": len(rows), "active_version": active}})
    return jsonify(
        served_by={"app": "backend", "host": HOSTNAME, "build_version": APP_VERSION,
                   "active_version": active},
        orders=[dict(r, amount=float(r["amount"])) for r in rows],
    )


@app.post("/api/orders")
def create_order():
    data = request.get_json(force=True, silent=True) or {}
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orders (customer, item, amount) VALUES (%s,%s,%s) RETURNING id",
            (data.get("customer", "anon"), data.get("item", "thing"),
             data.get("amount", 1.0)),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
    return jsonify(created=new_id), 201


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
