#!/usr/bin/env python3
"""
=============================================================
  Custom Geosite Builder untuk Xray-Core
  Output : custom.dat
  Geosite: custom:adblock

  Sumber  : StevenBlack, GoodbyeAds, EasyList, EasyPrivacy,
            AdGuard DNS, Peter Lowe, 1Hosts Xtra, OISD Big,
            Phishing Army, URLhaus
=============================================================
  Cara pakai:
    python3 builder.py               → build normal
    python3 builder.py --dry-run     → fetch & hitung saja, tanpa build
    python3 builder.py --verbose     → tampilkan domain saat parsing
    python3 builder.py --no-dedup    → skip deduplication
    python3 builder.py --clear-cache → hapus cache, fetch ulang semua
=============================================================
"""

import os
import re
import sys
import time
import shutil
import hashlib
import logging
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
OUTPUT_DIR  = BASE_DIR / "output"
LOG_DIR     = BASE_DIR / "logs"
BUILDER_DIR = BASE_DIR / "domain-list-community"
CACHE_DIR   = BASE_DIR / ".cache"

# Nama file output dan kategori geosite
OUTPUT_FILENAME = "custom.dat"
GEOSITE_CATEGORY = "adblock"

# Daftar sumber blocklist — semua masuk kategori "adblock"
SOURCES = {
    "stevenblack-base": {
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        "format": "hosts",
        "description": "StevenBlack base (ads + malware)",
    },
    "stevenblack-fakenews": {
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews/hosts",
        "format": "hosts",
        "description": "StevenBlack + Fake News",
    },
    "goodbyeads-main": {
        "url": "https://raw.githubusercontent.com/jerryn70/GoodbyeAds/master/Hosts/GoodbyeAds.txt",
        "format": "hosts",
        "description": "GoodbyeAds main list",
    },
    "goodbyeads-youtube": {
        "url": "https://raw.githubusercontent.com/jerryn70/GoodbyeAds/master/Extension/GoodbyeAds-YouTube-AdBlock.txt",
        "format": "hosts",
        "description": "GoodbyeAds YouTube AdBlock",
    },
    "goodbyeads-samsung": {
        "url": "https://raw.githubusercontent.com/jerryn70/GoodbyeAds/master/Extension/GoodbyeAds-Samsung-AdBlock.txt",
        "format": "hosts",
        "description": "GoodbyeAds Samsung AdBlock",
    },
    "easylist": {
        "url": "https://v.firebog.net/hosts/Easylist.txt",
        "format": "hosts",
        "description": "EasyList (via Firebog)",
    },
    "easyprivacy": {
        "url": "https://v.firebog.net/hosts/Easyprivacy.txt",
        "format": "hosts",
        "description": "EasyPrivacy tracker list",
    },
    "adguard-dns": {
        "url": "https://v.firebog.net/hosts/AdguardDNS.txt",
        "format": "hosts",
        "description": "AdGuard DNS filter",
    },
    "peterlowe": {
        "url": "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
        "format": "hosts",
        "description": "Peter Lowe's Ad and tracking server list",
    },
    "1hosts-xtra": {
        "url": "https://github.com/badmojr/1Hosts/releases/download/latest/1hosts-Xtra_hosts.txt",
        "format": "hosts",
        "description": "1Hosts Xtra (aggressive adblock)",
    },
    "oisd-big": {
        "url": "https://big.oisd.nl/domainswild2",
        "format": "domainswild2",
        "description": "OISD Big (comprehensive DNS blocklist)",
    },
    "phishing-army": {
        "url": "https://phishing.army/download/phishing_army_blocklist.txt",
        "format": "plain",
        "description": "Phishing Army blocklist",
    },
    "urlhaus-malware": {
        "url": "https://urlhaus.abuse.ch/downloads/hostfile/",
        "format": "hosts",
        "description": "URLhaus malware hosts",
    },
}

