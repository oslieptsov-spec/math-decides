"""python -m web [--host H] [--port P]"""
import sys

from .server import serve


def main(argv):
    host = next((argv[i + 1] for i, a in enumerate(argv) if a == "--host"), "127.0.0.1")
    port = int(next((argv[i + 1] for i, a in enumerate(argv) if a == "--port"), 8080))
    try:
        serve(host, port)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
