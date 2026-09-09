# Vendored Everything binaries

FileCheck pins the official portable binaries required by its Windows packages so release builds do not depend on live upstream downloads.

- Everything: 1.4.1.1032 portable, x64 and x86
- ES: 1.1.0.37, x64 and x86
- Source: voidtools official downloads / voidtools ES GitHub releases
- `SHA256SUMS.txt` records the exact committed executable hashes.

Build workflows must verify these hashes and PE architecture before packaging.
