#!/bin/sh
# Use signed Ubuntu indexes over HTTPS with an isolated build-time CA bundle.
set -eu

if [ "$#" -eq 0 ]; then
    echo 'At least one package is required' >&2
    exit 2
fi
# shellcheck source=/dev/null
. /etc/os-release
if [ "$ID:$VERSION_CODENAME" != 'ubuntu:noble' ]; then
    echo 'Container dependencies require Ubuntu 24.04 (noble)' >&2
    exit 1
fi

apt_root=$(mktemp -d)
trap 'rm -rf "$apt_root"' EXIT
chmod 755 "$apt_root"
mkdir "$apt_root/lists"
chmod 755 "$apt_root/lists"
test -r /usr/share/keyrings/ubuntu-archive-keyring.gpg
bootstrap_ca=/tmp/apt-bootstrap-ca.pem
test -s "$bootstrap_ca"
architecture=$(dpkg --print-architecture)
if [ "$architecture" = amd64 ]; then
    printf '%s\t%s\n' \
        'https://security.ubuntu.com/ubuntu/' 'priority:1' \
        'https://archive.ubuntu.com/ubuntu/' 'priority:2' > "$apt_root/mirrors.txt"
else
    printf '%s\n' 'https://ports.ubuntu.com/ubuntu-ports/' > "$apt_root/mirrors.txt"
fi
cat > "$apt_root/ubuntu.sources" <<SOURCES
Types: deb
URIs: mirror+file:$apt_root/mirrors.txt
Suites: noble noble-updates noble-backports noble-security
Components: main restricted universe multiverse
Architectures: $architecture
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES
chmod 644 "$apt_root/mirrors.txt" "$apt_root/ubuntu.sources"
source_list=$apt_root/ubuntu.sources
source_parts=-
apt_get() {
    limit=$1
    shift
    timeout --signal=TERM --kill-after=15s "$limit" apt-get \
        -o Acquire::Retries=2 \
        -o "Acquire::https::CAInfo=$bootstrap_ca" \
        -o Acquire::http::Timeout=20 \
        -o Acquire::https::Timeout=20 \
        -o DPkg::Lock::Timeout=60 \
        -o "Dir::Etc::sourcelist=$source_list" \
        -o "Dir::Etc::sourceparts=$source_parts" \
        -o "Dir::State::lists=$apt_root/lists" "$@"
}
apt_get 180s update --error-on=any
apt_get 360s install --yes --no-install-recommends ca-certificates "$@"
