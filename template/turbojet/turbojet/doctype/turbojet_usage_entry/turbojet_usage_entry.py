import frappe
from frappe.model.document import Document


class TurboJetUsageEntry(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(frappe._("Usage Entry tidak boleh diubah; buat entri adjust baru."))

    def on_trash(self):
        frappe.throw(frappe._("Usage Entry tidak boleh dihapus."))
