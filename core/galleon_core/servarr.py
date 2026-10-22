"""Radarr, Sonarr and Prowlarr share one API design (the Servarr base); this module drives all three."""

from __future__ import annotations

import copy

from . import log
from .http import ApiError, Http


def fill(template: dict, fields: dict) -> dict:
    """Copy a provider schema template and set its `fields[]` values by name."""
    item = copy.deepcopy(template)
    known = {f["name"] for f in item.get("fields", [])}
    for f in item.get("fields", []):
        if f["name"] in fields:
            f["value"] = fields[f["name"]]
    missing = set(fields) - known
    if missing:
        log.warn(f"{item.get('implementation')}: ignoring unknown fields {sorted(missing)}")
    return item


class Servarr:
    def __init__(self, name: str, url: str, api_key: str, version: str = "v3"):
        self.name = name
        self.url = url
        self.api_key = api_key
        self.api = Http(f"{url}/api/{version}", {"X-Api-Key": api_key}, name)

    def wait(self) -> None:
        self.api.wait("/system/status")
        log.ok(f"{self.name} is up")

    # ── security ──────────────────────────────────────────────────────────
    def ensure_login(self, user: str, password: str, allowed_hosts: str) -> None:
        host = self.api.get("/config/host")
        if (host.get("username") == user and host.get("authenticationMethod") == "forms"
                and host.get("allowedHosts") == allowed_hosts):
            log.skip(f"{self.name}: login already set")
            return
        host.update(
            authenticationMethod="forms",
            authenticationRequired="disabledForLocalAddresses",
            allowedHosts=allowed_hosts,
            username=user,
            password=password,
            passwordConfirmation=password,
            analyticsEnabled=False,
        )
        self.api.put(f"/config/host/{host['id']}", host)
        log.ok(f"{self.name}: login '{user}' (no password needed on your LAN)")

    # ── generic providers (download clients, apps, proxies, indexers) ─────
    def ensure_provider(self, resource: str, implementation: str, name: str, fields: dict, **extra) -> dict:
        existing = [p for p in self.api.get(f"/{resource}") if p.get("implementation") == implementation]
        match = next((p for p in existing if p.get("name") == name), existing[0] if existing else None)
        for dup in existing:  # self-heal duplicates left by an interrupted run
            if match and dup["id"] != match["id"] and dup.get("name") == match.get("name"):
                self.api.delete(f"/{resource}/{dup['id']}")
                log.warn(f"{self.name}: removed duplicate {resource} '{dup['name']}' (id {dup['id']})")
        if match:
            item = fill(match, fields)
            item.update(extra)
            self.api.put(f"/{resource}/{match['id']}", item, params={"forceSave": "true"})
            log.skip(f"{self.name}: {resource} '{match['name']}' refreshed")
            return match
        schema = next(t for t in self.api.get(f"/{resource}/schema") if t.get("implementation") == implementation)
        item = fill(schema, fields)
        item.update(name=name, **extra)
        if "enable" in schema:
            item.setdefault("enable", True)
        created = self.api.post(f"/{resource}", item, params={"forceSave": "true"})
        log.ok(f"{self.name}: {resource} '{name}' added")
        return created

    def ensure_tag(self, label: str) -> int:
        for t in self.api.get("/tag"):
            if t["label"].lower() == label.lower():
                return t["id"]
        return self.api.post("/tag", {"label": label})["id"]


