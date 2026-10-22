#!/usr/bin/env bash
# Voyage test: asserts that `./galleon up` produced a fully wired fleet.
# Usage: tests/e2e.sh   (run from the repo root after ./galleon up)
set -euo pipefail
cd "$(dirname "$0")/.."
get() { grep -E "^$1=" .env | cut -d= -f2-; }
H=localhost
U=$(get GALLEON_ADMIN_USER); P=$(get GALLEON_ADMIN_PASSWORD)
RK=$(get RADARR_API_KEY); SK=$(get SONARR_API_KEY); PK=$(get PROWLARR_API_KEY)
pass=0; fail=0
check() { # check "label" <command...>
  local label=$1; shift
  if "$@" >/dev/null 2>&1; then printf '  \033[32m✔\033[0m %s\n' "$label"; pass=$((pass+1))
  else printf '  \033[31m✖\033[0m %s\n' "$label"; fail=$((fail+1)); fi
}

echo "⛵ voyage test"
# v5 answers 204 + QBT_SID_<port> cookie, v4 answers 200 "Ok."
check "qBittorrent accepts the admin login" sh -c "curl -fsS -i -d 'username=$U&password=$P' -H 'Referer: http://$H:8080' http://$H:8080/api/v2/auth/login | grep -qiE 'set-cookie: (QBT_)?SID[_0-9]*='"
for app in "radarr 7878 $RK /data/media/movies" "sonarr 8989 $SK /data/media/tv"; do
  # shellcheck disable=SC2086  # intentional word splitting
  set -- $app
  check "$1: exactly one qBittorrent download client" sh -c "curl -fsS -H 'X-Api-Key: $3' http://$H:$2/api/v3/downloadclient | python3 -c \"import json,sys; sys.exit(0 if [c['implementation'] for c in json.load(sys.stdin)]==['QBittorrent'] else 1)\""
  check "$1: no duplicate custom formats" sh -c "curl -fsS -H 'X-Api-Key: $3' http://$H:$2/api/v3/customformat | python3 -c \"import json,sys; n=[c['name'] for c in json.load(sys.stdin)]; sys.exit(0 if len(n)==len(set(n)) else 1)\""
  check "$1: root folder $4" sh -c "curl -fsS -H 'X-Api-Key: $3' http://$H:$2/api/v3/rootfolder | grep -q '$4'"
  check "$1: hardlinks enabled" sh -c "curl -fsS -H 'X-Api-Key: $3' http://$H:$2/api/v3/config/mediamanagement | grep -q '\"copyUsingHardlinks\": *true'"
  check "$1: indexers synced from Prowlarr" sh -c "curl -fsS -H 'X-Api-Key: $3' http://$H:$2/api/v3/indexer | python3 -c 'import json,sys; sys.exit(0 if len(json.load(sys.stdin))>0 else 1)'"
done
check "prowlarr: Radarr + Sonarr apps" sh -c "curl -fsS -H 'X-Api-Key: $PK' http://$H:9696/api/v1/applications | python3 -c 'import json,sys; sys.exit(0 if len(json.load(sys.stdin))==2 else 1)'"
check "prowlarr: FlareSolverr proxy" sh -c "curl -fsS -H 'X-Api-Key: $PK' http://$H:9696/api/v1/indexerproxy | grep -q FlareSolverr"
check "jellyfin: wizard completed" sh -c "curl -fsS http://$H:8096/System/Info/Public | grep -q '\"StartupWizardCompleted\":true'"
check "seerr: initialized" sh -c "curl -fsS http://$H:5055/api/v1/settings/public | grep -q '\"initialized\":true'"
echo "  $pass passed, $fail failed"
[[ $fail == 0 ]]
