"""python -m web [--host H] [--port P] [--strict]

Defaults to 127.0.0.1:7690. A busy port moves to the next free one unless
--strict is given, in which case the failure is reported as it happens.
"""
import sys

from .server import DEFAULT_PORT, serve


def main(argv):
    host = next((argv[i + 1] for i, a in enumerate(argv) if a == "--host"), "127.0.0.1")
    port = next((argv[i + 1] for i, a in enumerate(argv) if a == "--port"), None)
    try:
        serve(host, port, auto="--strict" not in argv)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
