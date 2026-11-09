#!/usr/bin/env bash
# テスト用の SMB サーバー (Samba) をポート 1445 で起動する (Ubuntu / Debian 用)。
#   ./scripts/start-test-samba.sh
#   SMB_TEST_HOST=127.0.0.1 SMB_TEST_PORT=1445 SMB_TEST_SHARE=share \
#   SMB_TEST_USER=smbtest SMB_TEST_PASSWORD=secret ./gradlew :core:test
set -euo pipefail

command -v smbd >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq samba; }

dir="$(mktemp -d)"
chmod 755 "$dir"
mkdir -p "$dir/share"
chmod 777 "$dir/share"
id smbtest >/dev/null 2>&1 || sudo useradd -M -s /usr/sbin/nologin smbtest

cat > "$dir/smb.conf" <<CONF
[global]
  server min protocol = SMB2_02
  map to guest = Bad User
  disable netbios = yes
  smb ports = 1445
  load printers = no
  printing = bsd
  printcap name = /dev/null
[share]
  path = $dir/share
  read only = no
  guest ok = yes
  force user = smbtest
CONF

printf 'secret\nsecret\n' | sudo smbpasswd -c "$dir/smb.conf" -a -s smbtest >/dev/null
sudo smbd -s "$dir/smb.conf" -D
for _ in $(seq 1 20); do
  (echo >/dev/tcp/127.0.0.1/1445) 2>/dev/null && { echo "Samba is listening on 127.0.0.1:1445 ($dir/share)"; exit 0; }
  sleep 0.5
done
echo "Samba did not start" >&2
exit 1