# Domain yang tidak boleh diblokir (whitelist)
WHITELIST = {
    "localhost",
    "local",
    "broadcasthost",
    "ip6-localhost",
    "ip6-loopback",
    "ip6-localnet",
    "ip6-mcastprefix",
    "ip6-allnodes",
    "ip6-allrouters",
    "ip6-allhosts",
    "0.0.0.0",
    "analytics.google.com",
    "clients.google.com",
    "update.googleapis.com",
}

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  FETCH
# ─────────────────────────────────────────────

def fetch_url(url: str, source_name: str) -> str | None:
    """Download URL dengan retry 3x dan caching 6 jam."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key  = hashlib.md5(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.cache"
    cache_meta = CACHE_DIR / f"{cache_key}.meta"

    if cache_file.exists() and cache_meta.exists():
        if time.time() - float(cache_meta.read_text().strip()) < 6 * 3600:
            log.info(f"  [CACHE] {source_name}")
            return cache_file.read_text(encoding="utf-8", errors="ignore")

    for attempt in range(1, 4):
        try:
            log.info(f"  [FETCH] {source_name} (attempt {attempt}) ← {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GeoSiteBuilder/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                cache_file.write_text(content, encoding="utf-8")
                cache_meta.write_text(str(time.time()))
                return content
        except urllib.error.URLError as e:
            log.warning(f"  [WARN] Gagal fetch {source_name}: {e}")
            if attempt < 3:
                time.sleep(3 * attempt)
    return None


# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

def is_valid_domain(domain: str) -> bool:
    """Validasi format domain."""
    if not domain or len(domain) > 253 or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or domain.startswith("-"):
        return False
    if not re.match(r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$', domain):
        return False
    for label in domain.split("."):
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
    return True


def parse_hosts_format(content: str) -> set[str]:
    """Parse format /etc/hosts: '0.0.0.0 domain.com' atau '127.0.0.1 domain.com'."""
    domains = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "#" in line:
            line = line[:line.index("#")].strip()
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1", "::1", "::"):
            d = parts[1].lower().strip()
            if d not in WHITELIST and is_valid_domain(d):
                domains.add(d)
        elif len(parts) == 1:
            d = parts[0].lower().strip().lstrip("|").rstrip("^")
            if d not in WHITELIST and is_valid_domain(d):
                domains.add(d)
    return domains


def parse_plain_format(content: str) -> set[str]:
    """Parse format plain: satu domain per baris."""
    domains = set()
    for line in content.splitlines():
        line = re.sub(r'^(\|\||\|)', '', line.strip().lower())
        line = re.sub(r'[\^/].*$', '', line).strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if line not in WHITELIST and is_valid_domain(line):
            domains.add(line)
    return domains


def parse_domainswild2_format(content: str) -> set[str]:
    """
    Parse format domainswild2 dari OISD.
    Setiap baris bisa berupa '*.domain.com' atau 'domain.com'.
    Prefix '*.' dihapus karena xray 'domain:' sudah match semua subdomain.
    """
    domains = set()
    for line in content.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if line.startswith("*."):
            line = line[2:]
        if line not in WHITELIST and is_valid_domain(line):
            domains.add(line)
    return domains


# ─────────────────────────────────────────────
#  DEDUPLICATION
# ─────────────────────────────────────────────

def deduplicate_domains(domains: set[str]) -> set[str]:
    """
    Hapus subdomain yang redundant.
    Contoh: jika 'example.com' ada, maka 'ads.example.com' dihapus
    karena xray 'domain:example.com' sudah mencakup semua subdomainnya.
    """
    log.info("  Deduplicating domains...")
    sorted_domains = sorted(domains, key=lambda d: len(d.split(".")))
    result = set()
    for domain in sorted_domains:
        parts = domain.split(".")
        is_redundant = any(
            ".".join(parts[i:]) in result
            for i in range(1, len(parts) - 1)
        )
        if not is_redundant:
            result.add(domain)
    removed = len(domains) - len(result)
    log.info(f"  Removed {removed:,} redundant subdomains")
    return result


# ─────────────────────────────────────────────
#  FILE WRITER
# ─────────────────────────────────────────────

def write_domain_list(domains: set[str]) -> Path:
    """Tulis file domain list untuk Go builder."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / GEOSITE_CATEGORY
    lines = [
        f"# {'='*58}",
        f"# Custom Geosite - {GEOSITE_CATEGORY}",
        f"# Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Total     : {len(domains):,} domains",
        f"# Sources   : {', '.join(SOURCES.keys())}",
        f"# {'='*58}",
        "",
    ]
    for domain in sorted(domains):
        lines.append(f"domain:{domain}")
    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(f"  Written: {filepath} ({len(domains):,} domains)")
    return filepath


