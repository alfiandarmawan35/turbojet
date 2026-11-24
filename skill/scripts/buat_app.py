"""Buat aplikasi baru dari template TurboJet (Frappe + engine Python/Rust).

Sumber diambil dari git (branch template, hanya berkas ter-track), lalu semua nama
``turbojet``/``TurboJet``/``TURBOJET`` diganti: folder, nama DocType, modul Frappe, isi berkas teks.
Modul native (.pyd/.so) ikut disalin apa adanya — nama modulnya (ops_rs, split_rs) tidak berubah.

    python buat_app.py --judul "Kasir Kapal" --tujuan "C:/.../kasir_kapal"
    python buat_app.py --judul "Kasir Kapal" --tujuan D:/x --repo <repo turbojet> --ref main

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
SKIP = ("skill/",)  # skill pembuat app tidak ikut ke app turunan
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--judul", required=True, help='judul app, mis. "Kasir Kapal"')
    ap.add_argument("--tujuan", required=True, help="folder app baru (harus belum ada / kosong)")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--ref", default=DEFAULT_REF, help="branch/commit template")
    args = ap.parse_args(argv)

    title = args.judul.strip()
    name = scrub(title)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "turbojet":
        sys.exit(f"nama app tidak valid: {name!r}")
    dest = os.path.abspath(args.tujuan)
    if os.path.exists(dest) and os.listdir(dest):
        sys.exit(f"folder tujuan sudah berisi: {dest}")

    tar_bytes = subprocess.run(
        ["git", "-C", args.repo, "archive", "--format=tar", args.ref],
        check=True, capture_output=True,
    ).stdout
    commit = subprocess.run(
        ["git", "-C", args.repo, "rev-parse", "--short", args.ref], check=True, capture_output=True, text=True
    ).stdout.strip()

    count = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        for member in tar.getmembers():
            if not member.isfile() or member.name.startswith(SKIP):
                continue
            rel = member.name
            rel_new = rename_text(rel, name, title)
            out = os.path.join(dest, *rel_new.split("/"))
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
                    if rel.endswith("rust-anything.json"):
                        meta = json.loads(text)
                        meta["root"] = dest  # path absolut sumber -> app baru
                        text = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
                    data = text.encode("utf-8")
            with open(out, "wb") as fh:
                fh.write(data)
            if member.mode & 0o111:
                os.chmod(out, 0o755)
            count += 1

    print(json.dumps({"app": name, "judul": title, "tujuan": dest, "berkas": count,
                      "template": f"{args.ref}@{commit}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
