from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class DSADetails(models.Model):
    _name = 'dsa.details'
    _description = 'DSA Details, includes employee name, travel dates and necessary information to calculate DSA Amount'
    _order = 'travel_from desc'

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
        string='Travel From (Location)',
        required=True
    )

    travel_location_to = fields.Char(
        string='Travel To (Location)',
        required=True
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
        string='Daily Accommodation Listing'
    )

    lines_remaining = fields.Integer(
        compute='_compute_lines_remaining',
        string='Remaining Accommodation Slots'
    )

    total_travel_days = fields.Integer(
        compute='_compute_lines_remaining',
        string='Total Travel Days'
    )

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends('travel_from', 'travel_to', 'line_ids')
    def _compute_lines_remaining(self):
        for rec in self:
            if rec.travel_from and rec.travel_to and rec.travel_to >= rec.travel_from:
                total = (rec.travel_to - rec.travel_from).days + 1
                rec.total_travel_days = total
                rec.lines_remaining = max(0, total - len(rec.line_ids))
            else:
                rec.total_travel_days = 0
                rec.lines_remaining = 0

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('travel_from')
    def _onchange_travel_from(self):
        if self.travel_from and (
            not self.travel_to or self.travel_to < self.travel_from
        ):
            self.travel_to = self.travel_from

    @api.onchange('travel_to')
    def _onchange_travel_to(self):
        if (
            self.travel_from
            and self.travel_to
            and self.travel_to < self.travel_from
        ):
            self.travel_to = self.travel_from
            return {
                'warning': {
                    'title': '⚠️ Invalid Date Range',
                    'message': 'Travel End Date cannot be before Travel Start Date.',
                }
            }

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('travel_from', 'travel_to')
    def _check_travel_dates(self):
        for rec in self:
            if rec.travel_from and rec.travel_to:
                if rec.travel_to < rec.travel_from:
                    raise ValidationError(
                        'Travel End Date cannot be before Travel Start Date.'
                    )

    @api.constrains('line_ids', 'travel_from', 'travel_to')
    def _check_line_count(self):
        for rec in self:
            if rec.travel_from and rec.travel_to:
                total_days = (rec.travel_to - rec.travel_from).days + 1
                if len(rec.line_ids) > total_days:
                    raise ValidationError(
                        f'You cannot add more than {total_days} accommodation '
                        f'line(s) for the selected travel period '
                        f'({rec.travel_from} to {rec.travel_to}).'
                    )


class DSADetailsLine(models.Model):
    _name = 'dsa.details.line'
    _description = 'Daily Accommodation Line'
    _order = 'dsa_date_from asc'

    # One accommodation entry per date per DSA record
    _sql_constraints = [
        (
            'unique_dsa_date_from',
            'UNIQUE(dsa_id, dsa_date_from)',
            'An accommodation entry for this date already exists on this DSA record.'
        )
    ]

    dsa_id = fields.Many2one(
        'dsa.details',
        string='DSA Detail',
        required=True,
        ondelete='cascade'
    )

    # Related from parent so line form view can use it for button visibility
    lines_remaining = fields.Integer(
        related='dsa_id.lines_remaining',
        string='Remaining Days',
        readonly=True,
    )

    dsa_date_from = fields.Date(
        string='From',
        required=True,
    )

    dsa_date_to = fields.Date(
        string='To',
        required=True,
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

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('dsa_id')
    def _onchange_dsa_id(self):
        """
        Fires when this line is linked to its parent — including on unsaved
        (NewId) parent records.

        Sequence:
          Line 1  →  travel_from
          Line 2  →  line 1 dsa_date_from + 1 day
          Line N  →  line N-1 dsa_date_from + 1 day
          Always clamped to travel_to
        """
        parent = self.dsa_id
        if not parent or not parent.travel_from:
            return

        existing = parent.line_ids.filtered(
            lambda l: l.dsa_date_from and l != self
        ).sorted('dsa_date_from')

        if existing:
            next_date = existing[-1].dsa_date_from + timedelta(days=1)
        else:
            next_date = parent.travel_from

        if parent.travel_to and next_date > parent.travel_to:
            next_date = parent.travel_to

        self.dsa_date_from = next_date
        self.dsa_date_to = next_date

    @api.onchange('dsa_date_from', 'dsa_date_to')
    def _onchange_line_dates(self):
        """
        If user manually picks a date outside the travel window,
        auto-correct and show Odoo's native warning toast.
        """
        parent = self.dsa_id
        if not parent or not parent.travel_from or not parent.travel_to:
            return

        warning_msgs = []

        if self.dsa_date_from:
            if self.dsa_date_from < parent.travel_from:
                self.dsa_date_from = parent.travel_from
                warning_msgs.append(
                    f'  \u2022 "From" date set to travel start: {parent.travel_from}'
                )
            elif self.dsa_date_from > parent.travel_to:
                self.dsa_date_from = parent.travel_to
                warning_msgs.append(
                    f'  \u2022 "From" date set to travel end: {parent.travel_to}'
                )

        if self.dsa_date_to:
            if self.dsa_date_to < parent.travel_from:
                self.dsa_date_to = parent.travel_from
                warning_msgs.append(
                    f'  \u2022 "To" date set to travel start: {parent.travel_from}'
                )
            elif self.dsa_date_to > parent.travel_to:
                self.dsa_date_to = parent.travel_to
                warning_msgs.append(
                    f'  \u2022 "To" date set to travel end: {parent.travel_to}'
                )

        if (
            self.dsa_date_from
            and self.dsa_date_to
            and self.dsa_date_from > self.dsa_date_to
        ):
            self.dsa_date_to = self.dsa_date_from
            warning_msgs.append(
                '  \u2022 "To" date cannot be before "From" \u2014 set to match "From".'
            )

        if warning_msgs:
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Date Out of Travel Range',
                    'message': (
                        'The selected date(s) were outside the travel period '
                        'and have been adjusted:\n\n'
                        + '\n'.join(warning_msgs)
                        + f'\n\nAllowed range:  {parent.travel_from}  \u2192  {parent.travel_to}'
                    ),
                }
            }

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('dsa_date_from')
    def _check_unique_date_per_dsa(self):
        for line in self:
            duplicate = self.search([
                ('dsa_id', '=', line.dsa_id.id),
                ('dsa_date_from', '=', line.dsa_date_from),
                ('id', '!=', line.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'An accommodation entry for {line.dsa_date_from} already '
                    f'exists on this DSA record. Each date can only have one entry.'
                )

    @api.constrains('dsa_date_from', 'dsa_date_to')
    def _check_line_dates(self):
        for line in self:
            if line.dsa_date_from and line.dsa_date_to:
                if line.dsa_date_from > line.dsa_date_to:
                    raise ValidationError(
                        'Accommodation start date cannot be after end date.'
                    )

            parent = line.dsa_id
            if parent.travel_from and parent.travel_to:
                if line.dsa_date_from and line.dsa_date_from < parent.travel_from:
                    raise ValidationError(
                        f'Accommodation "From" date ({line.dsa_date_from}) '
                        f'cannot be before travel start date ({parent.travel_from}).'
                    )
                if line.dsa_date_to and line.dsa_date_to > parent.travel_to:
                    raise ValidationError(
                        f'Accommodation "To" date ({line.dsa_date_to}) '
                        f'cannot be after travel end date ({parent.travel_to}).'
                    )