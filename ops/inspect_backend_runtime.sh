#!/usr/bin/env bash
set -euo pipefail
for image in medsynth-api:ci medsynth-worker:ci; do
  name=${image%%:*}
  docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
    --entrypoint sh "$image" -ec '
      id
      cat /etc/os-release
      grep -E "^(Uid|Gid|CapEff|NoNewPrivs):" /proc/self/status
      dpkg-query -W ncurses-bin ncurses-base libncursesw6 libtinfo6 libsystemd0 libudev1 libacl1 util-linux mount perl-base
      command -v infocmp
      command -v nsenter
      nsenter --help
      cat /etc/fstab
      if command -v systemd-homed; then exit 1; fi
      if perl -MArchive::Tar -e 1; then exit 1; fi
      if find /usr -name systemd-homed -o -path "*/Archive/Tar.pm" | grep .; then exit 1; fi
      python -c "import torch,numpy,scipy,psycopg,sdv,PIL; from pathlib import Path; m=Path(\"/proc/self/maps\").read_text(); print({n:n in m for n in (\"libacl\",\"libsystemd\",\"libudev\",\"libncurses\",\"libtinfo\")}); print(torch.__version__,sdv.__version__)"
    ' > "release-artifacts/$name-runtime.txt" 2>&1
  docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
    --tmpfs /tmp:uid=10001,gid=10001,mode=1770 -e PYTHONPATH=/app \
    -v "$PWD/ops:/verification:ro" --entrypoint python "$image" \
    /verification/container_model_probe.py > "release-artifacts/$name-models.txt" 2>&1
done
test "$(docker inspect --format '{{.Config.User}}' medsynth-api:ci)" = 10001:10001
test "$(docker inspect --format '{{.Config.User}}' medsynth-worker:ci)" = 10001:10001
test "$(docker inspect --format '{{.Config.User}}' medsynth-frontend:ci)" = 101:101
