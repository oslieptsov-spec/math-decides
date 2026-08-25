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

    def redacted(self):
        return {"model": self.model, "base_url": self.base_url, "path": self.path,
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "key_present": bool(self.api_key)}


def build_body(config, messages, schema):
    return {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        # Structure is imposed by the decoder, not requested in the prompt.
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "explanation", "strict": True,
                                            "schema": schema}},
        "chat_template_kwargs": {"thinking": False},
    }


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
        "response_id": response.get("id"),
        "system_fingerprint": response.get("system_fingerprint"),
        "usage": response.get("usage"),
        "reasoning_returned": bool(message.get("reasoning_content")),
    }
