"""Buat aplikasi baru dari template TurboJet (Frappe + engine Python/Rust).

Sumber diambil dari git (branch template, hanya berkas ter-track), lalu semua nama
``turbojet``/``TurboJet``/``TURBOJET`` diganti: folder, nama DocType, modul Frappe, isi berkas teks.
Modul native (.pyd/.so) ikut disalin apa adanya — nama modulnya (ops_rs, split_rs) tidak berubah.

    python buat_app.py --judul "Kasir Kapal"                      # -> <monorepo>/apps/kasir_kapal
    python buat_app.py --judul "Kasir Kapal" --tujuan "C:/.../kasir_kapal"   # repo sendiri berbentuk monorepo
    python buat_app.py --judul "Kasir Kapal" --tujuan "C:/.../kasir_kapal" --datar   # tanpa monorepo
    python buat_app.py --judul "Kasir Kapal" --tujuan D:/x --repo <repo turbojet> --ref main

Dengan --tujuan, app dibuat sebagai MONOREPO: <tujuan>/apps/<nama>/ (app Frappe + engine + rust + dev),
<tujuan>/docs/ (konsep TurboJet), <tujuan>/tools/, README.md, .gitignore. Tempat paket lain (UI web, mobile,
layanan) = apps/<nama>-web, apps/<nama>-mobile, dst. Di dalam monorepo TurboJet (tanpa --tujuan) app tetap datar.

Nama app = judul huruf kecil, spasi -> ``_`` (aturan ``frappe.scrub``), mis. "Kasir Kapal" -> kasir_kapal.
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile

DEFAULT_REPO = r"C:\Users\alfian\Documents\turbojet"  # github alfiandarmawan35/turbojet
DEFAULT_REF = "main"
PREFIX = "template/"  # monorepo: template app ada di folder template/
BINARY_EXT = {".pyd", ".so", ".png", ".svg", ".ico", ".xlsx", ".pdf"}


def scrub(title):
    return re.sub(r"[^a-z0-9_]", "", title.strip().lower().replace(" ", "_").replace("-", "_"))


KEEP = "KONSEP_TURBOJET_FRAPPE_RUST"  # dokumen konsep template tetap dirujuk dengan nama aslinya


def rename_text(text, name, title):
    text = text.replace(KEEP, "\0KEEP\0")
    # nama class (TurboJetJob) tanpa spasi; teks lain ("TurboJet Job") pakai judul apa adanya
    text = re.sub(r"TurboJet(?=\w)", title.replace(" ", ""), text)
    text = text.replace("TurboJet", title).replace("TURBOJET", name.upper()).replace("turbojet", name)
    return text.replace("\0KEEP\0", KEEP)


MONO_GITIGNORE = """__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/
node_modules/
dist/
.env
*.local.txt
"""


def write_monorepo(dest, name, title, args):
    """Kerangka monorepo di sekeliling apps/<nama>. Mengembalikan jumlah berkas yang ditulis."""
    konsep = subprocess.run(
        ["git", "-C", args.repo, "show", f"{args.ref}:{KEEP}.md"], capture_output=True
    ).stdout
    files = {
        ".gitignore": MONO_GITIGNORE,
        "README.md": (
            f"# {title} (monorepo)\n\n"
            f"Dibuat dari template TurboJet (Frappe v16 + engine Python/Rust).\n\n"
            "| Folder | Isi |\n|---|---|\n"
            f"| `apps/{name}/` | app Frappe `{name}`: paket Frappe, engine Python/Rust, `rust/`, `bench/`, bench Docker `dev/`, tes |\n"
            f"| `apps/` (lainnya) | paket tambahan bila perlu: `apps/{name}-web` (UI), `apps/{name}-mobile`, layanan lain |\n"
            "| `docs/` | konsep, keputusan, brief kerja |\n"
            "| `tools/` | skrip operasional (deploy, impor, agen) |\n\n"
            "```bash\n"
            f"cd apps/{name} && python -m venv .venv && .venv/Scripts/python -m pip install pytest && .venv/Scripts/python -m pytest -q\n"
            f"bash apps/{name}/dev/bench.sh up   # bench Frappe lokal (Docker)\n"
            "```\n"
        ),
        "docs/README.md": "# docs\n\nKonsep, keputusan, dan brief kerja app ini. `KONSEP_TURBOJET_FRAPPE_RUST.md` = konsep template asal.\n",
        "tools/README.md": "# tools\n\nSkrip operasional monorepo (deploy, impor data, agen otomatis). Agen Claude Code mandiri: lihat monorepo TurboJet `tools/pi/`.\n",
    }
    n = 0
    for rel, text in files.items():
        out = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        n += 1
    if konsep:
        with open(os.path.join(dest, "docs", KEEP + ".md"), "wb") as fh:
            fh.write(konsep)
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--judul", required=True, help='judul app, mis. "Kasir Kapal"')
    ap.add_argument("--tujuan", help="folder app baru (belum ada / kosong); bawaan <repo>/apps/<nama>")
    ap.add_argument("--datar", action="store_true", help="dengan --tujuan: tanpa susunan monorepo")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--ref", default=DEFAULT_REF, help="branch/commit template")
    args = ap.parse_args(argv)

    title = args.judul.strip()
    name = scrub(title)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "turbojet":
        sys.exit(f"nama app tidak valid: {name!r}")
    dest = os.path.abspath(args.tujuan or os.path.join(args.repo, "apps", name))
    if os.path.exists(dest) and os.listdir(dest):
        sys.exit(f"folder tujuan sudah berisi: {dest}")
    mono = bool(args.tujuan) and not args.datar
    app_dir = os.path.join(dest, "apps", name) if mono else dest

    tar_bytes = subprocess.run(
        ["git", "-C", args.repo, "archive", "--format=tar", args.ref, PREFIX],
        check=True, capture_output=True,
    ).stdout
    commit = subprocess.run(
        ["git", "-C", args.repo, "rev-parse", "--short", args.ref], check=True, capture_output=True, text=True
    ).stdout.strip()

    count = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            rel = member.name[len(PREFIX):]
            rel_new = rename_text(rel, name, title)
            out = os.path.join(app_dir, *rel_new.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            data = tar.extractfile(member).read()
            ext = os.path.splitext(rel)[1].lower()
            if ext not in BINARY_EXT and not rel.endswith(".jsonl"):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    pass
                else:
                    text = rename_text(text, name, title)
                    if mono and rel == "README.md":
                        text = text.replace("](../KONSEP_TURBOJET_FRAPPE_RUST.md)", "](../../docs/KONSEP_TURBOJET_FRAPPE_RUST.md)")
                    if rel.endswith("rust-anything.json"):
                        meta = json.loads(text)
                        meta["root"] = app_dir  # path absolut sumber -> app baru
                        text = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
                    data = text.encode("utf-8")
            with open(out, "wb") as fh:
                fh.write(data)
            if member.mode & 0o111:
                os.chmod(out, 0o755)
            count += 1

    if mono:
        count += write_monorepo(dest, name, title, args)
    print(json.dumps({"app": name, "judul": title, "tujuan": dest, "app_dir": app_dir, "monorepo": mono,
                      "berkas": count, "template": f"{args.ref}@{commit}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
