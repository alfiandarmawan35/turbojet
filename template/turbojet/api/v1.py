"""API publik v1. Portal dan klien API memakai fungsi yang sama.

    POST /api/method/turbojet.api.v1.preview_csv
    POST /api/method/turbojet.api.v1.create_import_job
    GET  /api/method/turbojet.api.v1.job_status?job=TJ-2026-00001
    GET  /api/method/turbojet.api.v1.list_jobs
    POST /api/method/turbojet.api.v1.cancel_job
"""

import json

import frappe
from frappe import _

from turbojet.engine.csvio import detect_encoding
from turbojet.engine.ops.preview import preview
from turbojet.services import entitlements, idempotency, jobs

ROLES = ("TurboJet Owner", "TurboJet Admin", "TurboJet Member", "System Manager")
ADMIN_ROLES = ("TurboJet Owner", "TurboJet Admin", "System Manager")
JOB_FIELDS = (
    "name",
    "operation",
    "status",
    "attempt",
    "rows_read",
    "rows_valid",
    "rows_rejected",
    "output_file",
    "errors_file",
    "error_code",
    "error_message",
    "engine_path",
    "creation",
    "modified",
)


def _own_private_file(file_url):
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        frappe.throw(_("Berkas tidak ditemukan"), frappe.DoesNotExistError)
    doc = frappe.get_doc("File", name)
    if not doc.is_private or doc.owner != frappe.session.user:
        frappe.throw(_("Berkas tidak ditemukan"), frappe.DoesNotExistError)
    return doc


@frappe.whitelist(methods=["POST"])
def preview_csv(file_url, rows=20):
    frappe.only_for(ROLES)
    doc = _own_private_file(file_url)
    path = doc.get_full_path()
    with open(path, encoding=detect_encoding(path), errors="replace", newline="") as fh:
        head = fh.read(64 * 1024)
    return json.loads(preview(head, min(int(rows), 100)))


@frappe.whitelist(methods=["POST"])
def create_import_job(file_url, group_by, value_column, decimal="comma", delimiter=None, client_key=None):
    frappe.only_for(ROLES)
    doc = _own_private_file(file_url)
    options = {"group_by": group_by, "value_column": value_column, "decimal": decimal}
    if delimiter:
        options["delimiter"] = delimiter
    if client_key:
        prior = idempotency.claim("csv_import", client_key, {"file_url": file_url, **options})
        if prior:
            return _job_view(prior[1])
    entitlements.check("csv_import", file_bytes=doc.file_size)
    job = jobs.create_job("group_sum", "csv_import", file_url, options, request_id=client_key)
    if client_key:
        idempotency.complete("csv_import", client_key, "TurboJet Job", job.name)
    return _job_view(job.name)


@frappe.whitelist()
def job_status(job):
    frappe.get_doc("TurboJet Job", job).check_permission("read")
    return _job_view(job)


@frappe.whitelist()
def list_jobs(limit=20):
    frappe.only_for(ROLES)
    return frappe.get_list(
        "TurboJet Job", fields=list(JOB_FIELDS), order_by="creation desc", limit_page_length=min(int(limit), 100)
    )


@frappe.whitelist(methods=["POST"])
def cancel_job(job):
    doc = frappe.get_doc("TurboJet Job", job)
    doc.check_permission("read")
    if doc.owner != frappe.session.user and not set(ADMIN_ROLES) & set(frappe.get_roles()):
        frappe.throw(_("Tidak boleh membatalkan pekerjaan orang lain"), frappe.PermissionError)
    jobs.request_cancel(job)
    return _job_view(job)


def _job_view(name):
    return frappe.db.get_value("TurboJet Job", name, list(JOB_FIELDS), as_dict=True)
