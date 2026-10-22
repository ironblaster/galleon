"""Jellyfin: run the first-start wizard headlessly and create the libraries."""

from __future__ import annotations

from . import log
from .http import ApiError, Http

CLIENT = 'MediaBrowser Client="Galleon", Device="Galleon", DeviceId="galleon-bootstrap", Version="1.0.0"'


class Jellyfin:
    def __init__(self, url: str):
        self.url = url
        self.api = Http(url, {"Authorization": CLIENT}, "Jellyfin")

    def wait(self) -> None:
        self.api.wait("/System/Info/Public")
        log.ok("Jellyfin is up")

    def ensure_wizard(self, user: str, password: str, culture: str, country: str, language: str) -> None:
        if self.api.get("/System/Info/Public").get("StartupWizardCompleted"):
            log.skip("Jellyfin: setup wizard already completed")
            return
        self.api.post("/Startup/Configuration", {
            "UICulture": culture, "MetadataCountryCode": country, "PreferredMetadataLanguage": language,
        })
        self.api.get("/Startup/User")  # materialises the initial user
        self.api.post("/Startup/User", {"Name": user, "Password": password})
        self.api.post("/Startup/RemoteAccess", {"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
        self.api.post("/Startup/Complete")
        log.ok(f"Jellyfin: wizard done, admin '{user}'")

    def login(self, user: str, password: str) -> None:
        try:
            r = self.api.post("/Users/AuthenticateByName", {"Username": user, "Pw": password})
        except ApiError as e:
            raise ApiError("Jellyfin login failed: the admin password differs from GALLEON_ADMIN_PASSWORD") from e
        self.api.headers["Authorization"] = f'{CLIENT}, Token="{r["AccessToken"]}"'

    def ensure_library(self, name: str, collection: str, path: str, language: str, country: str) -> None:
        for lib in self.api.get("/Library/VirtualFolders"):
            if path in [loc.rstrip("/") for loc in lib.get("Locations", [])]:
                log.skip(f"Jellyfin: library '{lib['Name']}' already watches {path}")
                return
        self.api.post(
            "/Library/VirtualFolders",
            {"LibraryOptions": {
                "PreferredMetadataLanguage": language,
                "MetadataCountryCode": country,
                "EnableRealtimeMonitor": True,
                "PathInfos": [{"Path": path}],
            }},
            params={"name": name, "collectionType": collection, "refreshLibrary": "true"},
        )
        log.ok(f"Jellyfin: library '{name}' → {path}")
