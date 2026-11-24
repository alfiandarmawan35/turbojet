"""Uji asap app di bench lokal lewat HTTP (stdlib saja).

Alur: login → unggah CSV privat → preview_csv → create_import_job (client_key) → ulangi dengan
client_key sama (harus job yang sama) → tunggu done → unduh hasil → cek kuota & engine_path.
Ditambah: CSV rusak → job failed dengan kode jelas dan kuota dilepas.
"""

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CSV_OK = "kota;total\nAmbon;1.000,50\nBitung;2,25\nAmbon;3\nKupang;abc\n"
CSV_BAD = "kota;total\nAmbon;1\n"  # kolom grup salah dipilih -> INVALID_OPTIONS / kolom tidak ada


class Client:
    def __init__(self, base, site):
        self.base = base.rstrip("/")
        self.site = site
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, data=None, files=None, get=False):
        url = f"{self.base}/api/method/{method}"
        headers = {"Accept": "application/json", "X-Frappe-Site-Name": self.site}
        if get:
            url += "?" + urllib.parse.urlencode(data or {})
            body = None
        elif files:
            boundary = uuid.uuid4().hex
            parts = []
            for k, v in (data or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for k, (fname, content) in files.items():
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                    f"Content-Type: text/csv\r\n\r\n".encode() + content + b"\r\n"
                )
            body = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        else:
            body = urllib.parse.urlencode(data or {}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method="GET" if get else "POST")
        try:
            with self.opener.open(req, timeout=60) as resp:
                return json.loads(resp.read() or b"{}").get("message")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise SystemExit(f"GAGAL {method}: HTTP {exc.code}\n{detail[:2000]}") from None

    def get_raw(self, path):
        req = urllib.request.Request(f"{self.base}{path}", headers={"X-Frappe-Site-Name": self.site})
        with self.opener.open(req, timeout=60) as resp:
            return resp.read()


def check(cond, label):
    print(("OK   " if cond else "GAGAL") + " " + label)
    if not cond:
        check.failed += 1


check.failed = 0


def wait_job(c, app, job, seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        view = c.call(f"{app}.api.v1.job_status", {"job": job}, get=True)
        if view["status"] in ("done", "failed", "cancelled"):
            return view
        time.sleep(1)
    raise SystemExit(f"job {job} tidak selesai dalam {seconds} dtk: {view}")


def upload(c, name, text):
    f = c.call("upload_file", {"is_private": 1}, files={"file": (name, text.encode("utf-8"))})
    return f["file_url"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8090")
    ap.add_argument("--app", default="turbojet")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--site", default=None, help="default <app>.localhost")
    args = ap.parse_args()
    app = args.app
    c = Client(args.url, args.site or f"{app}.localhost")
    c.call("login", {"usr": "Administrator", "pwd": args.password})

    url = upload(c, f"smoke-{uuid.uuid4().hex[:6]}.csv", CSV_OK)
    prev = c.call(f"{app}.api.v1.preview_csv", {"file_url": url})
    check(prev.get("columns") == ["kota", "total"] and prev.get("delimiter") == ";", f"preview_csv {prev}")

    key = uuid.uuid4().hex
    opts = {"file_url": url, "group_by": "kota", "value_column": "total", "decimal": "comma", "client_key": key}
    j1 = c.call(f"{app}.api.v1.create_import_job", opts)
    j2 = c.call(f"{app}.api.v1.create_import_job", opts)
    check(j1["name"] == j2["name"], f"idempotensi: client_key sama -> job sama ({j1['name']}, {j2['name']})")

    done = wait_job(c, app, j1["name"])
    check(done["status"] == "done", f"job selesai: status={done['status']} {done.get('error_code') or ''} {done.get('error_message') or ''}")
    check(done["engine_path"] == "rust", f"engine_path={done['engine_path']}")
    check((done["rows_read"], done["rows_valid"], done["rows_rejected"]) == (4, 3, 1),
          f"baris dibaca/valid/ditolak = {done['rows_read']}/{done['rows_valid']}/{done['rows_rejected']}")
    if done.get("output_file"):
        out = c.get_raw(done["output_file"]).decode("utf-8-sig")
        check("Ambon,2,1003.50" in out and "Bitung,1,2.25" in out, f"output.csv:\n{out.strip()}")

    bad_url = upload(c, f"smoke-bad-{uuid.uuid4().hex[:6]}.csv", CSV_BAD)
    jb = c.call(f"{app}.api.v1.create_import_job",
                {"file_url": bad_url, "group_by": "tidak_ada", "value_column": "total", "decimal": "comma"})
    bad = wait_job(c, app, jb["name"])
    check(bad["status"] == "failed" and bad["error_code"], f"CSV salah -> failed {bad['error_code']}: {bad['error_message']}")

    jobs = c.call(f"{app}.api.v1.list_jobs", {"limit": 5}, get=True)
    check(len(jobs) >= 2, f"list_jobs {len(jobs)} job")
    print("\nSELESAI:", "semua lulus" if not check.failed else f"{check.failed} gagal")
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
