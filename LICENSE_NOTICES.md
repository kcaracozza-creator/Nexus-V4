# NEXUS Third-Party License Notices

NEXUS incorporates third-party software components. This document lists components
whose licenses require attribution or impose distribution conditions.

---

## Permissive Licenses (MIT / BSD / Apache 2.0 / PSF)

The following major dependencies are used under permissive licenses that impose
no copyleft conditions on NEXUS:

| Package | License | Use |
|---|---|---|
| FastAPI | MIT | REST API framework |
| Flask / Werkzeug | BSD 3-Clause | Marketplace API |
| Uvicorn | BSD 3-Clause | ASGI server |
| Requests | Apache 2.0 | HTTP client |
| NumPy | BSD 3-Clause | Numerical processing |
| Pandas | BSD 3-Clause | Data analysis |
| SQLAlchemy | MIT | ORM / database layer |
| Pillow | MIT-like (PIL) | Image processing |
| PyTesseract | Apache 2.0 | OCR wrapper |
| Tesseract OCR | Apache 2.0 | OCR engine |
| PyTorch | BSD 3-Clause | ML inference |
| TensorFlow-ROCm | Apache 2.0 | ML (AMD GPU) |
| Stable-Baselines3 | MIT | RL training |
| Gymnasium | MIT | RL environments |
| PyBullet | zlib | Physics simulation |
| PySerial | BSD 3-Clause | Serial hardware I/O |
| Python-Jose | MIT | JWT auth |
| Passlib | BSD | Password hashing |
| bcrypt | Apache 2.0 | Password hashing |
| RapidFuzz | MIT | Fuzzy string matching |
| BeautifulSoup4 | MIT | HTML parsing |
| lxml | BSD 3-Clause | XML/HTML parser |
| Gunicorn | MIT | Production WSGI server |
| Pytest / Black / Flake8 | MIT | Dev tooling |

---

## LGPL Dependencies

The following dependencies are licensed under the GNU Lesser General Public License (LGPL).
LGPL permits use in proprietary software. The LGPL obligation is that end users must be
able to replace the LGPL library with a modified version. Since NEXUS installs these
via pip (standard Python dynamic linking), this requirement is satisfied.

### psycopg2-binary
- **License**: GNU Lesser General Public License v3 (LGPL-3.0)
- **Use**: PostgreSQL database driver
- **Source**: https://github.com/psycopg/psycopg2
- **Bundled components**: libpq, OpenSSL (both LGPL/OpenSSL-compatible)
- **LGPL note**: Users may substitute psycopg2 with any LGPL-compatible build.
  The psycopg2 source code is available at the URL above.

### opencv-python (FFmpeg component)
- **License**: Apache 2.0 (OpenCV core); bundled FFmpeg is LGPL 2.1+
- **Use**: Computer vision, image processing, card scanning
- **Source**: https://github.com/opencv/opencv
- **FFmpeg source**: https://ffmpeg.org/download.html
- **LGPL note**: The FFmpeg libraries bundled in the PyPI opencv-python wheel are
  compiled with LGPL (non-GPL) codecs only. Users may substitute the FFmpeg
  libraries with any LGPL-compatible build. FFmpeg source is available at the
  URL above.

---

## SIL Open Font License (OFL-1.1)

### Keyrune Font
- **License**: SIL Open Font License 1.1 (OFL-1.1)
- **Use**: MTG set symbol glyphs rendered in NEXUS UI
- **Author**: Andrew Gioia
- **Source**: https://github.com/andrewgioia/keyrune
- **Font file used**: `assets/fonts/keyrune.ttf`
- **OFL summary**: The font may be used, embedded, and distributed freely in any
  software (including commercial) provided the font itself is not sold standalone.
- **Note**: NEXUS uses only the OFL-licensed font binary. The CSS wrapper
  (`assets/fonts/nexus_set_symbols.css`) is independently authored NEXUS code
  and is not derived from keyrune's GPL-licensed CSS source.

---

## Blockchain Toolchain (Development Only — Not Distributed)

The `blockchain/node_modules/` directory contains Hardhat and related Ethereum
development tools used to compile and deploy the NexusCardNFT smart contract.
These tools are used only during development and contract deployment; they are
**not included in NEXUS runtime distributions** and do not affect NEXUS's
license obligations.

---

## What Is NOT Included

NEXUS does **not** include or distribute:
- `assets/keyrune-master/` (full keyrune dev package with GPL-licensed CSS/LESS/SCSS)
  — this directory is a development reference only and must be excluded from
  any NEXUS software distribution or device image
- Any GPL-licensed software that would impose copyleft conditions on NEXUS

---

*Last updated: 2026-03-02*
