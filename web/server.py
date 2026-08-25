"""The API behind the page. Standard library only.

Deliberately small: a fork should be able to read the whole surface in one
sitting, which is itself part of the argument. Six endpoints, no framework, no
build step, no database.

Three rules are enforced here rather than in the page, because a rule the
browser enforces is a rule an attacker skips.

Free text never reaches a language model. The console's open field returns a
structural verdict only — the receipt, its digest, and the proof that neither
moved. Prose is reserved for the two built-in presets, which removes the abuse
surface instead of policing it.

Sabotage is replay, never a switch. The recording is generated offline and
served as data; there is no live path that disables the post-validator.

The counter never resets quietly. It carries the date it started counting from,
and that date is published next to it.
"""
import datetime
import errno
import json
import os
import socket
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from attacks import cases, runner
from explainer import client, explain, render
from gate import canonical, engine, examples, schema

ROOT = Path(__file__).resolve().parent
COUNTER_FILE = ROOT / "counter.json"
CANNED_FILE = ROOT / "canned.json"
SABOTAGE_FILE = ROOT / "sabotage.json"

# 7690 after the accent colour, #76B900. Off every default any other tool
# claims, so the demo does not fight a stray dev server for its port.
DEFAULT_PORT = 7690
COUNTING_SINCE = "2026-08-25"
RATE_LIMIT = (60, 60.0)          # requests per window, window in seconds
# The last few increments, kept so a jump in the count can be attributed. An
# unexplained counter is worth less than no counter: it was 33 once with no
# way to say what had incremented it, and that is the whole argument against
# publishing a number nobody can account for.
RECENT_KEPT = 25
MAX_BODY = 64 * 1024
# An oversized body is drained before it is refused, so the client gets a 413
# rather than a reset connection. Draining is itself capped: a refusal must not
# become a way to make the server read whatever it is handed.
DRAIN_CAP = 1024 * 1024
DRAIN_CHUNK = 64 * 1024

_hits = defaultdict(deque)


def _rate_limited(address):
    limit, window = RATE_LIMIT
    now = time.time()
    seen = _hits[address]
    while seen and now - seen[0] > window:
        seen.popleft()
    if len(seen) >= limit:
        return True
    seen.append(now)
    return False


def _load_counter():
    if COUNTER_FILE.exists():
        try:
            return json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"attacks_blocked": 0, "since": COUNTING_SINCE, "resets": [], "recent": []}


