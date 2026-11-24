"""Data awal: peran, paket contoh Free/Pro, dan paket aktif."""

import frappe

ROLES = ("TurboJet Owner", "TurboJet Admin", "TurboJet Member")

PLANS = [
    {
        "plan_code": "free",
        "title": "Free",
        "price": 0,
        "period": "Monthly",
        "max_active_jobs": 1,
        "max_file_mb": 10,
        "max_rows": 100_000,
        "max_groups": 10_000,
        "limits": [{"feature": "csv_import", "limit_per_period": 5}],
    },
    {
        "plan_code": "pro",
        "title": "Pro",
        "price": 149_000,
        "period": "Monthly",
        "max_active_jobs": 3,
        "max_file_mb": 200,
        "max_rows": 5_000_000,
        "max_groups": 100_000,
        "limits": [{"feature": "csv_import", "limit_per_period": 500}],
    },
]


def after_install():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert(ignore_permissions=True)
    for plan in PLANS:
        if not frappe.db.exists("TurboJet Plan", plan["plan_code"]):
            frappe.get_doc({"doctype": "TurboJet Plan", **plan}).insert(ignore_permissions=True)
    settings = frappe.get_single("TurboJet Settings")
    if not settings.active_plan:
        settings.active_plan = "free"
        settings.entitlement_version = 1
        settings.save(ignore_permissions=True)
    frappe.db.commit()
