from frappe.model.document import Document


class TurboJetIdempotencyKey(Document):
    def autoname(self):
        from turbojet.services.idempotency import key_name

        self.name = key_name(self.user, self.operation, self.client_key)
