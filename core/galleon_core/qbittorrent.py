"""qBittorrent WebUI API v2."""

from __future__ import annotations

import json

from . import log
from .http import ApiError, Http

CATEGORIES = {"radarr": "/data/torrents/movies", "sonarr": "/data/torrents/tv"}


class QBittorrent:
    def __init__(self, url: str):
        self.api = Http(f"{url}/api/v2", {"Referer": url}, "qBittorrent")

    def wait(self) -> None:
        # /app/version answers 403 until login: that still means "up"
        self.api.wait("/app/version", accept=(403,))
        log.ok("qBittorrent is up")

    def login(self, user: str, password: str) -> None:
        try:
            r = self.api.post("/auth/login", form={"username": user, "password": password}, body=None)
        except ApiError as e:
            r = f"HTTP {e.status}"
        if r not in (None, "Ok."):  # v5 answers 204 No Content, v4 answers "Ok."
            raise ApiError(
                "qBittorrent rejected the Galleon credentials. If you created qBittorrent.conf yourself, "
                "set its WebUI password to GALLEON_ADMIN_PASSWORD (or delete the file and re-run)."
            )

    def configure(self) -> None:
        prefs = {
            "save_path": "/data/torrents",
            "temp_path_enabled": False,
            "auto_tmm_enabled": True,
            "torrent_changed_tmm_enabled": True,
            "save_path_changed_tmm_enabled": True,
            "category_changed_tmm_enabled": True,
            "web_ui_host_header_validation_enabled": False,
        }
        self.api.post("/app/setPreferences", form={"json": json.dumps(prefs)})
        log.ok("qBittorrent: automatic torrent management on /data/torrents")
        existing = self.api.get("/torrents/categories") or {}
        for name, path in CATEGORIES.items():
            endpoint = "/torrents/editCategory" if name in existing else "/torrents/createCategory"
            self.api.post(endpoint, form={"category": name, "savePath": path})
        log.ok(f"qBittorrent: categories {', '.join(CATEGORIES)}")
