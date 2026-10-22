# Changelog

## 0.1.0 — maiden voyage

- One-command install of Radarr, Sonarr, Prowlarr, qBittorrent, Jellyfin, Seerr, Unpackerr and FlareSolverr
- `galleon-seed`: folder layout, pre-seeded API keys, hashed qBittorrent password, hardlink probe
- Helmsman bootstrap: wires every service over its API and is safe to re-run
- Indexer presets (`public-general`, `public-anime`, `private-it`, `custom`) and a secret-stripping `export-indexers`
- Language packs: en, it, de, fr, es, pt, nl, pl
- Optional Gluetun VPN, GPU transcoding and Recyclarr/TRaSH profiles
- Tested against qBittorrent 5.x (204 login, `QBT_SID_<port>` cookie), *arr "Allowed Hosts" validation and the Seerr v3 library API
