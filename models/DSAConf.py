from docutils.parsers import null

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DSAConf(models.Model):
    _name = 'dsa.conf'
    _description = 'DSA Configurations, includes: DSA Rates and Deductions'
    _rec_name = 'display_name'

    year = fields.Char(
        string='Year',
        required=True,
    )

    dsa_rate = fields.Float(
        string='DSA Rate',
        required=True
    )

    issue_date = fields.Date(
        string='Date of Issue',
        required=True,
    )

    deduction_if_lunch_provided = fields.Float(
        string='Deduction % if Lunch Provided',
        required=True,
        default=0
    )

    deduction_if_hotel_provided = fields.Float(
        string='Deduction % if Hotel Provided',
        required=True,
        default=0
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.constrains('active')
    def _check_single_active_configuration(self):
        for rec in self:
            if not rec.active:
                continue

            duplicate = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
            ], limit=1)

            if duplicate:
                raise ValidationError(

                    'Please archive the existing configuration before creating another.'

                )

    @api.depends('dsa_rate', 'issue_date')
    def _compute_display_name(self):
        for rec in self:
            parts = []

            if rec.issue_date:
                parts.append(f"Revision: [{rec.issue_date.strftime('%d %b %Y')}]")

            if rec.dsa_rate:
                parts.append(f"Rate: [{rec.dsa_rate:.2f}]")

            rec.display_name = " ".join(parts)