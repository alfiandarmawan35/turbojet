"""Siklus hidup TurboJet Job: buat + reservasi, lease, jalankan engine, terbitkan, retry, sapu.

Status: queued → leased → running → done, dengan cabang retry_wait, failed,
cancel_requested → cancelled. Nomor ``attempt`` adalah fencing token: hanya pemegang
attempt terbaru yang boleh menerbitkan hasil dan menuntaskan kuota.
"""

import json
import os
import random
import shutil
import socket
import subprocess
import sys
import time

import frappe
from frappe.utils import add_to_date, now_datetime

from turbojet.engine import contract
from turbojet.services import entitlements, quota

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_LIMIT = 3
HEARTBEAT_SECONDS = 15
LEASE_LOCK = "turbojet_job_lease"
RUNNING_STATUSES = ("leased", "running")


# ---------------------------------------------------------------- pembuatan


def create_job(operation, feature, input_file_url, options, request_id=None):
    """Dipanggil di dalam transaksi permintaan: job dan reservasi kuota tersimpan bersama."""
    settings = frappe.get_cached_doc("TurboJet Settings")
    plan = entitlements.active_plan()
    spec = {
        "contract_version": contract.CONTRACT_VERSION,
        "operation": operation,
        "options": options,
        "limits": entitlements.job_limits(plan),
    }
    period = entitlements.current_period()
    job = frappe.get_doc(
        {
            "doctype": "TurboJet Job",
            "operation": operation,
            "feature": feature,
            "status": "queued",
            "input_file": input_file_url,
            "spec_json": json.dumps(spec, ensure_ascii=False, indent=1),
            "request_id": request_id,
            "max_attempts": settings.default_max_attempts or 3,
            "quota_amount": 1,
            "quota_period": period,
        }
    ).insert(ignore_permissions=True)
    quota.reserve(feature, 1, job.name, request_id=request_id, period=period)
    frappe.db.set_value("TurboJet Job", job.name, "quota_state", "reserved", update_modified=False)
    enqueue(job.name)
    return job


def enqueue(name):
    frappe.enqueue(
        "turbojet.services.jobs.run_job",
        queue="long",
        timeout=3600,
        enqueue_after_commit=True,
        job_id=f"turbojet::{frappe.local.site}::{name}",
        deduplicate=True,
        tj_job=name,
    )


# ---------------------------------------------------------------- eksekusi


def run_job(tj_job):
    lease = _acquire_lease(tj_job)
    if lease is None:
        return
    attempt = lease["attempt"]
    try:
        outcome, out_dir = _execute(tj_job, attempt)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title=f"TurboJet {tj_job} attempt {attempt}")
        _settle(tj_job, attempt, "INTERNAL", None)
        return
    _settle(tj_job, attempt, outcome, out_dir)


def _acquire_lease(tj_job):
    """Ambil hak eksekusi secara atomik. ``None`` bila job tidak layak dijalankan sekarang."""
    if not frappe.db.sql("select get_lock(%s, 10)", LEASE_LOCK)[0][0]:
        return None  # penyapu akan mencoba lagi
    try:
        rows = frappe.db.sql(
            """select status, attempt, max_attempts, lease_until, next_attempt_at
            from `tabTurboJet Job` where name=%s for update""",
            tj_job,
            as_dict=True,
        )
        if not rows:
            frappe.db.rollback()
            return None
        row = rows[0]
        now = now_datetime()
        fresh = row.status == "queued" or (
            row.status == "retry_wait" and (not row.next_attempt_at or row.next_attempt_at <= now)
        )
        expired = row.status in RUNNING_STATUSES and row.lease_until and row.lease_until < now
        if not (fresh or expired):
            frappe.db.rollback()
            return None
        if fresh and entitlements.active_job_count() >= entitlements.active_plan().max_active_jobs:
            frappe.db.rollback()
            return None  # batas pekerjaan aktif per site; tetap antre
        attempt = (row.attempt or 0) + 1
        if attempt > (row.max_attempts or 3):
            _fail(tj_job, "MAX_ATTEMPTS", "percobaan habis")
            frappe.db.commit()
            return None
        frappe.db.sql(
            """update `tabTurboJet Job` set status='leased', attempt=%s, lease_owner=%s,
            lease_until=%s, error_code=null, error_message=null where name=%s""",
            (attempt, _worker_id(), _lease_until(), tj_job),
        )
        frappe.db.commit()
        return {"attempt": attempt}
    finally:
        frappe.db.sql("select release_lock(%s)", LEASE_LOCK)


