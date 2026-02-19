#!/bin/bash
# ============================================================
#  SETUP SCRIPT — Custom Geosite Builder untuk Xray-Core
#  - Cek & install dependensi (Go, git, python3)
#  - Jalankan build pertama (opsional)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDER_SCRIPT="$SCRIPT_DIR/builder.py"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
title() { echo -e "\n${CYAN}$1${NC}"; }

echo ""
echo "════════════════════════════════════════════════"
echo "   Custom Geosite Builder — Setup"
echo "════════════════════════════════════════════════"

# ── 1. Cek Python3 ──
title "▸ Mengecek Python3..."
if command -v python3 &>/dev/null; then
    info "Python3 ditemukan: $(python3 --version)"
else
    error "Python3 tidak ditemukan. Install dengan: sudo apt install python3"
fi

# ── 2. Cek Git ──
title "▸ Mengecek Git..."
if command -v git &>/dev/null; then
    info "Git ditemukan: $(git --version)"
else
    warn "Git tidak ditemukan. Mencoba install..."
    sudo apt-get update -qq && sudo apt-get install -y git \
        || error "Gagal install git. Install manual: sudo apt install git"
    info "Git berhasil diinstall."
fi

# ── 3. Cek Go ──
title "▸ Mengecek Go..."
GO_BIN=""
for candidate in "go" "/usr/local/go/bin/go" "/usr/bin/go" "$HOME/go/bin/go" "/snap/bin/go"; do
    if command -v "$candidate" &>/dev/null 2>&1; then
        GO_BIN="$candidate"
        break
    fi
done

if [ -n "$GO_BIN" ]; then
    info "Go ditemukan: $($GO_BIN version)"
else
    warn "Go tidak ditemukan."
    echo ""
    read -rp "  Install Go otomatis? [y/N] " yn_go
    if [[ "$yn_go" =~ ^[Yy]$ ]]; then
        GO_VERSION="1.22.4"
        ARCH="amd64"
        [[ "$(uname -m)" == "aarch64" ]] && ARCH="arm64"
        GO_TAR="go${GO_VERSION}.linux-${ARCH}.tar.gz"
        GO_URL="https://golang.org/dl/${GO_TAR}"

        info "Mendownload Go ${GO_VERSION} (${ARCH})..."
        wget -q --show-progress "$GO_URL" -O "/tmp/${GO_TAR}" \
            || error "Gagal download Go. Cek koneksi internet."

        info "Menginstall Go ke /usr/local/go..."
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf "/tmp/${GO_TAR}"
        rm "/tmp/${GO_TAR}"

        # Tambah ke PATH permanen
        PROFILE_LINE='export PATH=$PATH:/usr/local/go/bin'
        for rc in ~/.bashrc ~/.profile; do
            grep -qF "/usr/local/go/bin" "$rc" 2>/dev/null || echo "$PROFILE_LINE" >> "$rc"
        done
        export PATH=$PATH:/usr/local/go/bin

        info "Go berhasil diinstall: $(go version)"
    else
        warn "Lewati install Go."
        warn "Builder tidak bisa membuat .dat tanpa Go."
        warn "Install manual: https://golang.org/dl/"
    fi
fi

# ── 4. Buat direktori yang diperlukan ──
title "▸ Menyiapkan direktori..."
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/output"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/.cache"
info "Direktori siap."

# ── 5. First Run ──
echo ""
echo "════════════════════════════════════════════════"
read -rp "  Jalankan build pertama sekarang? [y/N] " yn_build
echo "════════════════════════════════════════════════"
if [[ "$yn_build" =~ ^[Yy]$ ]]; then
    echo ""
    info "Memulai build pertama..."
    python3 "$BUILDER_SCRIPT"
else
    echo ""
    warn "Build dilewati."
fi

# ── Selesai ──
echo ""
echo "════════════════════════════════════════════════"
echo "  Setup selesai!"
echo ""
echo "  Perintah build:"
echo "    python3 builder.py               → Build normal"
echo "    python3 builder.py --dry-run     → Test tanpa build"
echo "    python3 builder.py --clear-cache → Fetch ulang semua"
echo "    python3 builder.py --verbose     → Tampilkan domain"
echo ""
echo "  Setelah build, install manual:"
echo "    sudo cp output/custom.dat /usr/local/share/xray/custom.dat"
echo "    sudo systemctl restart xray"
echo ""
echo "  Gunakan di config xray:"
echo "    \"domain\": [\"custom:adblock\"]"
echo "════════════════════════════════════════════════"
echo ""
"  Perintah build:"
echo "    python3 builder.py               → Build normal"
echo "    python3 builder.py --dry-run     → Test tanpa build"
echo "    python3 builder.py --clear-cache → Fetch ulang semua"
echo "    python3 builder.py --verbose     → Tampilkan domain"
echo ""
echo "  Setelah build, install manual:"
echo "    sudo cp output/custom.dat /usr/local/share/xray/custom.dat"
echo "    sudo systemctl restart xray"
echo ""
echo "  Gunakan di config xray:"
echo "    \"domain\": [\"custom:adblock\"]"
echo "════════════════════════════════════════════════"
echo ""
