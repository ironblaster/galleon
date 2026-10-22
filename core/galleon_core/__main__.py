"""Entry point: `python -m galleon_core <seed|bootstrap|export|version>`."""

import sys

from . import __version__, bootstrap, export, seed
from .settings import Settings


def main() -> int:
    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("bootstrap", [])
    if cmd == "seed":
        return seed.run(Settings())
    if cmd == "bootstrap":
        return bootstrap.run(Settings())
    if cmd == "export":
        return export.main(rest)
    if cmd == "version":
        print(__version__)
        return 0
    print(f"unknown command '{cmd}' (seed | bootstrap | export | version)", file=sys.stderr)
    return 64


sys.exit(main())
