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
import json
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

COUNTING_SINCE = "2026-08-25"
RATE_LIMIT = (60, 60.0)          # requests per window, window in seconds
MAX_BODY = 64 * 1024

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
    return {"attacks_blocked": 0, "since": COUNTING_SINCE}


def _bump_counter():
    state = _load_counter()
    state["attacks_blocked"] += 1
    state.setdefault("since", COUNTING_SINCE)
    COUNTER_FILE.write_text(json.dumps(state), encoding="utf-8")
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
    return dict(_load_counter(), mode=mode(), model=config.model,
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
            return {"ok": True, "receipt": receipt, "mode": "canned", **stored}
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
    counter = _bump_counter() if outcome["blocked"] else _load_counter()
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
        counter = _bump_counter()
        return {"ok": True, "blocked": True, "column": "schema",
                "evidence": sorted({e["code"] for e in exc.errors}),
                "counter": counter}

    moved = [name for name, entry in receipt["outputs"].items()
             if entry["status"] != baseline["outputs"][name]["status"]]
    leaked = text and text in canonical.dumps(receipt)
    blocked = not moved and not leaked
    counter = _bump_counter() if blocked else _load_counter()
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


ROUTES_GET = {"/api/state": lambda: api_state(),
              "/api/attacks": lambda: api_attacks(),
              "/api/sabotage": lambda: api_sabotage()}
ROUTES_POST = {"/api/evaluate": api_evaluate, "/api/explain": api_explain,
               "/api/attack": api_attack, "/api/freetext": api_freetext}


class Handler(BaseHTTPRequestHandler):
    server_version = "gate/0.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

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
            return self._send(413, {"error": "BODY_TOO_LARGE"})
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "MALFORMED_JSON"})
        return self._send(200, handler(payload))


def serve(host="127.0.0.1", port=8080):
    print(f"gate ui on http://{host}:{port}  (mode: {mode()})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
