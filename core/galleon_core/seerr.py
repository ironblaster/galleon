"""Seerr: sign in through Jellyfin, enable libraries, connect Radarr & Sonarr."""

from __future__ import annotations

from . import log
from .http import ApiError, Http

JELLYFIN = 2  # Seerr MediaServerType


class Seerr:
    def __init__(self, url: str):
        self.api = Http(f"{url}/api/v1", name="Seerr")

    def wait(self) -> None:
        self.api.wait("/status")
        log.ok("Seerr is up")

    def login(self, user: str, password: str, email: str) -> bool:
        """Returns True when this call performed first-time setup."""
        public = self.api.get("/settings/public")
        creds = {"username": user, "password": password}
        if public.get("mediaServerType") != JELLYFIN or not public.get("initialized"):
            try:
                self.api.post("/auth/jellyfin", {
                    **creds, "hostname": "jellyfin", "port": 8096, "useSsl": False, "urlBase": "",
                    "email": email, "serverType": JELLYFIN,
                })
                log.ok(f"Seerr: linked to Jellyfin, admin '{user}'")
                return not public.get("initialized")
            except ApiError as e:
                if e.status not in (400, 403, 500):
                    raise
        self.api.post("/auth/jellyfin", creds)
        return False

    def ensure_libraries(self) -> None:
        libs = self.api.post("/settings/jellyfin/library/sync") or []
        for lib in libs:
            if not lib.get("enabled"):
                self.api.put(f"/settings/jellyfin/library/{lib['id']}", {"enabled": True})
        log.ok(f"Seerr: {len(libs)} Jellyfin libraries enabled")

    def _pick_profile(self, profiles: list[dict], preferred: str) -> dict:
        for p in profiles:
            if p["name"].lower() == preferred.lower():
                return p
        return next((p for p in profiles if "1080" in p["name"]), profiles[0])

    def ensure_arr(self, kind: str, port: int, api_key: str, root: str, preferred_profile: str, external: str) -> None:
        if any(s.get("hostname") == kind for s in self.api.get(f"/settings/{kind}")):
            log.skip(f"Seerr: {kind} already connected")
            return
        conn = {"hostname": kind, "port": port, "apiKey": api_key, "useSsl": False, "baseUrl": ""}
        info = self.api.post(f"/settings/{kind}/test", conn)
        profile = self._pick_profile(info["profiles"], preferred_profile)
        body = {
            **conn,
            "name": kind.capitalize(),
            "activeProfileId": profile["id"],
            "activeProfileName": profile["name"],
            "activeDirectory": root,
            "is4k": False,
            "isDefault": True,
            "externalUrl": external,
            "syncEnabled": True,
            "preventSearch": False,
            "tags": [],
            "tagRequests": False,
        }
        if kind == "radarr":
            body["minimumAvailability"] = "released"
        else:
            body.update(
                activeAnimeProfileId=profile["id"], activeAnimeProfileName=profile["name"],
                activeAnimeDirectory=root, seriesType="standard", animeSeriesType="anime",
                enableSeasonFolders=True, animeTags=[],
            )
        self.api.post(f"/settings/{kind}", body)
        log.ok(f"Seerr: {kind} connected (profile '{profile['name']}')")

    def ensure_locale(self, locale: str, app_url: str) -> None:
        main = self.api.get("/settings/main")
        if main.get("locale") != locale or not main.get("applicationUrl"):
            self.api.post("/settings/main", {"locale": locale, "applicationUrl": main.get("applicationUrl") or app_url})
        log.ok(f"Seerr: locale '{locale}'")

    def finish(self) -> None:
        if not self.api.get("/settings/public").get("initialized"):
            self.api.post("/settings/initialize")
        log.ok("Seerr: setup complete")