def _execute(tj_job, attempt):
    job = frappe.get_doc("TurboJet Job", tj_job)
    attempt_dir = frappe.get_site_path("private", "turbojet_work", tj_job, f"attempt-{attempt}")
    os.makedirs(attempt_dir, exist_ok=True)
    spec_path = os.path.join(attempt_dir, "job.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        fh.write(job.spec_json)
    out_dir = os.path.join(attempt_dir, "out")
    input_path = frappe.get_doc("File", {"file_url": job.input_file}).get_full_path()
    max_seconds = json.loads(job.spec_json).get("limits", {}).get(
        "max_seconds", contract.DEFAULT_LIMITS["max_seconds"]
    )

    frappe.db.sql(
        "update `tabTurboJet Job` set status='running' where name=%s and attempt=%s", (tj_job, attempt)
    )
    frappe.db.commit()

    cmd = [sys.executable, "-m", "turbojet.engine", "run", "--spec", spec_path, "--input", input_path, "--out", out_dir]
    with open(os.path.join(attempt_dir, "stderr.log"), "wb") as err:
        proc = subprocess.Popen(
            cmd,
            cwd=attempt_dir,
            stdout=subprocess.DEVNULL,
            stderr=err,
            env=_engine_env(),
            preexec_fn=_rlimit_fn() if os.name == "posix" else None,  # noqa: PLW1509
        )
        deadline = time.monotonic() + max_seconds + 30
        while True:
            try:
                return proc.wait(timeout=HEARTBEAT_SECONDS), out_dir
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() > deadline:
                _stop(proc, kill=True)
                return "TIMEOUT", out_dir
            state = _heartbeat(tj_job, attempt, out_dir, job.owner)
            if state == "lost":
                _stop(proc, kill=True)
                return "LOST", out_dir
            if state == "cancel":
                _stop(proc, kill=False)
                return "CANCELLED", out_dir


def _heartbeat(tj_job, attempt, out_dir, owner):
    frappe.db.sql(
        """update `tabTurboJet Job` set lease_until=%s
        where name=%s and attempt=%s and status in ('running', 'cancel_requested')""",
        (_lease_until(), tj_job, attempt),
    )
    rows_read = _read_progress(out_dir)
    if rows_read is not None:
        frappe.db.sql(
            "update `tabTurboJet Job` set rows_read=%s where name=%s and attempt=%s", (rows_read, tj_job, attempt)
        )
    row = frappe.db.get_value("TurboJet Job", tj_job, ["attempt", "status"], as_dict=True)
    frappe.db.commit()
    if rows_read is not None:
        frappe.publish_realtime(
            "turbojet_job_progress", {"job": tj_job, "rows_read": rows_read}, user=owner, after_commit=False
        )
    if row.attempt != attempt:
        return "lost"
    if row.status == "cancel_requested":
        return "cancel"
    return "ok"


# ---------------------------------------------------------------- penyelesaian


def _settle(tj_job, attempt, outcome, out_dir):
    rows = frappe.db.sql(
        "select attempt, status from `tabTurboJet Job` where name=%s for update", tj_job, as_dict=True
    )
    if not rows or rows[0].attempt != attempt:
        frappe.db.rollback()  # worker basi: percobaan lebih baru sudah memegang job
        return
    status = rows[0].status
    if outcome == "CANCELLED" or status == "cancel_requested":
        _cancel(tj_job)
    elif outcome == EXIT_OK:
        manifest = contract.verify_manifest(out_dir)
        if manifest is None:
            _retry_or_fail(tj_job, attempt, "BAD_MANIFEST", "manifest hilang atau checksum tidak cocok")
        else:
            _publish(tj_job, out_dir, manifest)
    elif outcome in (EXIT_INPUT, EXIT_LIMIT):
        failure = _read_json(os.path.join(out_dir, contract.FAILURE_FILE)) or {}
        _fail(tj_job, failure.get("code", "INVALID_INPUT"), failure.get("message", ""))
    else:
        failure = (_read_json(os.path.join(out_dir, contract.FAILURE_FILE)) if out_dir else None) or {}
        _retry_or_fail(tj_job, attempt, failure.get("code", str(outcome)), failure.get("message", ""))
    frappe.db.commit()
    if out_dir and outcome == EXIT_OK:
        shutil.rmtree(os.path.dirname(out_dir), ignore_errors=True)


def _publish(tj_job, out_dir, manifest):
    result = _read_json(os.path.join(out_dir, contract.RESULT_FILE))
    output_url = _attach(tj_job, out_dir, contract.OUTPUT_FILE, f"{tj_job}-hasil.csv")
    errors_url = _attach(tj_job, out_dir, contract.ERRORS_FILE, f"{tj_job}-baris-ditolak.csv")
    frappe.db.set_value(
        "TurboJet Job",
        tj_job,
        {
            "status": "done",
            "output_file": output_url,
            "errors_file": errors_url,
            "result_json": json.dumps(result, ensure_ascii=False, indent=1),
            "rows_read": result["rows_read"],
            "rows_valid": result["rows_valid"],
            "rows_rejected": result["rows_rejected"],
            "engine_path": manifest["engine_path"],
            "engine_version": manifest["engine_version"],
            "lease_until": None,
        },
    )
    _settle_quota(tj_job, "commit")
    frappe.publish_realtime("turbojet_job_done", {"job": tj_job}, user=frappe.db.get_value("TurboJet Job", tj_job, "owner"))


def _attach(tj_job, out_dir, name, file_name):
    with open(os.path.join(out_dir, name), "rb") as fh:
        content = fh.read()
    doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "is_private": 1,
            "attached_to_doctype": "TurboJet Job",
            "attached_to_name": tj_job,
            "content": content,
        }
    ).insert(ignore_permissions=True)
    return doc.file_url


