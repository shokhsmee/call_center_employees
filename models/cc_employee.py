# -*- coding: utf-8 -*-
import logging, requests
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Try these keys in order for your bot token.
PARAM_BOT_TOKEN_KEYS = (
    "warranty_bot.bot_token",  # your current system param key
    "tg.bot_token",
    "warranty.bot_token",
)

class CcEmployee(models.Model):
    _name = "cc.employee"
    _description = "Hodim"
    _order = "name"
    _rec_name = "name"

    image_1920 = fields.Image(string="Rasm", max_width=1920, max_height=1920)
    name = fields.Char(required=True, string="F.I.O")
    user_id = fields.Many2one("res.users", string="Odoo User", ondelete="set null")

    is_usta = fields.Boolean(string="Usta (Servis)")
    
    # NEW FIELD: Usta Status - controls bot access
    usta_status = fields.Boolean(
        string="Usta Status (Bot faol)", 
        default=False,
        help="Agar False bo'lsa, usta botda faqat cheklangan xabarni ko'radi"
    )
    
    phone = fields.Char(string="Telefon")
    email = fields.Char(string="Email")

    service_region_ids = fields.Many2many(
        "cc.region", "cc_employee_region_rel", "employee_id", "region_id",
        string="Ish hududi",
    )
    state_ids = fields.Many2many(
        "res.country.state", "cc_employee_state_rel", "employee_id", "state_id",
        string="Viloyatlar (ixtiyoriy filtrlash)"
    )

    note = fields.Text(string="Izoh")
    active = fields.Boolean(default=True, index=True)

    # Saved by the bot during registration
    tg_user_id = fields.Char(string="TG User ID")
    tg_chat_id = fields.Char(string="TG Chat ID")

    # ----- Telegram helper -----
    def _tg_send(self, text: str):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ""
        for k in PARAM_BOT_TOKEN_KEYS:
            v = (ICP.get_param(k) or "").strip()
            if v:
                token = v
                break
        if not token:
            _logger.info("Telegram token not configured. Tried keys: %s", ", ".join(PARAM_BOT_TOKEN_KEYS))
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for rec in self:
            chat = (rec.tg_chat_id or "").strip()
            if not chat:
                continue
            try:
                requests.post(
                    url,
                    json={"chat_id": chat, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
            except Exception as e:
                _logger.exception("Telegram notify failed: %s", e)

    # ----- Group sync + Activation notification -----
    def write(self, vals):
        was_active = {r.id: bool(r.active) for r in self}
        was_usta_status = {r.id: bool(r.usta_status) for r in self}
        
        res = super().write(vals)

        # keep your group sync
        group = self.env.ref("call_center_employees.group_service_ustalar", raise_if_not_found=False)
        if group:
            for rec in self:
                if not rec.user_id:
                    continue
                if "is_usta" in vals:
                    if vals.get("is_usta"):
                        rec.user_id.groups_id = [(4, group.id)]
                    else:
                        rec.user_id.groups_id = [(3, group.id)]
                else:
                    if rec.is_usta and group not in rec.user_id.groups_id:
                        rec.user_id.groups_id = [(4, group.id)]
                    if not rec.is_usta and group in rec.user_id.groups_id:
                        rec.user_id.groups_id = [(3, group.id)]

        # notify those who just became active
        if "active" in vals and vals.get("active") is True:
            became_active = self.filtered(lambda r: not was_active.get(r.id) and r.active)
            if became_active:
                became_active._tg_send(_("Siz faollashtirildingiz! Bot funksiyalari endi ochiq. ✅"))
        
        # NEW: notify those whose usta_status changed
        if "usta_status" in vals:
            if vals.get("usta_status") is True:
                became_enabled = self.filtered(lambda r: not was_usta_status.get(r.id) and r.usta_status)
                if became_enabled:
                    became_enabled._tg_send(_("✅ Usta statusingiz faollashtirildi! Bot funksiyalari ochiq."))
            elif vals.get("usta_status") is False:
                became_disabled = self.filtered(lambda r: was_usta_status.get(r.id) and not r.usta_status)
                if became_disabled:
                    became_disabled._tg_send(_("⚠️ Usta statusingiz to'xtatildi. Iltimos, administrator bilan bog'laning."))
        
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        group = self.env.ref("call_center_employees.group_service_ustalar", raise_if_not_found=False)
        if group:
            for rec in records:
                if rec.user_id:
                    if rec.is_usta:
                        rec.user_id.groups_id = [(4, group.id)]
                    else:
                        rec.user_id.groups_id = [(3, group.id)]
        return records

    # 🔴 CHANGED: only enforce regions when ACTIVE
    @api.constrains('is_usta', 'service_region_ids', 'active')
    def _check_usta_regions(self):
        for rec in self:
            if rec.is_usta and rec.active and not rec.service_region_ids:
                raise ValidationError("Usta uchun kamida bitta ish hududi (tuman) tanlang.")