# ─────────────────────────────────────────────
#  GO BUILDER
# ─────────────────────────────────────────────

def find_go() -> str | None:
    """Cari binary Go di lokasi umum."""
    candidates = [
        "go",
        "/usr/local/go/bin/go",
        "/usr/bin/go",
        os.path.expanduser("~/go/bin/go"),
        "/snap/bin/go",
    ]
    for path in candidates:
        try:
            result = subprocess.run([path, "version"], capture_output=True)
            if result.returncode == 0:
                log.info(f"  Go ditemukan: {path}")
                return path
        except FileNotFoundError:
            continue
    return None


def clone_or_update_builder():
    """Clone atau update domain-list-community."""
    if BUILDER_DIR.exists():
        log.info("Updating domain-list-community builder...")
        result = subprocess.run(["git", "pull"], cwd=BUILDER_DIR, capture_output=True, text=True)
        log.info(f"  git pull: {result.stdout.strip()}")
    else:
        log.info("Cloning domain-list-community builder...")
        subprocess.run([
            "git", "clone", "--depth=1",
            "https://github.com/v2fly/domain-list-community",
            str(BUILDER_DIR)
        ], check=True)


def copy_data_to_builder():
    """Salin file domain list ke folder data builder."""
    builder_data = BUILDER_DIR / "data"
    for f in DATA_DIR.iterdir():
        shutil.copy2(f, builder_data / f.name)
        log.info(f"  Copied: {f.name} → builder/data/")


