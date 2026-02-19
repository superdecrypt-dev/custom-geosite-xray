# custom-geosite-xrayder untuk Xray-Core

Build otomatis `custom.dat` dari berbagai sumber blocklist populer untuk digunakan di xray-core.

## Hasil

| File output | Kategori | Penggunaan di xray |
|-------------|----------|--------------------|
| `custom.dat` | `adblock` | `"custom:adblock"` |

---

## Sumber Blocklist

| Sumber | Format | Deskripsi |
|--------|--------|-----------|
| StevenBlack base | hosts | Ads + malware |
| StevenBlack fakenews | hosts | + Fake news |
| GoodbyeAds main | hosts | Mobile ads |
| GoodbyeAds YouTube | hosts | YouTube ads |
| GoodbyeAds Samsung | hosts | Samsung ads |
| EasyList | hosts | Web ads |
| EasyPrivacy | hosts | Tracker & analytics |
| AdGuard DNS | hosts | DNS-level ads |
| Peter Lowe's list | hosts | Ad servers |
| 1Hosts Xtra | hosts | Aggressive adblock |
| OISD Big | domainswild2 | Comprehensive DNS blocklist |
| Phishing Army | plain | Phishing domains |
| URLhaus | hosts | Active malware hosts |

---

## Struktur Folder

```
geosite-builder/
├── builder.py          → Script utama
├── setup.sh            → Script setup & first run
├── config-xray.json    → Contoh config xray
├── README.md
├── data/               → Domain list (dibuat otomatis saat build)
├── output/             → Hasil build: custom.dat
├── logs/               → Log setiap build
├── .cache/             → Cache fetch (valid 6 jam)
└── domain-list-community/  → Go builder (di-clone otomatis)
```

---

## Cara Install

### 1. Prasyarat
- Python 3.8+
- Go 1.18+
- git

### 2. Setup pertama kali
```bash
chmod +x setup.sh
./setup.sh
```

Script akan otomatis:
- Cek dan bantu install Go jika belum ada
- Membuat semua direktori yang dibutuhkan
- Menjalankan build pertama (opsional)

### 3. Install ke xray (manual)
```bash
sudo cp output/custom.dat /usr/local/share/xray/custom.dat
sudo systemctl restart xray
```

---

## Perintah Build

```bash
# Build normal
python3 builder.py

# Hanya fetch & hitung domain, tanpa buat file
python3 builder.py --dry-run

# Paksa fetch ulang semua sumber (abaikan cache)
python3 builder.py --clear-cache

# Tampilkan sample domain saat parsing
python3 builder.py --verbose

# Skip deduplication
python3 builder.py --no-dedup
```

---

## Penggunaan di Config Xray

Tambahkan rule berikut di bagian `routing.rules` **sebelum** rule `direct` atau `proxy`:

```json
{
  "type": "field",
  "domain": ["custom:adblock"],
  "outboundTag": "block"
}
```

Contoh config lengkap tersedia di `config-xray.json`.

---

## Tambah Sumber Blocklist Sendiri

Edit bagian `SOURCES` di `builder.py`:

```python
"nama-sumber": {
    "url": "https://url-blocklist.com/hosts.txt",
    "format": "hosts",      # hosts / plain / domainswild2
    "description": "Deskripsi singkat",
},
```

Format yang didukung:

| Format | Keterangan |
|--------|-----------|
| `hosts` | File `/etc/hosts`: `0.0.0.0 domain.com` |
| `plain` | Satu domain per baris |
| `domainswild2` | Format OISD: `*.domain.com` |

Lalu build ulang:
```bash
python3 builder.py --clear-cache
```

---

## Troubleshooting

**Go tidak ditemukan:**
```bash
export PATH=$PATH:/usr/local/go/bin
# Atau install dari https://golang.org/dl/
```

**Fetch gagal (timeout/network error):**
```bash
python3 builder.py --clear-cache
```

**Ingin lihat domain apa saja yang diblokir:**
```bash
python3 builder.py --dry-run --verbose 2>&1 | less
```

**Verifikasi xray membaca custom.dat:**
```bash
# Pastikan file ada
ls -lh /usr/local/share/xray/custom.dat

# Cek log xray
sudo journalctl -u xray -n 50
```
