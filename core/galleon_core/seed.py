"""Pre-flight: create the folder layout and pre-seed config files before any service starts.

Everything here is create-if-missing, so re-running never clobbers a live install.
"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import sys

from . import log
from .settings import Settings

ARR_PORTS = {"radarr": 7878, "sonarr": 8989, "prowlarr": 9696}

CONFIG_DIRS = [
    "radarr", "sonarr", "prowlarr", "qbittorrent/qBittorrent", "jellyfin/config", "jellyfin/cache",
    "seerr", "unpackerr", "recyclarr", "galleon",
]

DATA_DIRS = ["torrents/movies", "torrents/tv", "media/movies", "media/tv"]

ARR_CONFIG = """<Config>
  <BindAddress>*</BindAddress>
  <Port>{port}</Port>
  <UrlBase></UrlBase>
  <ApiKey>{key}</ApiKey>
  <AuthenticationMethod>Forms</AuthenticationMethod>
  <AuthenticationRequired>DisabledForLocalAddresses</AuthenticationRequired>
  <AllowedHosts>{allowed}</AllowedHosts>
  <AnalyticsEnabled>False</AnalyticsEnabled>
  <LogLevel>info</LogLevel>
  <InstanceName>{name}</InstanceName>
</Config>
"""

QBIT_CONFIG = """[BitTorrent]
Session\\DefaultSavePath=/data/torrents
Session\\TempPathEnabled=false
Session\\Port={torrent_port}
Session\\DisableAutoTMMByDefault=false

[LegalNotice]
Accepted=true

[Preferences]
General\\Locale={locale}
WebUI\\Port=8080
WebUI\\Username={user}
WebUI\\Password_PBKDF2="@ByteArray({hash})"
WebUI\\HostHeaderValidation=false
WebUI\\CSRFProtection=true
"""


def qbit_password_hash(password: str) -> str:
    """qBittorrent's WebUI\\Password_PBKDF2 format: base64(salt):base64(pbkdf2-sha512)."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100_000, dklen=64)
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"


def _mkdir(path: str, uid: int, gid: int) -> bool:
    """mkdir -p that chowns only the levels it creates, never existing user data."""
    if os.path.isdir(path):
        return False
    _mkdir(os.path.dirname(path), uid, gid)
    os.mkdir(path, 0o775)
    os.chown(path, uid, gid)
    return True


def _claim_mount(path: str, uid: int, gid: int) -> None:
    """Docker creates missing bind-mount sources as root: hand fresh, empty ones to PUID."""
    st = os.stat(path)
    if st.st_uid == 0 and uid != 0 and not os.listdir(path):
        os.chown(path, uid, gid)
        os.chmod(path, 0o775)


def _write_once(path: str, content: str, uid: int, gid: int) -> bool:
    if os.path.exists(path):
        return False
    with open(path, "w") as f:
        f.write(content)
    os.chown(path, uid, gid)
    os.chmod(path, 0o660)
    return True


def run(s: Settings) -> int:
    log.banner("Galleon · preparing the hull")
    problems = s.validate()
    if problems:
        for p in problems:
            log.fail(p)
        log.fail("Fix .env (or run `./galleon init`) and try again.")
        return 2

    log.section("Folders")
    _claim_mount(s.config_root, s.puid, s.pgid)
    _claim_mount(s.data_root, s.puid, s.pgid)
    for d in CONFIG_DIRS:
        if _mkdir(os.path.join(s.config_root, d), s.puid, s.pgid):
            log.ok(f"config/{d}")
    for d in DATA_DIRS:
        if _mkdir(os.path.join(s.data_root, d), s.puid, s.pgid):
            log.ok(f"data/{d}")
    log.skip("existing folders left untouched")

    log.section("Pre-seeded configs")
    keys = {"radarr": s.radarr_key, "sonarr": s.sonarr_key, "prowlarr": s.prowlarr_key}
    for app, port in ARR_PORTS.items():
        path = os.path.join(s.config_root, app, "config.xml")
        content = ARR_CONFIG.format(port=port, key=keys[app], name=app.capitalize(), allowed=s.allowed_hosts(app))
        if _write_once(path, content, s.puid, s.pgid):
            log.ok(f"{app}: API key + forms auth")
        else:
            log.skip(f"{app}: config.xml exists, keeping it")

    qbit_conf = os.path.join(s.config_root, "qbittorrent/qBittorrent/qBittorrent.conf")
    content = QBIT_CONFIG.format(
        torrent_port=os.environ.get("GALLEON_TORRENT_PORT", "6881"),
        locale=s.lang[1].replace("-", "_"),
        user=s.admin_user,
        hash=qbit_password_hash(s.admin_password),
    )
    if _write_once(qbit_conf, content, s.puid, s.pgid):
        log.ok("qbittorrent: WebUI credentials + /data/torrents")
    else:
        log.skip("qbittorrent: qBittorrent.conf exists, keeping it")

    recyclarr = os.path.join(s.config_root, "recyclarr/recyclarr.yml")
    if not os.path.exists(recyclarr) and os.path.exists("/opt/galleon/recyclarr.yml"):
        shutil.copy("/opt/galleon/recyclarr.yml", recyclarr)
        os.chown(recyclarr, s.puid, s.pgid)
        log.ok("recyclarr: TRaSH template")

    log.section("Hardlink check")
    probe_src = os.path.join(s.data_root, "torrents", ".galleon-probe")
    probe_dst = os.path.join(s.data_root, "media", ".galleon-probe")
    try:
        with open(probe_src, "w") as f:
            f.write("⛵")
        os.link(probe_src, probe_dst)
        log.ok("torrents/ and media/ share a filesystem: instant, space-free imports")
    except OSError as e:
        log.warn(f"hardlinks unavailable ({e.strerror}): imports will be copies")
    finally:
        for p in (probe_src, probe_dst):
            if os.path.exists(p):
                os.remove(p)

    log.ok("hull ready")
    return 0


if __name__ == "__main__":
    sys.exit(run(Settings()))
