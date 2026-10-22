# Configuration reference

Every setting lives in `.env`, which `./galleon init` generates. After you edit it, run `./galleon up` (this recreates the containers whose settings changed) and then `./galleon bootstrap`.

## Core

| Variable | Default | Meaning |
|---|---|---|
| `GALLEON_DATA_DIR` | `./data` | Media and downloads. **Must be a single filesystem** for hardlinks to work |
| `GALLEON_CONFIG_DIR` | `./config` | One sub-folder per service |
| `GALLEON_HOST` | auto-detected LAN IP | Used for the links Galleon prints, for Seerr/Jellyfin public URLs and for the *arr "Allowed Hosts" list |
| `GALLEON_ALLOWED_HOSTS` | *(empty)* | Extra comma-separated host names (e.g. `nas.local`) that may use password-less LAN access to the *arr apps |
| `PUID` / `PGID` | your user | The user that owns every file the stack writes |
| `TZ` | host timezone | |
| `GALLEON_ADMIN_USER` / `GALLEON_ADMIN_PASSWORD` | `admin` / random | The single login shared by the whole stack |
| `RADARR_API_KEY`, `SONARR_API_KEY`, `PROWLARR_API_KEY` | random | Seeded before first boot. Changing them on a live install does nothing: `config.xml` wins |

## Behaviour

| Variable | Default | Meaning |
|---|---|---|
| `GALLEON_LANGUAGE` | from `$LANG` | `en it de fr es pt nl pl`: sets Jellyfin metadata and library names, the Seerr UI language and a preferred-audio custom format |
| `GALLEON_INDEXER_PRESETS` | *(empty)* | Comma-separated preset names, see [`presets/indexers`](../presets/indexers) |
| `GALLEON_QUALITY_PROFILE` | `HD-1080p` | The Radarr/Sonarr profile Seerr requests with |
| `GALLEON_TRASH` | `false` | Runs Recyclarr daily with the TRaSH "HD Bluray + WEB" and "WEB-1080p" profiles |
| `GALLEON_GPU` | `false` | Passes `/dev/dri` to Jellyfin (Intel QSV / AMD VAAPI). Set `GALLEON_RENDER_GID` to `getent group render \| cut -d: -f3` |
| `GALLEON_VPN` | `false` | Runs qBittorrent inside Gluetun's network namespace |

## VPN

When `GALLEON_VPN=true`, all of qBittorrent's traffic goes through [Gluetun](https://github.com/qdm12/gluetun-wiki). If the tunnel drops, its kill switch blocks the traffic. Example for WireGuard:

```ini
GALLEON_VPN=true
VPN_SERVICE_PROVIDER=mullvad
VPN_TYPE=wireguard
WIREGUARD_PRIVATE_KEY=...
WIREGUARD_ADDRESSES=10.64.0.1/32
VPN_SERVER_COUNTRIES=Netherlands
VPN_FORWARDED_PORT=        # if your provider gives you one
```

Radarr and Sonarr then reach qBittorrent at `gluetun:8080`, and Galleon sets this up for you.

## Hardware transcoding

- **Intel / AMD:** `GALLEON_GPU=true`, then in Jellyfin go to *Dashboard → Playback → Transcoding* and choose QSV or VAAPI.
- **NVIDIA:** install the NVIDIA Container Toolkit and add a `compose.override.yaml`:

  ```yaml
  services:
    jellyfin:
      deploy:
        resources:
          reservations:
            devices: [{ driver: nvidia, count: all, capabilities: [gpu] }]
  ```

## Private tracker credentials

Presets refer to credentials as `${GALLEON_IDX_<INDEXER>_<FIELD>}`. Add the real values to `.env`:

```ini
GALLEON_IDX_ILCORSAROBLU_USERNAME=me
GALLEON_IDX_ILCORSAROBLU_PASSWORD=hunter2
```

Galleon skips an indexer, with a warning, while its variables are missing.

## Migrating from an existing install

```bash
./galleon export-indexers --url http://old-nas:9696 --api-key <old prowlarr key>
# → config/galleon/indexers.yml (+ the list of GALLEON_IDX_* lines to add to .env)
sed -i 's/^GALLEON_INDEXER_PRESETS=.*/GALLEON_INDEXER_PRESETS=custom/' .env
./galleon bootstrap
```
