from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DSAConf(models.Model):
    _name = 'dsa.conf'
    _description = 'DSA Configurations, includes: DSA Rates and Deductions'
    _rec_name = 'display_name'

    job_id = fields.Many2one(
        'hr.job',
        string='Designation',
        required=True,
        domain=[('active', '=', True)]
    )

    dsa_rate = fields.Float(
        string='DSA Rate',
        required=True
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

    @api.constrains('job_id', 'active')
    def _check_single_active_configuration(self):
        for rec in self:
            if not rec.active or not rec.job_id:
                continue

            duplicate = self.search([
                ('id', '!=', rec.id),
                ('job_id', '=', rec.job_id.id),
                ('active', '=', True),
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    'An active DSA Configuration already exists for designation "%s". '
                    'Please archive the existing configuration before creating another.'
                    % rec.job_id.name
                )
    @api.depends('job_id', 'dsa_rate')
    def _compute_display_name(self):
        for rec in self:
            if rec.job_id and rec.dsa_rate:
                rec.display_name = '%s: %.2f' % (rec.job_id.name, rec.dsa_rate)
            elif rec.job_id:
                rec.display_name = rec.job_id.name
            else:
                rec.display_name = ''