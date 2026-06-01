# models/dsa_details.py

from odoo import fields, models
from datetime import datetime


class DSADetails(models.Model):
    _name = 'dsa.details'
    _description = (
        'DSA Details, includes employee name, travel dates '
        'and necessary information to calculate DSA Amount'
    )

    def _get_current_month(self):
        return str(datetime.now().month)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Designation',
        related='employee_id.job_id',
        store=True,
        readonly=True
    )

    po_number = fields.Char(
        string='PO Number',
        required=True
    )

    travel_from = fields.Date(
        string='Travel Start Date',
        required=True
    )

    travel_to = fields.Date(
        string='Travel End Date',
        required=True
    )

    travel_location_from = fields.Char(
        string='Travel From (Location)'
    )

    travel_location_to = fields.Char(
        string='Travel To (Location)'
    )

    travel_purpose = fields.Text(
        string='Travel Purpose'
    )

    month = fields.Selection(
        [
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string='Month',
        required=True,
        default=lambda self: str(datetime.now().month)
    )

    line_ids = fields.One2many(
        'dsa.details.line',
        'dsa_id',
        string='Daily Accomodation Listing'
    )

class DSADetailsLines(models.Model):
    _name = 'dsa.details.line'
    _description = 'Daily Accommodation Line Listing'

    dsa_id = fields.Many2one(
        'dsa.details',
        string='DSA Detail',
        required=True,
        ondelete='cascade'
    )

    dsa_date_from = fields.Date(
        string='From',
        required=True,
        
    )

    dsa_date_to = fields.Date(
        string='To',
        required=True
    )

    place_of_stay = fields.Char(
        string='Place of Stay'
    )

    hotel_provided = fields.Boolean(
        string='Hotel Provided',
    )
    lunch_provided = fields.Boolean(
        string='Lunch Provided',
    )

