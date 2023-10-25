"""Main controller"""

from odoo import http
from odoo.addons.web import controllers


class Session(controllers.main.Session):
    """Session controller"""

    @http.route()
    def logout(self, *args, **kwargs):
        """Logout"""
        uid = http.request.session.uid
        if uid is not None:
            http.request.env["print.printer"].with_user(uid).clear_ephemeral()
        return super().logout(*args, **kwargs)


class PrintAuditLogAction(controllers.main.Action):
    @http.route()
    def load(self, action_id, additional_context=None):
        """
        Extend load to log a note in the audit trail
        of the affected records when a report is printed.
        Only affects models who have the class attribute AUDIT_LOG_PRINTING set to True.

        NB: If setting this class attribute on models,
        ensure the model has `_inherit = ["mail.thread"]`
        """
        IrModel = http.request.env["ir.model"]
        res = super().load(action_id, additional_context=additional_context)
        if res.get("binding_type") == "report":
            binding_model = res.get("binding_model_id")
            if binding_model:
                # `binding_model`` is a tuple of the model id and display name
                # `.model` gives us the models _name which we can pass into it to get an emptyset.
                model = http.request.env[IrModel.browse(binding_model[0]).model]
                if hasattr(model, "AUDIT_LOG_PRINTING") and model.AUDIT_LOG_PRINTING:
                    for record in model.browse(http.request.env.context.get("active_ids")):
                        record.message_post(
                            body=f"Report [{res.get('name')}] Printed from the Desktop."
                        )
        return res
