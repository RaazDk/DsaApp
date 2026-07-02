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
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Work Location',
        related='employee_id.work_location_id',
        store=True,
        readonly=True,
    )
    work_address_id = fields.Many2one(
        'res.partner',
        string='Work Address',
        related='employee_id.address_id',
        store=True,
        readonly=True,
    )

    tr_number = fields.Char(
        string='Travel Order Number',
        required=True
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
    conf_id = fields.Many2one(
        'dsa.conf',
        string='Allowance Configuration',
        compute='_compute_conf_id',
        store=True,
        readonly=True,
    )


    line_ids = fields.One2many(
        'dsa.details.line',
        'dsa_id',
        string='Daily Accommodation Listing',

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

    @api.depends('job_id')
    def _compute_conf_id(self):
        for rec in self:
            rec.conf_id = self.env['dsa.conf'].search([
                ('active', '=', True),
            ], limit=1)


    @api.depends(
        'travel_from',
        'travel_to',
        'line_ids',
        'line_ids.dsa_date_from',
        'line_ids.dsa_date_to'
    )
    def _compute_lines_remaining(self):
        for rec in self:

            if not rec.travel_from or not rec.travel_to:
                rec.total_travel_days = 0
                rec.lines_remaining = 0
                continue

            total_days = (
                                 rec.travel_to - rec.travel_from
                         ).days + 1

            covered_dates = set()

            for line in rec.line_ids:

                if not line.dsa_date_from or not line.dsa_date_to:
                    continue

                current = line.dsa_date_from

                while current <= line.dsa_date_to:
                    covered_dates.add(current)
                    current += timedelta(days=1)

            rec.total_travel_days = total_days
            rec.lines_remaining = max(
                0,
                total_days - len(covered_dates)
            )
    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self.conf_id = False

        if not self.job_id:
            return

        conf = self.env['dsa.conf'].search([
            ('active', '=', True),
        ], limit=1)

        if not conf:
            self.conf_id = False
            self.travel_from = False
            self.travel_to = False
            self.travel_location_from = False
            self.travel_location_to = False
            self.travel_purpose = False
            self.line_ids = [(5, 0, 0)]

            return {
                'warning': {
                    'title': 'DSA Configuration Not Found',
                    'message': (
                                   'No active DSA Rate Configuration could be found for '
                                   'designation "%s".\n\n'
                                   'Please create a DSA Configuration before proceeding.'
                               ) % self.job_id.name
                }
            }

        self.conf_id = conf

        return {
            'domain': {
                'conf_id': [
                    ('job_id', '=', self.job_id.id),
                    ('active', '=', True),
                ]
            }
        }
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
                    'title': '\u26a0\ufe0f Invalid Date Range',
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
                        'You cannot add more than %d accommodation '
                        'line(s) for the selected travel period '
                        '(%s to %s).' % (total_days, rec.travel_from, rec.travel_to)
                    )
                # Re-validate existing lines when travel window shrinks
                for line in rec.line_ids:
                    if line.dsa_date_from and line.dsa_date_from < rec.travel_from:
                        raise ValidationError(
                            'Existing accommodation line date (%s) is before '
                            'the updated travel start date (%s).'
                            % (line.dsa_date_from, rec.travel_from)
                        )
                    if line.dsa_date_to and line.dsa_date_to > rec.travel_to:
                        raise ValidationError(
                            'Existing accommodation line date (%s) is after '
                            'the updated travel end date (%s).'
                            % (line.dsa_date_to, rec.travel_to)
                        )


class DSADetailsLine(models.Model):
    _name = 'dsa.details.line'
    _description = 'Daily Accommodation Line'
    _order = 'dsa_date_from asc'

    _unique_dsa_date = models.Constraint(
        'UNIQUE(dsa_id, dsa_date_from)',
        'An accommodation entry for this date already exists on this DSA record.'
    )

    dsa_id = fields.Many2one(
        'dsa.details',
        string='DSA Detail',
        required=True,
        ondelete='cascade'
    )

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dsa_id = vals.get('dsa_id')

            if dsa_id and not vals.get('dsa_date_from'):
                dsa = self.env['dsa.details'].browse(dsa_id)

                covered_dates = set(
                    self.search([
                        ('dsa_id', '=', dsa.id)
                    ]).mapped('dsa_date_from')
                )

                total_days = (
                                     dsa.travel_to - dsa.travel_from
                             ).days + 1

                next_date = None

                for i in range(total_days):
                    candidate = dsa.travel_from + timedelta(days=i)

                    if candidate not in covered_dates:
                        next_date = candidate
                        break

                if not next_date:
                    raise ValidationError(
                        'All travel dates already have accommodation entries.'
                    )

                vals['dsa_date_from'] = next_date
                vals['dsa_date_to'] = next_date

            dsa_date_from = vals.get('dsa_date_from')

            if dsa_id and dsa_date_from:
                existing = self.search_count([
                    ('dsa_id', '=', dsa_id),
                    ('dsa_date_from', '=', dsa_date_from),
                ])

                if existing:
                    raise ValidationError(
                        'Accommodation entry for %s already exists.'
                        % dsa_date_from
                    )

        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------



    @api.onchange('dsa_date_from')
    def _onchange_duplicate_date(self):
        if not self.dsa_id or not self.dsa_date_from:
            return

        duplicates = self.dsa_id.line_ids.filtered(
            lambda l: l != self and l.dsa_date_from == self.dsa_date_from
        )

        if duplicates:
            self.dsa_date_from = False

            return {
                'warning': {
                    'title': 'Duplicate Date',
                    'message': (
                            'Accommodation entry for selected date already exists on this DSA record.'
                    ),
                }
            }

    @api.onchange('dsa_date_from', 'dsa_date_to')
    def _onchange_line_dates(self):
        """
        Validates dsa_date_from/dsa_date_to against the parent travel window.
        On violation: resets the offending field to False and shows a warning toast.
        """
        parent = self.dsa_id
        if not parent:
            return

        travel_from = parent.travel_from
        travel_to = parent.travel_to

        if not travel_from or not travel_to:
            return

        warning_msgs = []

        if self.dsa_date_from:
            if self.dsa_date_from < travel_from or self.dsa_date_from > travel_to:
                warning_msgs.append(
                    '  \u2022 "From" date %s is outside travel period \u2014 field has been reset.'
                    % self.dsa_date_from
                )
                self.dsa_date_from = False

        if self.dsa_date_to:
            if self.dsa_date_to < travel_from or self.dsa_date_to > travel_to:
                warning_msgs.append(
                    '  \u2022 "To" date %s is outside travel period \u2014 field has been reset.'
                    % self.dsa_date_to
                )
                self.dsa_date_to = False

        if self.dsa_date_from and self.dsa_date_to:
            if self.dsa_date_from > self.dsa_date_to:
                warning_msgs.append(
                    '  \u2022 "From" date cannot be after "To" date \u2014 "To" has been reset.'
                )
                self.dsa_date_to = False

        if warning_msgs:
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Invalid Accommodation Date',
                    'message': (
                        'The following date(s) were invalid and have been cleared:\n\n'
                        + '\n'.join(warning_msgs)
                        + '\n\nAllowed range:  %s  \u2192  %s' % (travel_from, travel_to)
                    ),
                }
            }

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('dsa_date_from', 'dsa_date_to', 'dsa_id')
    def _check_date_overlap(self):
        for line in self:

            if not line.dsa_date_from or not line.dsa_date_to:
                continue

            overlap = self.search([
                ('id', '!=', line.id),
                ('dsa_id', '=', line.dsa_id.id),
                ('dsa_date_from', '<=', line.dsa_date_to),
                ('dsa_date_to', '>=', line.dsa_date_from),
            ], limit=1)

            if overlap:
                raise ValidationError(
                    'Accommodation dates %s to %s overlap with existing accommodation entry %s to %s.'
                    % (
                        line.dsa_date_from,
                        line.dsa_date_to,
                        overlap.dsa_date_from,
                        overlap.dsa_date_to,
                    )
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
                        'Accommodation "From" date (%s) cannot be before '
                        'travel start date (%s).' % (line.dsa_date_from, parent.travel_from)
                    )
                if line.dsa_date_to and line.dsa_date_to > parent.travel_to:
                    raise ValidationError(
                        'Accommodation "To" date (%s) cannot be after '
                        'travel end date (%s).' % (line.dsa_date_to, parent.travel_to)
                    )