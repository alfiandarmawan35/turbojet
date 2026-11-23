"""Hak paket. Satu-satunya tempat portal, API, dan generator fitur memeriksa akses."""

import frappe
from frappe import _
from frappe.utils import now_datetime

ACTIVE_STATUSES = ("leased", "running", "publishing", "cancel_requested")


class QuotaExceeded(frappe.ValidationError):
    pass


def current_period():
    return now_datetime().strftime("%Y-%m")


def active_plan():
    plan_code = frappe.db.get_single_value("TurboJet Settings", "active_plan") or "free"
    return frappe.get_cached_doc("TurboJet Plan", plan_code)


def feature_limit(feature, plan=None):
    plan = plan or active_plan()
    for row in plan.limits:
        if row.feature == feature:
            return row.limit_per_period
    return 0


def job_limits(plan=None):
    """Batas yang diteruskan ke engine lewat ``job.json``."""
    plan = plan or active_plan()
    return {"max_rows": plan.max_rows, "max_groups": plan.max_groups}


def check(feature, amount=1, file_bytes=None):
    """Lempar exception bila fitur tidak ada di paket atau berkas terlalu besar.

    Sisa kuota tidak dicek di sini: itu tugas ``quota.reserve`` di bawah kunci baris.
    """
    plan = active_plan()
    if feature_limit(feature, plan) <= 0:
        raise QuotaExceeded(_("Fitur {0} tidak termasuk paket {1}").format(feature, plan.title))
    if file_bytes is not None and file_bytes > plan.max_file_mb * 1024 * 1024:
        frappe.throw(_("Berkas melebihi {0} MB untuk paket {1}").format(plan.max_file_mb, plan.title))
    return plan


def active_job_count():
    return frappe.db.count("TurboJet Job", {"status": ("in", ACTIVE_STATUSES)})
