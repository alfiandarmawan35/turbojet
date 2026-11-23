"""Buku kuota: reserve → commit atau release, tepat satu kali per pekerjaan.

Kebenaran saat bersamaan dijamin oleh ``SELECT ... FOR UPDATE`` pada satu baris
TurboJet Quota Balance per (fitur, periode). Status ``quota_state`` di TurboJet Job
(dicek di bawah kunci baris job oleh pemanggil) menjamin commit/release tidak ganda.
"""

import frappe
from frappe import _

from turbojet.services import entitlements
from turbojet.services.entitlements import QuotaExceeded


def balance_name(feature, period):
    return f"QB-{feature}-{period}"


def _lock_balance(feature, period):
    name = balance_name(feature, period)
    rows = frappe.db.sql(
        "select name, granted, reserved, used from `tabTurboJet Quota Balance` where name=%s for update",
        name,
        as_dict=True,
    )
    if rows:
        return rows[0]
    try:
        frappe.get_doc(
            {
                "doctype": "TurboJet Quota Balance",
                "feature": feature,
                "period": period,
                "granted": entitlements.feature_limit(feature),
            }
        ).insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        pass  # dibuat oleh permintaan lain; baca ulang dengan kunci
    return frappe.db.sql(
        "select name, granted, reserved, used from `tabTurboJet Quota Balance` where name=%s for update",
        name,
        as_dict=True,
    )[0]


def _entry(balance, entry_type, amount, job=None, reason=None, request_id=None):
    frappe.get_doc(
        {
            "doctype": "TurboJet Usage Entry",
            "balance": balance,
            "entry_type": entry_type,
            "amount": amount,
            "job": job,
            "reason": reason,
            "request_id": request_id,
        }
    ).insert(ignore_permissions=True)


def reserve(feature, amount, job, request_id=None, period=None):
    period = period or entitlements.current_period()
    bal = _lock_balance(feature, period)
    available = bal.granted - bal.reserved - bal.used
    if available < amount:
        raise QuotaExceeded(_("Kuota {0} periode {1} habis").format(feature, period))
    frappe.db.sql(
        "update `tabTurboJet Quota Balance` set reserved = reserved + %s where name=%s", (amount, bal.name)
    )
    _entry(bal.name, "reserve", amount, job=job, request_id=request_id)
    return bal.name


def commit(feature, amount, job, period):
    bal = _lock_balance(feature, period)
    frappe.db.sql(
        "update `tabTurboJet Quota Balance` set reserved = reserved - %s, used = used + %s where name=%s",
        (amount, amount, bal.name),
    )
    _entry(bal.name, "commit", amount, job=job)


def release(feature, amount, job, period, reason=None):
    bal = _lock_balance(feature, period)
    frappe.db.sql(
        "update `tabTurboJet Quota Balance` set reserved = reserved - %s where name=%s", (amount, bal.name)
    )
    _entry(bal.name, "release", amount, job=job, reason=reason)


def adjust(feature, amount, reason, period=None):
    """Koreksi admin (positif = tambah kuota). Wajib alasan, tercatat di buku."""
    if not reason:
        frappe.throw(_("Alasan koreksi wajib diisi"))
    period = period or entitlements.current_period()
    bal = _lock_balance(feature, period)
    frappe.db.sql(
        "update `tabTurboJet Quota Balance` set granted = granted + %s where name=%s", (amount, bal.name)
    )
    _entry(bal.name, "adjust", amount, reason=reason)
