"""Console output with a nautical accent."""

import sys

_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def banner(text: str) -> None:
    print(_c("1;36", f"\n⛵  {text}"), flush=True)


def section(text: str) -> None:
    print(_c("1;34", f"\n━━ {text} "), flush=True)


def ok(text: str) -> None:
    print(f"  {_c('32', '✔')} {text}", flush=True)


def skip(text: str) -> None:
    print(f"  {_c('90', '•')} {_c('90', text)}", flush=True)


def warn(text: str) -> None:
    print(f"  {_c('33', '⚠')} {text}", flush=True)


def fail(text: str) -> None:
    print(f"  {_c('31', '✖')} {text}", flush=True)
