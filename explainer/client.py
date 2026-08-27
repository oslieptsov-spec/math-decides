"""Transport to an OpenAI-compatible Nemotron endpoint. No dependencies.

The same client speaks to the hosted API catalog and to a self-hosted NIM,
because the two expose the same interface. Which one answered is recorded in
the provenance rather than assumed, since the post-validator has to be equally
strict on both and the two do not decode identically.

Reasoning is switched off deliberately. A reasoning trace is model prose that
no schema covers, and prose the validator does not see is prose that must not
be shown. Switching it off removes the channel instead of policing it.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
DEFAULT_MAX_TOKENS = 900
DEFAULT_TIMEOUT = 60


class TransportError(Exception):
    """The endpoint did not return a usable answer."""


def load_env(root=None):
    """Read .env without a dependency. Environment variables win."""
    path = Path(root or Path(__file__).resolve().parent.parent) / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


class Config:
    def __init__(self, model=None, base_url=None, temperature=0.0,
                 max_tokens=DEFAULT_MAX_TOKENS, timeout=DEFAULT_TIMEOUT, path=None):
        load_env()
        self.api_key = os.environ.get("NVIDIA_API_KEY")
        self.base_url = base_url or os.environ.get("NVIDIA_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.environ.get("NVIDIA_MODEL", DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.path = path or ("nim" if "integrate.api.nvidia.com" not in self.base_url
                             else "api-catalog")
        # Where the NIM runs is not discoverable from its API: a self-hosted
        # endpoint on a rented H100 and one on GKE answer identically. So it is
        # declared by whoever started the process and labelled as declared, not
        # reported as if it had been measured.
        self.deployment = os.environ.get("NIM_DEPLOYMENT")

    def redacted(self):
        return {"model": self.model, "base_url": self.base_url, "path": self.path,
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "key_present": bool(self.api_key),
                "deployment_declared": self.deployment}


THINKING_OFF = "detailed thinking off"


def without_thinking(messages):
    """Reasoning off, by both of the switches that exist.

    `chat_template_kwargs` is read by the templates that know it. The
    llama-nemotron family ignores it and takes the instruction as the opening
    line of the system message instead. Asked without that line, the model
    here spent its entire token budget reasoning and returned an answer of
    zero characters — a refusal produced by a switch that was set and not
    read. Both are set, because the request cannot see which template will
    read it, and a directive the template does not use costs a few tokens.
    """
    if not messages or messages[0].get("role") != "system":
        return messages
    head = messages[0]
    if head.get("content", "").startswith(THINKING_OFF):
        return messages
    return ([{"role": "system",
              "content": f"{THINKING_OFF}\n\n{head.get('content', '')}"}]
            + list(messages[1:]))


def build_body(config, messages, schema, mode="json_schema"):
    """The request, with structure imposed as strongly as the stack allows.

    Three rungs, strongest first. `json_schema` is the OpenAI-standard form and
    the one the boundary would like: the decoder refuses to emit anything else.
    An older NIM rejects it at the door but takes the same schema through its
    own `nvext` extension, which is the same guarantee under a different name.
    `json_object` is the last rung and the weakest by a wide margin — it
    constrains the answer to be JSON and nothing more.

    The gap between the last two is not cosmetic. Asked for bare `json_object`,
    the model here emitted nine hundred tokens of whitespace and one character
    of answer: a grammar that permits unlimited spacing, and a small model that
    took the permission. The same request under `nvext` returned the object in
    four hundred.

    Nothing about the guarantee changes on any rung. The schema was never what
    made the answer safe; the comparison against the receipt is.
    """
    body = {
        "model": config.model,
        "messages": without_thinking(messages),
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "chat_template_kwargs": {"thinking": False},
    }
    # Structure is imposed by the decoder where the decoder can impose it.
    if mode == "json_schema":
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "explanation", "strict": True,
                            "schema": schema}}
    elif mode == "nvext":
        body["nvext"] = {"guided_json": schema}
    else:
        body["response_format"] = {"type": "json_object"}
    return body


def post(config, body):
    if not config.api_key:
        raise TransportError("NVIDIA_API_KEY is not set")
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {config.api_key}",
                 "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise TransportError(f"HTTP {exc.code}: {exc.read()[:200]!r}") from exc
    except Exception as exc:
        raise TransportError(f"{type(exc).__name__}: {exc}") from exc


_BUILD_CACHE = {}
_SCHEMA_MODE_CACHE = {}


def schema_mode(config, probe):
    """Whether this endpoint accepts a strict schema, asked once and cached.

    `probe` sends one tiny request per rung and raises where the stack refuses
    it. The strongest accepted rung wins; if a stack turns all three down, the
    weakest is used and the real call reports whatever it reports rather than
    this probe guessing.
    """
    if config.base_url in _SCHEMA_MODE_CACHE:
        return _SCHEMA_MODE_CACHE[config.base_url]
    mode = "json_object"
    for candidate in ("json_schema", "nvext", "json_object"):
        try:
            probe(candidate)
        except TransportError:
            continue
        mode = candidate
        break
    _SCHEMA_MODE_CACHE[config.base_url] = mode
    return mode


def probe_build(config):
    """A build identifier, where the serving stack publishes one.

    The chat completion carries no `system_fingerprint` on either path, which
    was read as "no build is available anywhere". A self-hosted NIM does
    publish one — on its own endpoint, not in the OpenAI-shaped response — so
    the honest answer differs by path rather than being absent from both.
    Probed once per endpoint and cached; a stack without the route simply has
    no build.
    """
    if config.base_url in _BUILD_CACHE:
        return _BUILD_CACHE[config.base_url]
    build = None
    try:
        request = urllib.request.Request(f"{config.base_url}/version",
                                         headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read())
        release, api = payload.get("release"), payload.get("api")
        if release:
            build = f"nim {release}" + (f" (api {api})" if api else "")
    except Exception:
        build = None
    _BUILD_CACHE[config.base_url] = build
    return build


def extract(response):
    """The answer text and the provenance the endpoint actually supplies.

    There is less provenance here than one would like: the endpoint returns a
    model name and a response id but no build identifier, so a silent update on
    the provider side is detectable by behaviour and not by version. That limit
    is recorded rather than papered over.
    """
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TransportError(f"unexpected response shape: {str(response)[:200]}") from exc
    return (message.get("content") or "").strip(), {
        "model": response.get("model"),
        "build": None,
        "response_id": response.get("id"),
        "system_fingerprint": response.get("system_fingerprint"),
        "usage": response.get("usage"),
        "reasoning_returned": bool(message.get("reasoning_content")),
    }
