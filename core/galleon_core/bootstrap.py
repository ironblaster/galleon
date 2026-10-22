"""The helmsman: waits for the fleet, then wires every service to every other one.

Idempotent by design: each step checks what exists and only adds or refreshes what's missing,
so `./galleon bootstrap` can be re-run at any time.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

from . import log, presets
from .jellyfin import Jellyfin
from .qbittorrent import QBittorrent
from .seerr import Seerr
from .servarr import MediaArr, Prowlarr
from .settings import Settings


class Voyage:
    def __init__(self, s: Settings):
        self.s = s
        self.failed: list[str] = []
        self.qbit = QBittorrent(f"http://{s.qbit_host}:8080")
        self.radarr = MediaArr("radarr", "http://radarr:7878", s.radarr_key)
        self.sonarr = MediaArr("sonarr", "http://sonarr:8989", s.sonarr_key)
        self.prowlarr = Prowlarr("http://prowlarr:9696", s.prowlarr_key)
        self.jellyfin = Jellyfin("http://jellyfin:8096")
        self.seerr = Seerr("http://seerr:5055")

    def step(self, title: str, fn) -> None:
        log.section(title)
        try:
            fn()
        except Exception as e:  # keep sailing: one broken service must not sink the rest
            log.fail(str(e))
            if os.environ.get("GALLEON_DEBUG"):
                traceback.print_exc()
            self.failed.append(title)

    # ── steps ────────────────────────────────────────────────────────────
    def muster(self):
        for svc in (self.qbit, self.radarr, self.sonarr, self.prowlarr, self.jellyfin, self.seerr):
            svc.wait()

    def download(self):
        self.qbit.login(self.s.admin_user, self.s.admin_password)
        self.qbit.configure()

    def media_arr(self, arr: MediaArr, root: str):
        def run():
            arr.ensure_login(self.s.admin_user, self.s.admin_password, self.s.allowed_hosts(arr.kind))
            arr.ensure_root_folder(root)
            arr.ensure_media_management()
            arr.ensure_qbittorrent(self.s.qbit_host, self.s.admin_user, self.s.admin_password)
            if self.s.language != "en":
                arr.ensure_language_format(self.s.lang[0])
        return run

    def indexers(self):
        p = self.prowlarr
        p.ensure_login(self.s.admin_user, self.s.admin_password, self.s.allowed_hosts("prowlarr"))
        tag = p.ensure_flaresolverr("http://flaresolverr:8191/")
        p.ensure_app("radarr", "http://radarr:7878", self.s.radarr_key)
        p.ensure_app("sonarr", "http://sonarr:8989", self.s.sonarr_key)
        entries = presets.load(self.s.indexer_presets, self.s.presets_dir, self.s.config_root)
        if not entries:
            log.skip("no indexer presets selected (GALLEON_INDEXER_PRESETS)")
        added = sum(p.add_indexer(e, tag) for e in entries)
        if entries:
            log.ok(f"{added}/{len(entries)} indexers aboard")
        p.sync_apps()

    def watch(self):
        _, culture, country, (movies, shows) = self.s.lang
        jf = self.jellyfin
        jf.ensure_wizard(self.s.admin_user, self.s.admin_password, culture, country, self.s.language)
        jf.login(self.s.admin_user, self.s.admin_password)
        jf.ensure_library(movies, "movies", "/data/media/movies", self.s.language, country)
        jf.ensure_library(shows, "tvshows", "/data/media/tv", self.s.language, country)

    def requests(self):
        sr, s = self.seerr, self.s
        sr.login(s.admin_user, s.admin_password, s.admin_email)
        sr.ensure_libraries()
        sr.ensure_arr("radarr", 7878, s.radarr_key, "/data/media/movies", s.quality_profile,
                      f"http://{s.host}:{s.port('radarr', 7878)}")
        sr.ensure_arr("sonarr", 8989, s.sonarr_key, "/data/media/tv", s.quality_profile,
                      f"http://{s.host}:{s.port('sonarr', 8989)}")
        sr.ensure_locale(s.language, f"http://{s.host}:{s.port('seerr', 5055)}")
        sr.finish()

    # ── run ──────────────────────────────────────────────────────────────
    def sail(self) -> int:
        log.banner("Galleon · assembling the fleet")
        started = time.monotonic()
        self.step("Mustering the crew", self.muster)
        if self.failed:
            log.fail("some services never came up: check `./galleon logs`")
            return 1
        self.step("qBittorrent · downloads", self.download)
        self.step("Radarr · movies", self.media_arr(self.radarr, "/data/media/movies"))
        self.step("Sonarr · series", self.media_arr(self.sonarr, "/data/media/tv"))
        self.step("Prowlarr · indexers", self.indexers)
        self.step("Jellyfin · streaming", self.watch)
        self.step("Seerr · requests", self.requests)
        self.report(time.monotonic() - started)
        return 1 if self.failed else 0

    def report(self, elapsed: float) -> None:
        s = self.s
        urls = {
            "Seerr (start here)": ("seerr", 5055), "Jellyfin": ("jellyfin", 8096), "Radarr": ("radarr", 7878),
            "Sonarr": ("sonarr", 8989), "Prowlarr": ("prowlarr", 9696), "qBittorrent": ("qbittorrent", 8080),
        }
        state = {"completed_at": int(time.time()), "failed": self.failed,
                 "urls": {k: f"http://{s.host}:{s.port(*v)}" for k, v in urls.items()}}
        with open(os.path.join(s.config_root, "galleon", "state.json"), "w") as f:
            json.dump(state, f, indent=2)

        if self.failed:
            log.banner(f"Fleet assembled with {len(self.failed)} issue(s): {', '.join(self.failed)}")
            log.warn("re-run `./galleon bootstrap` once fixed: completed steps are skipped")
        else:
            log.banner(f"All hands on deck in {elapsed:.0f}s")
        print()
        for label, url in state["urls"].items():
            print(f"    {label:<20} {url}")
        print(f"\n    login: {s.admin_user} / (GALLEON_ADMIN_PASSWORD in .env)\n", flush=True)


def run(s: Settings) -> int:
    problems = s.validate()
    if problems:
        for p in problems:
            log.fail(p)
        return 2
    return Voyage(s).sail()


if __name__ == "__main__":
    sys.exit(run(Settings()))