def _retry_or_fail(tj_job, attempt, code, message):
    max_attempts = frappe.db.get_value("TurboJet Job", tj_job, "max_attempts") or 3
    if attempt >= max_attempts:
        _fail(tj_job, code, message)
        return
    delay = min(300, 10 * 2**attempt) + random.uniform(0, 5)
    frappe.db.set_value(
        "TurboJet Job",
        tj_job,
        {
            "status": "retry_wait",
            "next_attempt_at": add_to_date(now_datetime(), seconds=delay),
            "lease_until": None,
            "error_code": code,
            "error_message": (message or "")[:1000],
        },
    )


def _fail(tj_job, code, message):
    frappe.db.set_value(
        "TurboJet Job",
        tj_job,
        {"status": "failed", "lease_until": None, "error_code": code, "error_message": (message or "")[:1000]},
    )
    _settle_quota(tj_job, "release", reason=code)


def _cancel(tj_job):
    frappe.db.set_value("TurboJet Job", tj_job, {"status": "cancelled", "lease_until": None})
    _settle_quota(tj_job, "release", reason="CANCELLED")


def _settle_quota(tj_job, action, reason=None):
    """Commit atau release tepat satu kali; pemanggil sudah memegang kunci baris job."""
    job = frappe.db.get_value(
        "TurboJet Job", tj_job, ["feature", "quota_state", "quota_amount", "quota_period"], as_dict=True
    )
    if job.quota_state != "reserved":
        return
    if action == "commit":
        quota.commit(job.feature, job.quota_amount, tj_job, job.quota_period)
        state = "committed"
    else:
        quota.release(job.feature, job.quota_amount, tj_job, job.quota_period, reason=reason)
        state = "released"
    frappe.db.set_value("TurboJet Job", tj_job, "quota_state", state, update_modified=False)


def request_cancel(tj_job):
    rows = frappe.db.sql("select status from `tabTurboJet Job` where name=%s for update", tj_job, as_dict=True)
    status = rows[0].status
    if status in ("queued", "retry_wait"):
        _cancel(tj_job)
    elif status in RUNNING_STATUSES:
        frappe.db.set_value("TurboJet Job", tj_job, "status", "cancel_requested")
    else:
        frappe.throw(frappe._("Pekerjaan berstatus {0} tidak bisa dibatalkan").format(status))


# ---------------------------------------------------------------- penyapu (scheduler tiap menit)


def sweep():
    now = now_datetime()
    names = set(
        frappe.get_all(
            "TurboJet Job",
            filters={"status": "queued", "modified": ("<", add_to_date(now, minutes=-2))},
            pluck="name",
        )
    )
    names |= set(
        frappe.get_all("TurboJet Job", filters={"status": "retry_wait", "next_attempt_at": ("<=", now)}, pluck="name")
    )
    names |= set(
        frappe.get_all(
            "TurboJet Job", filters={"status": ("in", RUNNING_STATUSES), "lease_until": ("<", now)}, pluck="name"
        )
    )
    for name in frappe.get_all(
        "TurboJet Job", filters={"status": "cancel_requested", "lease_until": ("<", now)}, pluck="name"
    ):
        frappe.db.sql("select name from `tabTurboJet Job` where name=%s for update", name)
        _cancel(name)
    for name in names:
        enqueue(name)
    frappe.db.commit()


# ---------------------------------------------------------------- utilitas


def _lease_until():
    seconds = frappe.db.get_single_value("TurboJet Settings", "lease_seconds") or 120
    return add_to_date(now_datetime(), seconds=seconds)


def _worker_id():
    return f"{socket.gethostname()}:{os.getpid()}"


def _engine_env():
    """Lingkungan subprocess. Saklar rust-anything bisa disetel per site lewat site_config:
    ``"turbojet_engine_env": {"RUST_ANYTHING_MODE": "shadow"}``."""
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (frappe.conf.get("turbojet_engine_env") or {}).items()})
    return env


def _rlimit_fn():
    """Batas memori engine (Linux). Nilai dihitung di induk; anak hanya memanggil setrlimit."""
    import resource

    mem = int(frappe.conf.get("turbojet_engine_max_memory_mb") or 1024) * 1024 * 1024

    def apply():
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

    return apply


def _stop(proc, kill):
    if kill:
        proc.kill()
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _read_progress(out_dir):
    data = _read_json(os.path.join(out_dir, contract.PROGRESS_FILE))
    return data.get("rows_read") if data else None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