def _bump_counter(source):
    state = _load_counter()
    state["attacks_blocked"] += 1
    state.setdefault("since", COUNTING_SINCE)
    state.setdefault("resets", [])
    recent = state.setdefault("recent", [])
    recent.append({"source": source,
                   "at": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds")})
    del recent[:-RECENT_KEPT]
    COUNTER_FILE.write_text(json.dumps(state), encoding="utf-8")
    return state


def reset_counter(since, reason):
    """Start the count again, on the record.

    A counter that can be quietly zeroed is decoration. This one keeps every
    reset it has ever had, with the total it discarded and why, and the page
    shows the date the surviving count runs from.
    """
    state = _load_counter()
    state.setdefault("resets", []).append(
        {"at": since, "discarded_total": state["attacks_blocked"],
         "previous_since": state.get("since"), "reason": reason})
    state["attacks_blocked"] = 0
    state["since"] = since
    COUNTER_FILE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state


def _canned():
    if CANNED_FILE.exists():
        return json.loads(CANNED_FILE.read_text(encoding="utf-8"))
    return {}


def mode():
    """Which path is answering. Shown on the page at all times."""
    config = client.Config()
    if not config.api_key:
        return "canned"
    return "nim" if config.path == "nim" else "api-catalog"


def api_state():
    config = client.Config()
    state = _load_counter()
    state.pop("recent", None)
    state["resets"] = len(state.get("resets", []))
    return dict(state, mode=mode(), model=config.model,
                path=config.path, examples=sorted(examples.EXAMPLES))


def api_evaluate(payload):
    request = payload.get("request") or examples.load(
        payload.get("example", "incomplete-laws"))
    try:
        return {"ok": True, "receipt": engine.evaluate(request)}
    except schema.InvalidInput as exc:
        return {"ok": False, **exc.as_dict()}


def api_explain(payload):
    request = payload.get("request") or examples.load(
        payload.get("example", "incomplete-laws"))
    try:
        receipt = engine.evaluate(request)
    except schema.InvalidInput as exc:
        return {"ok": False, **exc.as_dict()}

    preset = payload.get("example")
    current = mode()
    if current == "canned":
        stored = _canned().get(preset)
        if stored and stored["receipt_sha"] == receipt["receipt_sha"]:
            # A recorded answer still names what produced it. Serving prose with
            # an empty provenance line would be the one thing worse than not
            # serving it: an explanation whose origin nobody can state.
            provenance = json.loads(json.dumps(stored["provenance"]))
            provenance["requested"] = dict(provenance.get("requested") or {},
                                           path="canned")
            provenance["recorded"] = True
            return {"ok": True, "receipt": receipt, "mode": "canned",
                    **dict(stored, provenance=provenance)}
        return {"ok": True, "receipt": receipt, "mode": "canned",
                "source": "template", "attempts": [],
                "explanation": render.render(receipt),
                "provenance": {"requested": {"path": "none"}, "returned": None}}

    result = explain.explain(receipt)
    return {"ok": True, "receipt": receipt, "mode": current, **result}


def api_attacks():
    """Cases grouped by the column that stops them. The grouping is the lesson."""
    grouped = defaultdict(list)
    for case in cases.ALL_CASES:
        grouped[case["expected"]].append(
            {"id": case["id"], "title": case["title"], "surface": case["surface"]})
    return {"groups": [{"column": column, "cases": grouped[column]}
                       for column in ("structure", "schema", "post-validator")]}


def api_attack(payload):
    case = next((c for c in cases.ALL_CASES if c["id"] == payload.get("id")), None)
    if case is None:
        return {"ok": False, "error": "UNKNOWN_CASE"}
    baseline = engine.evaluate(examples.load(case["example"]))
    if case["surface"] == "input":
        outcome = runner.run_input_case(case)
    else:
        outcome = runner.run_model_case(case, post_validation=True)
    counter = _bump_counter(case["id"]) if outcome["blocked"] else _load_counter()
    return {"ok": True, "id": case["id"], "title": case["title"],
            "surface": case["surface"], "column": outcome["observed"],
            "blocked": outcome["blocked"], "evidence": outcome["evidence"],
            "silently_released": outcome["silently_released"],
            "receipt_sha_before": baseline["receipt_sha"],
            "receipt_sha_after": outcome.get("receipt_sha", baseline["receipt_sha"]),
            "counter": counter}


def api_freetext(payload):
    """An open field, answered structurally. No model is called, ever."""
    text = str(payload.get("text", ""))[:4000]
    baseline = engine.evaluate(examples.load("incomplete-laws"))
    request = examples.load("incomplete-laws")
    request["description"] = text
    try:
        receipt = engine.evaluate(request)
    except schema.InvalidInput as exc:
        counter = _bump_counter("free-text/schema")
        return {"ok": True, "blocked": True, "column": "schema",
                "evidence": sorted({e["code"] for e in exc.errors}),
                "counter": counter}

    moved = [name for name, entry in receipt["outputs"].items()
             if entry["status"] != baseline["outputs"][name]["status"]]
    leaked = text and text in canonical.dumps(receipt)
    blocked = not moved and not leaked
    counter = _bump_counter("free-text/structure") if blocked else _load_counter()
    return {"ok": True, "blocked": blocked, "column": "structure",
            "evidence": ["payload absent from receipt" if not leaked
                         else "PAYLOAD PRESENT IN RECEIPT",
                         "statuses identical to the clean run" if not moved
                         else "STATUSES MOVED"],
            "receipt_sha_before": baseline["receipt_sha"],
            "receipt_sha_after": receipt["receipt_sha"],
            "note": "free text is answered structurally; no model is called",
            "counter": counter}


def api_sabotage():
    if SABOTAGE_FILE.exists():
        return json.loads(SABOTAGE_FILE.read_text(encoding="utf-8"))
    return {"available": False}


def api_rejected():
    """A real refused answer, recorded. Shown labelled, never as if it were live."""
    stored = _canned().get("_rejected_example")
    if not stored:
        return {"available": False}
    return dict(stored, available=True,
                note="recorded example — a real answer refused against its receipt")


ROUTES_GET = {"/api/state": lambda: api_state(),
              "/api/rejected": lambda: api_rejected(),
              "/api/attacks": lambda: api_attacks(),
              "/api/sabotage": lambda: api_sabotage()}
ROUTES_POST = {"/api/evaluate": api_evaluate, "/api/explain": api_explain,
               "/api/attack": api_attack, "/api/freetext": api_freetext}


class Handler(BaseHTTPRequestHandler):
    server_version = "gate/0.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body, content_type="application/json", close=False):
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(payload)

    def _drain(self, length):
        """Read and discard a refused body so the client can read the refusal."""
        remaining = min(length, DRAIN_CAP)
        while remaining > 0:
            chunk = self.rfile.read(min(DRAIN_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        return length <= DRAIN_CAP

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = (ROOT / "index.html").read_bytes()
            return self._send(200, page, "text/html; charset=utf-8")
        handler = ROUTES_GET.get(self.path)
        if handler is None:
            return self._send(404, {"error": "NOT_FOUND"})
        if _rate_limited(self.client_address[0]):
            return self._send(429, {"error": "RATE_LIMITED"})
        return self._send(200, handler())

    def do_POST(self):
        handler = ROUTES_POST.get(self.path)
        if handler is None:
            return self._send(404, {"error": "NOT_FOUND"})
        if _rate_limited(self.client_address[0]):
            return self._send(429, {"error": "RATE_LIMITED"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            fully_drained = self._drain(length)
            return self._send(413, {"error": "BODY_TOO_LARGE",
                                    "limit_bytes": MAX_BODY},
                              close=not fully_drained)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "MALFORMED_JSON"})
        return self._send(200, handler(payload))


def free_port(host, start, attempts=20):
    """The first free port at or after `start`."""
    for candidate in range(start, start + attempts):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
                return candidate
            except OSError:
                continue
    raise SystemExit(f"no free port in {start}..{start + attempts - 1}")


def serve(host="127.0.0.1", port=None, auto=True):
    """Serve the page. Busy ports are reported, not silently worked around."""
    port = int(port or os.environ.get("GATE_PORT") or DEFAULT_PORT)
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE or not auto:
            raise
        moved = free_port(host, port + 1)
        print(f"port {port} is busy; using {moved} instead "
              f"(pin one with --port or GATE_PORT)")
        httpd = ThreadingHTTPServer((host, moved), Handler)
        port = moved
    print(f"gate ui on http://{host}:{port}  (mode: {mode()})")
    httpd.serve_forever()
