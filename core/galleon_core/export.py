"""Export the indexers of an existing Prowlarr into a Galleon preset — with every secret stripped.

    ./galleon export-indexers --url http://192.168.1.10:9696 --api-key <key>

Only non-default, non-sensitive settings are kept. Credentials of private trackers become
${GALLEON_IDX_...} placeholders that you fill in your own .env, never in the preset file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

from . import log
from .http import Http

SENSITIVE = re.compile(r"pass|key|cookie|token|user|email|secret|pid|uid|auth|captcha|hash|session|rss|2fa|otp", re.I)
SAFE_TYPES = {"checkbox", "select", "number", "textbox", "tagSelect"}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def export(url: str, api_key: str) -> tuple[dict, list[str]]:
    api = Http(f"{url.rstrip('/')}/api/v1", {"X-Api-Key": api_key}, "Prowlarr")
    indexers = api.get("/indexer")
    schema = {t["definitionName"]: t for t in api.get("/indexer/schema")}
    proxy_tags = {t for p in api.get("/indexerproxy") if p["implementation"] == "FlareSolverr" for t in p["tags"]}

    out, secrets = [], []
    for ix in sorted(indexers, key=lambda i: (i.get("priority", 25), i["name"].lower())):
        defaults = {f["name"]: f.get("value") for f in schema.get(ix["definitionName"], {}).get("fields", [])}
        entry = {"definition": ix["definitionName"]}
        if ix["name"] != schema.get(ix["definitionName"], {}).get("name"):
            entry["name"] = ix["name"]
        if ix.get("priority", 25) != 25:
            entry["priority"] = ix["priority"]
        if proxy_tags & set(ix.get("tags", [])):
            entry["flaresolverr"] = True
        settings = {}
        for f in ix.get("fields", []):
            name, value = f["name"], f.get("value")
            if value in (None, "", []) or value == defaults.get(name):
                continue
            if SENSITIVE.search(name) or f.get("type") not in SAFE_TYPES or f.get("privacy") not in (None, "normal"):
                var = f"GALLEON_IDX_{_slug(ix['name'])}_{_slug(name)}"
                settings[name] = "${" + var + "}"
                secrets.append(var)
            else:
                settings[name] = value
        if settings:
            entry["settings"] = settings
        if ix.get("privacy") and ix["privacy"] != "public":
            entry["privacy"] = ix["privacy"]
        if not ix.get("enable", True):
            continue
        out.append(entry)

    doc = {
        "name": "custom",
        "description": f"Exported from {url} — secrets replaced by ${{...}} placeholders",
        "indexers": out,
    }
    return doc, secrets


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="galleon export-indexers")
    ap.add_argument("--url", required=True, help="existing Prowlarr URL, e.g. http://nas:9696")
    ap.add_argument("--api-key", default=os.environ.get("SOURCE_PROWLARR_API_KEY"), help="its API key")
    ap.add_argument("--out", default="/config-root/galleon/indexers.yml")
    args = ap.parse_args(argv)
    if not args.api_key:
        ap.error("--api-key is required (Prowlarr → Settings → General → API Key)")

    log.banner("Galleon · charting your indexers")
    doc, secrets = export(args.url, args.api_key)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("# Galleon indexer preset — safe to share: contains no credentials.\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)
    log.ok(f"{len(doc['indexers'])} indexers → {args.out}")
    if secrets:
        log.warn("private trackers need these lines in your .env (values from your tracker accounts):")
        for var in secrets:
            print(f"      {var}=")
    log.ok("enable it with GALLEON_INDEXER_PRESETS=custom (comma-separate to combine presets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
