"""Build reproducible unsigned Firefox and unpacked Chromium installation artifacts."""

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL = ["http://localhost/*", "http://127.0.0.1/*", "https://localhost/*", "https://127.0.0.1/*"]


def build():
    base = {
        "manifest_version": 3,
        "name": "NBA Terminal ESPN Session",
        "version": "1.0.0",
        "description": "Consented local-only reuse of your ESPN login. No passwords or roster writes.",
        "permissions": ["storage", "activeTab"],
        "optional_permissions": ["cookies"],
        "host_permissions": LOCAL,
        "optional_host_permissions": ["https://*.espn.com/*"],
        "action": {"default_popup": "popup.html"},
        "content_scripts": [{"matches": LOCAL, "js": ["content.js"], "run_at": "document_idle"}],
    }
    for target in ("firefox", "chromium"):
        manifest = dict(base)
        if target == "firefox":
            manifest["background"] = {"scripts": ["background.js"]}
            manifest["browser_specific_settings"] = {
                "gecko": {"id": "espn-session@nba-terminal.local", "strict_min_version": "128.0"}
            }
        else:
            manifest["background"] = {"service_worker": "background.js"}
            manifest["minimum_chrome_version"] = "120"
        files = {p.name: p.read_bytes() for p in sorted((ROOT / "src").iterdir()) if p.is_file()}
        files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        with zipfile.ZipFile(ROOT / "dist" / f"{target}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, content)
    (ROOT / "dist" / "instructions.md").write_bytes((ROOT / "README.md").read_bytes())


if __name__ == "__main__":
    build()
