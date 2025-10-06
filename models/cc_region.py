# -*- coding: utf-8 -*-
from odoo import api, fields, models

class CcRegion(models.Model):
    _name = "cc.region"
    _description = "Service Region (Tuman)"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code")
    note = fields.Text(string="Note")

    country_id = fields.Many2one(
        "res.country",
        string="Country",
        required=True,
        default=lambda self: self.env.ref("base.uz", raise_if_not_found=False) or self.env.user.company_id.country_id,
        ondelete="restrict",
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State (Viloyat)",
        domain="[('country_id', '=', country_id)]",
        ondelete="restrict",
    )

    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-set country from state when creating records"""
        for vals in vals_list:
            if vals.get('state_id') and not vals.get('country_id'):
                state = self.env['res.country.state'].browse(vals['state_id'])
                if state.country_id:
                    vals['country_id'] = state.country_id.id
        return super().create(vals_list)

    def write(self, vals):
        """Auto-set country from state when updating records"""
        if vals.get('state_id') and not vals.get('country_id'):
            state = self.env['res.country.state'].browse(vals['state_id'])
            if state.country_id:
                vals['country_id'] = state.country_id.id
        
        # Reset state if country changes and doesn't match
        if vals.get('country_id'):
            for record in self:
                if record.state_id and record.state_id.country_id.id != vals['country_id']:
                    vals['state_id'] = False
        
        return super().write(vals)

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Reset state when country changes in form view"""
        if self.state_id and self.state_id.country_id != self.country_id:
            self.state_id = False

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Auto-set country from state in form view"""
        if self.state_id and self.state_id.country_id:
            self.country_id = self.state_id.country_id