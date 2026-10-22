"""Runtime settings, read from the environment (.env via compose)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

LANGUAGES = {
    # iso: (arr language name, jellyfin culture, metadata country, library names)
    "en": ("English", "en-US", "US", ("Movies", "Shows")),
    "it": ("Italian", "it", "IT", ("Film", "Serie TV")),
    "de": ("German", "de", "DE", ("Filme", "Serien")),
    "fr": ("French", "fr", "FR", ("Films", "Séries")),
    "es": ("Spanish", "es", "ES", ("Películas", "Series")),
    "pt": ("Portuguese", "pt-BR", "BR", ("Filmes", "Séries")),
    "nl": ("Dutch", "nl", "NL", ("Films", "Series")),
    "pl": ("Polish", "pl", "PL", ("Filmy", "Seriale")),
}

_KEY = re.compile(r"^[a-f0-9]{32}$")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    puid: int = field(default_factory=lambda: int(_env("PUID", "1000")))
    pgid: int = field(default_factory=lambda: int(_env("PGID", "1000")))
    admin_user: str = field(default_factory=lambda: _env("GALLEON_ADMIN_USER", "admin"))
    admin_password: str = field(default_factory=lambda: _env("GALLEON_ADMIN_PASSWORD"))
    admin_email: str = field(default_factory=lambda: _env("GALLEON_ADMIN_EMAIL", "admin@galleon.local"))
    radarr_key: str = field(default_factory=lambda: _env("RADARR_API_KEY"))
    sonarr_key: str = field(default_factory=lambda: _env("SONARR_API_KEY"))
    prowlarr_key: str = field(default_factory=lambda: _env("PROWLARR_API_KEY"))
    language: str = field(default_factory=lambda: _env("GALLEON_LANGUAGE", "en").lower())
    indexer_presets: list[str] = field(
        default_factory=lambda: [p.strip() for p in _env("GALLEON_INDEXER_PRESETS").split(",") if p.strip()]
    )
    quality_profile: str = field(default_factory=lambda: _env("GALLEON_QUALITY_PROFILE", "HD-1080p"))
    qbit_host: str = field(default_factory=lambda: _env("GALLEON_QBIT_HOST", "qbittorrent"))
    host: str = field(default_factory=lambda: _env("GALLEON_HOST", "localhost"))
    extra_hosts: list[str] = field(
        default_factory=lambda: [h.strip() for h in _env("GALLEON_ALLOWED_HOSTS").split(",") if h.strip()]
    )

    config_root: str = "/config-root"
    data_root: str = "/data"
    presets_dir: str = "/presets"

    @property
    def lang(self):
        return LANGUAGES.get(self.language, LANGUAGES["en"])

    def allowed_hosts(self, service: str) -> str:
        """Host names the *arr apps accept for password-less LAN access (DNS-rebinding guard)."""
        hosts = ["localhost", "127.0.0.1", service, self.host, *self.extra_hosts]
        return ",".join(dict.fromkeys(h for h in hosts if h))

    def port(self, service: str, default: int) -> int:
        return int(_env(f"GALLEON_PORT_{service.upper()}", str(default)))

    def validate(self) -> list[str]:
        problems = []
        for name, key in (("RADARR", self.radarr_key), ("SONARR", self.sonarr_key), ("PROWLARR", self.prowlarr_key)):
            if not _KEY.match(key):
                problems.append(f"{name}_API_KEY must be 32 lowercase hex chars")
        if len(self.admin_password) < 8:
            problems.append("GALLEON_ADMIN_PASSWORD must be at least 8 characters")
        if self.language not in LANGUAGES:
            problems.append(f"GALLEON_LANGUAGE '{self.language}' unsupported (use one of {', '.join(LANGUAGES)})")
        return problems
