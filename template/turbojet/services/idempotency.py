"""Kunci idempotensi per (pengguna, operasi, kunci klien).

Kunci disisipkan PALING AWAL dalam transaksi. Permintaan kembar dengan kunci yang sama
tertahan di primary key sampai transaksi pertama selesai, lalu mendapat DuplicateEntryError
dan membaca hasil yang sudah ada.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

TTL_HOURS = 24


class IdempotencyConflict(frappe.ValidationError):
    pass


def key_name(user, operation, client_key):
    raw = f"{user}\x1f{operation}\x1f{client_key}".encode()
    return hashlib.sha256(raw).hexdigest()[:40]


def input_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def claim(operation, client_key, payload):
    """Kembalikan ``None`` bila kunci baru (dan sudah diklaim), atau ``(doctype, name)`` hasil lama."""
    user = frappe.session.user
    digest = input_hash(payload)
    name = key_name(user, operation, client_key)
    existing = frappe.db.get_value(
        "TurboJet Idempotency Key", name, ["input_hash", "result_doctype", "result_name"], as_dict=True
    )
    if existing is None:
        try:
            frappe.get_doc(
                {
                    "doctype": "TurboJet Idempotency Key",
                    "user": user,
                    "operation": operation,
                    "client_key": client_key,
                    "input_hash": digest,
                    "expires_at": add_to_date(now_datetime(), hours=TTL_HOURS),
                }
            ).insert(ignore_permissions=True)
            return None
        except frappe.DuplicateEntryError:
            existing = frappe.db.get_value(
                "TurboJet Idempotency Key", name, ["input_hash", "result_doctype", "result_name"], as_dict=True
            )
    if existing.input_hash != digest:
        raise IdempotencyConflict(_("IDEMPOTENCY_CONFLICT: kunci yang sama dipakai untuk input berbeda"))
    if not existing.result_name:
        raise IdempotencyConflict(_("IDEMPOTENCY_IN_PROGRESS: permintaan yang sama sedang diproses"))
    return existing.result_doctype, existing.result_name


def complete(operation, client_key, result_doctype, result_name):
    name = key_name(frappe.session.user, operation, client_key)
    frappe.db.set_value(
        "TurboJet Idempotency Key", name, {"result_doctype": result_doctype, "result_name": result_name}
    )


def purge_expired():
    frappe.db.delete("TurboJet Idempotency Key", {"expires_at": ("<", now_datetime())})