class MediaArr(Servarr):
    """Radarr / Sonarr."""

    def __init__(self, kind: str, url: str, api_key: str):
        super().__init__(kind.capitalize(), url, api_key)
        self.kind = kind

    def ensure_root_folder(self, path: str) -> None:
        if any(r["path"].rstrip("/") == path for r in self.api.get("/rootfolder")):
            log.skip(f"{self.name}: root folder {path} exists")
            return
        self.api.post("/rootfolder", {"path": path})
        log.ok(f"{self.name}: root folder {path}")

    def ensure_media_management(self) -> None:
        mm = self.api.get("/config/mediamanagement")
        mm.update(copyUsingHardlinks=True, importExtraFiles=True, extraFileExtensions="srt,sub,idx,ass")
        self.api.put(f"/config/mediamanagement/{mm['id']}", mm)
        naming = self.api.get("/config/naming")
        naming["renameMovies" if self.kind == "radarr" else "renameEpisodes"] = True
        self.api.put(f"/config/naming/{naming['id']}", naming)
        log.ok(f"{self.name}: hardlinks on, clean renaming on")

    def ensure_qbittorrent(self, host: str, user: str, password: str) -> None:
        category = {"radarr": "movieCategory", "sonarr": "tvCategory"}[self.kind]
        self.ensure_provider(
            "downloadclient", "QBittorrent", "qBittorrent",
            {"host": host, "port": 8080, "useSsl": False, "username": user, "password": password, category: self.kind},
            enable=True, priority=1,
        )

    def ensure_language_format(self, language: str, score: int = 100) -> None:
        """Prefer releases with the chosen audio language, without rejecting others."""
        lang = next((x for x in self.api.get("/language") if x["name"].lower() == language.lower()), None)
        if not lang:
            log.warn(f"{self.name}: language '{language}' not found, skipping preference")
            return
        cf_name = f"Audio: {language}"
        cf = next((c for c in self.api.get("/customformat") if c["name"] == cf_name), None)
        if not cf:
            spec = next(t for t in self.api.get("/customformat/schema") if t["implementation"] == "LanguageSpecification")
            spec = fill(spec, {"value": lang["id"]})
            spec.update(name=language, negate=False, required=True)
            cf = self.api.post("/customformat", {
                "name": cf_name, "includeCustomFormatWhenRenaming": False, "specifications": [spec],
            })
            log.ok(f"{self.name}: custom format '{cf_name}'")
        for profile in self.api.get("/qualityprofile"):
            items = profile.setdefault("formatItems", [])
            item = next((i for i in items if i["format"] == cf["id"]), None)
            if item and item["score"] == score:
                continue
            if item:
                item["score"] = score
            else:
                items.append({"format": cf["id"], "name": cf_name, "score": score})
            self.api.put(f"/qualityprofile/{profile['id']}", profile)
        log.ok(f"{self.name}: every quality profile prefers {language} audio (+{score})")

    def profiles(self) -> list[dict]:
        return self.api.get("/qualityprofile")


class Prowlarr(Servarr):
    def __init__(self, url: str, api_key: str):
        super().__init__("Prowlarr", url, api_key, "v1")
        self._schema: list[dict] | None = None

    def ensure_flaresolverr(self, url: str) -> int:
        tag = self.ensure_tag("flaresolverr")
        self.ensure_provider("indexerproxy", "FlareSolverr", "FlareSolverr", {"host": url, "requestTimeout": 60}, tags=[tag])
        return tag

    def ensure_app(self, kind: str, url: str, api_key: str) -> None:
        self.ensure_provider(
            "applications", kind.capitalize(), kind.capitalize(),
            {"prowlarrUrl": "http://prowlarr:9696", "baseUrl": url, "apiKey": api_key},
            syncLevel="fullSync",
        )

    def add_indexer(self, entry: dict, flaresolverr_tag: int) -> bool:
        """entry: {definition, name?, priority?, flaresolverr?, settings?} from a preset file."""
        if self._schema is None:
            self._schema = self.api.get("/indexer/schema")
        definition = entry["definition"]
        tpl = next((t for t in self._schema if t.get("definitionName", "").lower() == definition.lower()), None)
        if not tpl:
            log.warn(f"indexer '{definition}': no such Prowlarr definition (renamed or removed?)")
            return False
        name = entry.get("name") or tpl["name"]
        if any(i["name"] == name for i in self.api.get("/indexer")):
            log.skip(f"indexer '{name}' already aboard")
            return True
        item = fill(tpl, entry.get("settings") or {})
        profiles = self.api.get("/appprofile")
        item.update(
            name=name,
            enable=True,
            priority=int(entry.get("priority", 25)),
            appProfileId=profiles[0]["id"],
            tags=[flaresolverr_tag] if entry.get("flaresolverr") else [],
        )
        try:
            # forceSave keeps the indexer even if its test fails (site down, ISP block, Cloudflare)
            self.api.post("/indexer", item, params={"forceSave": "true"}, timeout=180)
        except ApiError as e:
            log.warn(f"indexer '{name}': {e}")
            return False
        except OSError as e:  # includes TimeoutError: Prowlarr may still save it, the next run will see it
            log.warn(f"indexer '{name}': no answer from Prowlarr ({e}), will re-check next run")
            return False
        log.ok(f"indexer '{name}'" + (" via FlareSolverr" if entry.get("flaresolverr") else ""))
        return True

    def sync_apps(self) -> None:
        self.api.post("/command", {"name": "ApplicationIndexerSync"})
        log.ok("Prowlarr: pushing indexers to Radarr & Sonarr")