def run_builder() -> bool:
    """Jalankan Go builder, output default: dlc.dat."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    go_bin = find_go()
    if not go_bin:
        log.error("Go tidak ditemukan! Install: https://golang.org/dl/")
        log.error("Atau tambahkan ke PATH: export PATH=$PATH:/usr/local/go/bin")
        return False

    log.info("Running Go builder...")
    result = subprocess.run(
        [go_bin, "run", "./", f"-outputdir={OUTPUT_DIR}"],
        cwd=BUILDER_DIR,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error(f"Builder error:\n{result.stderr}")
        return False
    log.info("  Build successful!")
    return True


def rename_output() -> bool:
    """Rename dlc.dat → custom.dat di folder output."""
    dlc_file    = OUTPUT_DIR / "dlc.dat"
    custom_file = OUTPUT_DIR / OUTPUT_FILENAME

    # Hapus file stale dari run sebelumnya jika ada
    for stale in ["geosite", "geosite.dat"]:
        p = OUTPUT_DIR / stale
        if p.exists():
            p.unlink()
            log.info(f"  Removed stale file: {stale}")

    if dlc_file.exists():
        shutil.move(str(dlc_file), str(custom_file))
        log.info(f"  Renamed: dlc.dat → {OUTPUT_FILENAME}")
        return True
    elif custom_file.exists():
        log.info(f"  Output: {custom_file}")
        return True
    else:
        files = [f.name for f in OUTPUT_DIR.iterdir()] if OUTPUT_DIR.exists() else []
        log.error(f"Output file tidak ditemukan! Isi folder: {files}")
        return False


# ─────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────

def print_summary(stats: dict):
    print("\n" + "="*60)
    print("  BUILD SUMMARY")
    print("="*60)
    for src_name, count in stats["fetched"].items():
        print(f"  ✓ {src_name:<35} {count:>8,} domains")
    print("-"*60)
    print(f"  📦 {GEOSITE_CATEGORY} (after dedup)  {stats['total']:>14,} domains")
    print(f"  📁 Output : {OUTPUT_DIR}/{OUTPUT_FILENAME}")
    print(f"  📝 Log    : {log_file}")
    print("="*60)
    print(f"\n  Install manual:")
    print(f"    sudo cp {OUTPUT_DIR}/{OUTPUT_FILENAME} /usr/local/share/xray/{OUTPUT_FILENAME}")
    print(f"    sudo systemctl restart xray")
    print()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Custom Geosite Builder for Xray-Core")
    parser.add_argument("--dry-run",     action="store_true", help="Fetch & hitung saja, tidak build .dat")
    parser.add_argument("--verbose",     action="store_true", help="Tampilkan domain saat parsing")
    parser.add_argument("--no-dedup",    action="store_true", help="Skip deduplication")
    parser.add_argument("--clear-cache", action="store_true", help="Hapus cache, fetch ulang semua sumber")
    args = parser.parse_args()

    if args.clear_cache and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        log.info("Cache cleared.")

    log.info("=" * 60)
    log.info("  Custom Geosite Builder for Xray-Core")
    log.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # ── Step 1: Fetch & Parse ──
    all_domains: set[str] = set()
    stats = {"fetched": {}, "total": 0}

    for source_name, cfg in SOURCES.items():
        log.info(f"\n[{source_name}] {cfg['description']}")
        content = fetch_url(cfg["url"], source_name)
        if not content:
            log.warning(f"  Skipping {source_name} (fetch failed)")
            continue

        if cfg["format"] == "hosts":
            domains = parse_hosts_format(content)
        elif cfg["format"] == "domainswild2":
            domains = parse_domainswild2_format(content)
        else:
            domains = parse_plain_format(content)

        log.info(f"  Parsed: {len(domains):,} domains")
        stats["fetched"][source_name] = len(domains)
        all_domains |= domains

        if args.verbose:
            for d in sorted(list(domains))[:20]:
                print(f"    {d}")
            if len(domains) > 20:
                print(f"    ... dan {len(domains) - 20:,} lainnya")

    # ── Step 2: Deduplication ──
    log.info("\n[DEDUP] Menghapus domain redundant...")
    final_domains = deduplicate_domains(all_domains) if not args.no_dedup else all_domains
    stats["total"] = len(final_domains)
    log.info(f"  Total unik: {len(final_domains):,} domains")

    if args.dry_run:
        log.info("\n[DRY RUN] Selesai. Tidak ada file yang dibuat.")
        print_summary(stats)
        return

    # ── Step 3: Tulis domain list ──
    log.info(f"\n[WRITE] Menulis {GEOSITE_CATEGORY}...")
    write_domain_list(final_domains)

    # ── Step 4: Clone/update Go builder ──
    log.info("\n[BUILDER] Menyiapkan Go builder...")
    try:
        clone_or_update_builder()
    except subprocess.CalledProcessError as e:
        log.error(f"Gagal clone builder: {e}")
        sys.exit(1)

    # ── Step 5: Copy data ke builder ──
    copy_data_to_builder()

    # ── Step 6: Build .dat ──
    log.info(f"\n[BUILD] Building {OUTPUT_FILENAME}...")
    if not run_builder():
        log.error("Build gagal!")
        sys.exit(1)

    # ── Step 7: Rename output ──
    if not rename_output():
        log.error("Rename output gagal!")
        sys.exit(1)

    print_summary(stats)
    log.info("Build selesai!")


if __name__ == "__main__":
    main()
