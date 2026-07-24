from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'),
    ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'),
    ('10', 'October'), ('11', 'November'), ('12', 'December'),
]

YEAR_SELECTION = [(str(y), str(y)) for y in range(2020, 2036)]


class DSADetails(models.Model):
    _name = 'dsa.details'
    _description = 'DSA Details'
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

    tr_number = fields.Char(string='Travel Order Number', required=True)
    po_number = fields.Char(string='PO Number', required=True)

    travel_from = fields.Date(string='Travel Start Date', required=True)
    travel_to = fields.Date(string='Travel End Date', required=True)

    travel_location_from = fields.Char(string='Travel From (Location)', required=True)
    travel_location_to = fields.Char(string='Travel To (Location)', required=True)
    travel_purpose = fields.Text(string='Travel Purpose')

    month = fields.Selection(
        MONTH_SELECTION,
        string='Month',
        required=True,
        default=lambda self: str(datetime.now().month)
    )

    year = fields.Selection(
        YEAR_SELECTION,
        string='Year',
        required=True,
        default=lambda self: str(datetime.now().year)
    )

    month_year_display = fields.Char(
        string='Month / Year',
        compute='_compute_month_year_display',
        store=True,
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

    total_dsa_amount = fields.Float(
        compute='_compute_total_dsa_amount',
        store=True,
        string='Total DSA Payable',
        aggregator=None,
    )

    total_dsa_days = fields.Integer(
        compute='_compute_total_dsa_days',
        store=True,
        string='No. of Days',
        aggregator=None,
        help='Total number of DSA days actually claimed '
             '(sum of days across all accommodation lines).',
    )

    night_halt_places = fields.Char(
        compute='_compute_night_halt_places',
        store=True,
        string='Place of Night Halt',
        help='Comma-separated list of places of stay from the '
             'accommodation lines, in date order.',
    )

    travel_cost_misc_expenses = fields.Float(
        string='Travel Cost and Misc Expenses',
        aggregator=None,
        help='Manually entered travel cost / miscellaneous expenses '
             'to add to the DSA amount for the total payable amount.',
    )

    total_payable_amount = fields.Float(
        compute='_compute_total_payable_amount',
        store=True,
        string='Total Payable Amount',
        aggregator=None,
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_last_dsa_date(self):
        """
        Returns the last date eligible to appear as a DSA accommodation line.

        Rule: travel_to is the "last day" of the trip (e.g. arrival-home day)
        and is NEVER counted as a DSA accommodation day, regardless of how
        many lines are listed. So the eligible DSA range is:

            travel_from  ->  travel_to - 1 day

        Edge case: single-day trips (travel_from == travel_to) have no
        eligible DSA day under this rule, so this returns a date before
        travel_from (i.e. an empty range) rather than raising - callers
        should treat that as "0 DSA days allowed" for that record.
        """
        self.ensure_one()
        if not self.travel_to:
            return False
        return self.travel_to - timedelta(days=1)

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends('month', 'year')
    def _compute_month_year_display(self):
        month_map = dict(MONTH_SELECTION)
        for rec in self:
            if rec.month and rec.year:
                rec.month_year_display = '%s %s' % (
                    month_map.get(rec.month, ''), rec.year
                )
            else:
                rec.month_year_display = ''

    @api.depends('job_id')
    def _compute_conf_id(self):
        for rec in self:
            # Position-specific first, then common rate fallback
            conf = self.env['dsa.conf'].get_conf_for_job(
                rec.job_id.id if rec.job_id else False
            )
            rec.conf_id = conf

    @api.depends(
        'travel_from', 'travel_to',
        'line_ids', 'line_ids.dsa_date_from', 'line_ids.dsa_date_to',
    )
    def _compute_lines_remaining(self):
        for rec in self:
            if not rec.travel_from or not rec.travel_to:
                rec.total_travel_days = 0
                rec.lines_remaining = 0
                continue

            # total_travel_days deliberately EXCLUDES travel_to (the last
            # day is never a DSA day) - same range as _get_last_dsa_date().
            total_days = (rec.travel_to - rec.travel_from).days
            covered_dates = set()

            for line in rec.line_ids:
                if not line.dsa_date_from or not line.dsa_date_to:
                    continue
                current = line.dsa_date_from
                while current <= line.dsa_date_to:
                    covered_dates.add(current)
                    current += timedelta(days=1)

            rec.total_travel_days = total_days
            rec.lines_remaining = max(0, total_days - len(covered_dates))

    @api.depends('line_ids.line_amount')
    def _compute_total_dsa_amount(self):
        for rec in self:
            rec.total_dsa_amount = sum(rec.line_ids.mapped('line_amount'))

    @api.depends('line_ids.line_days')
    def _compute_total_dsa_days(self):
        for rec in self:
            rec.total_dsa_days = sum(rec.line_ids.mapped('line_days'))

    @api.depends('line_ids.place_of_stay', 'line_ids.dsa_date_from')
    def _compute_night_halt_places(self):
        for rec in self:
            places = []
            for line in rec.line_ids.sorted('dsa_date_from'):
                if line.place_of_stay and line.place_of_stay not in places:
                    places.append(line.place_of_stay)
            rec.night_halt_places = ', '.join(places)

    @api.depends('total_dsa_amount', 'travel_cost_misc_expenses')
    def _compute_total_payable_amount(self):
        for rec in self:
            rec.total_payable_amount = (
                rec.total_dsa_amount + rec.travel_cost_misc_expenses
            )

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self.conf_id = False
        if not self.job_id:
            return

        conf = self.env['dsa.conf'].get_conf_for_job(
            self.job_id.id if self.job_id else False
        )

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

    @api.onchange('travel_from')
    def _onchange_travel_from(self):
        if not self.travel_from:
            return

        now = datetime.now().date()

        # Cannot be a future date
        if self.travel_from > now:
            self.travel_from = False
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Invalid Travel Start Date',
                    'message': 'Travel Start Date cannot be a future date.',
                }
            }

        # Cannot be before current year
        if self.travel_from.year < now.year:
            self.travel_from = False
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Invalid Travel Start Date',
                    'message': 'Travel Start Date cannot be before the current year (%d).' % now.year,
                }
            }

        # Auto-set travel_to if not set or before travel_from
        if not self.travel_to or self.travel_to < self.travel_from:
            self.travel_to = self.travel_from

        # Auto-adjust month and year from travel_from
        self.month = str(self.travel_from.month)
        self.year = str(self.travel_from.year)

    @api.onchange('travel_to')
    def _onchange_travel_to(self):
        if not self.travel_to:
            return

        now = datetime.now().date()

        # Cannot be before travel_from
        if self.travel_from and self.travel_to < self.travel_from:
            self.travel_to = self.travel_from
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Invalid Travel End Date',
                    'message': 'Travel End Date cannot be before Travel Start Date.',
                }
            }

        # Auto-adjust month/year from travel_to if travel_from not set
        if not self.travel_from and self.travel_to:
            self.month = str(self.travel_to.month)
            self.year = str(self.travel_to.year)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('travel_from')
    def _check_travel_from(self):
        now = datetime.now().date()
        for rec in self:
            if not rec.travel_from:
                continue
            if rec.travel_from > now:
                raise ValidationError(
                    'Travel Start Date cannot be a future date.'
                )
            if rec.travel_from.year < now.year:
                raise ValidationError(
                    'Travel Start Date cannot be before the current year (%d).' % now.year
                )

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
                # Eligible DSA days EXCLUDE travel_to (the last day of the
                # trip). This must match _compute_lines_remaining's
                # total_travel_days, otherwise the cap and the remaining-
                # slots counter disagree with each other.
                total_days = (rec.travel_to - rec.travel_from).days
                if len(rec.line_ids) > total_days:
                    raise ValidationError(
                        'You cannot add more than %d accommodation '
                        'line(s) for the selected travel period '
                        '(%s to %s), since the last travel day (%s) is '
                        'not counted as a DSA day.'
                        % (total_days, rec.travel_from, rec.travel_to, rec.travel_to)
                    )

                last_dsa_date = rec._get_last_dsa_date()
                for line in rec.line_ids:
                    if line.dsa_date_from and line.dsa_date_from < rec.travel_from:
                        raise ValidationError(
                            'Existing accommodation line date (%s) is before '
                            'the updated travel start date (%s).'
                            % (line.dsa_date_from, rec.travel_from)
                        )
                    if line.dsa_date_to and last_dsa_date and line.dsa_date_to > last_dsa_date:
                        raise ValidationError(
                            'Existing accommodation line date (%s) is after '
                            'the last eligible DSA date (%s). The final '
                            'travel day (%s) is not counted as a DSA day.'
                            % (line.dsa_date_to, last_dsa_date, rec.travel_to)
                        )

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_print_claimsheet(self):
        return self.env.ref('dsa.action_report_dsa_claimsheet').report_action(self)


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

    dsa_date_from = fields.Date(string='From', required=True)
    dsa_date_to = fields.Date(string='To', required=True)

    place_of_stay = fields.Char(string='Place of Stay')
    hotel_provided = fields.Boolean(string='Hotel Provided')
    lunch_provided = fields.Boolean(string='Lunch Provided')

    line_days = fields.Integer(
        compute='_compute_line_amount', store=True, string='No. of Days'
    )
    dsa_rate = fields.Float(
        compute='_compute_line_amount', store=True, string='Per Diem Rate'
    )
    deduction_pct = fields.Float(
        compute='_compute_line_amount', store=True, string='Deduction %'
    )
    claimed_rate = fields.Float(
        compute='_compute_line_amount', store=True, string='Claimed Per Diem'
    )
    line_amount = fields.Float(
        compute='_compute_line_amount', store=True, string='Amount'
    )

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends(
        'dsa_date_from', 'dsa_date_to',
        'hotel_provided', 'lunch_provided',
        'dsa_id.conf_id.dsa_rate',
        'dsa_id.conf_id.deduction_if_hotel_provided',
        'dsa_id.conf_id.deduction_if_lunch_provided',
    )
    def _compute_line_amount(self):
        for line in self:
            # Days: inclusive of both start and end
            if line.dsa_date_from and line.dsa_date_to:
                line.line_days = (line.dsa_date_to - line.dsa_date_from).days + 1
            else:
                line.line_days = 0

            conf = line.dsa_id.conf_id
            rate = conf.dsa_rate if conf else 0.0

            ded = 0.0
            if conf:
                if line.hotel_provided:
                    ded += conf.deduction_if_hotel_provided or 0.0
                if line.lunch_provided:
                    ded += conf.deduction_if_lunch_provided or 0.0
            ded = min(ded, 100.0)

            line.dsa_rate = rate
            line.deduction_pct = ded
            line.claimed_rate = rate * (1.0 - ded / 100.0)
            line.line_amount = line.line_days * line.claimed_rate

    # -------------------------------------------------------------------------
    # Create override — auto-fill next available date
    # First line  -> travel_from
    # Next line   -> previous line's dsa_date_to + 1 day
    # Last eligible DSA date -> travel_to - 1 day (travel_to itself is the
    # trip's last/arrival day and is never treated as a DSA day).
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dsa_id = vals.get('dsa_id')

            if dsa_id and not vals.get('dsa_date_from'):
                dsa = self.env['dsa.details'].browse(dsa_id)

                # Get existing lines sorted by date
                existing_lines = self.search(
                    [('dsa_id', '=', dsa.id)],
                    order='dsa_date_from asc'
                )

                if existing_lines:
                    # Next line starts day after last line's dsa_date_to
                    last_line = existing_lines[-1]
                    next_date = last_line.dsa_date_to + timedelta(days=1)
                else:
                    # First line starts at travel_from
                    next_date = dsa.travel_from

                # Clamp to the last eligible DSA date (travel_to - 1), NOT
                # travel_to itself, so the final travel day never becomes
                # a normal DSA line.
                last_dsa_date = dsa._get_last_dsa_date()
                if last_dsa_date and next_date > last_dsa_date:
                    raise ValidationError(
                        'All eligible DSA dates already have accommodation '
                        'entries. The last travel day (%s) is not counted '
                        'as a DSA day.' % dsa.travel_to
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
                    'message': 'Accommodation entry for selected date already exists.',
                }
            }

    @api.onchange('dsa_date_from', 'dsa_date_to')
    def _onchange_line_dates(self):
        parent = self.dsa_id
        if not parent or not parent.travel_from or not parent.travel_to:
            return

        travel_from = parent.travel_from
        # The last travel day (travel_to) is never a valid DSA day.
        last_dsa_date = parent._get_last_dsa_date()
        warning_msgs = []

        if self.dsa_date_from:
            if (self.dsa_date_from < travel_from
                    or not last_dsa_date
                    or self.dsa_date_from > last_dsa_date):
                warning_msgs.append(
                    '  \u2022 "From" date %s is outside the eligible DSA '
                    'period \u2014 reset.' % self.dsa_date_from
                )
                self.dsa_date_from = False

        if self.dsa_date_to:
            if (self.dsa_date_to < travel_from
                    or not last_dsa_date
                    or self.dsa_date_to > last_dsa_date):
                warning_msgs.append(
                    '  \u2022 "To" date %s is outside the eligible DSA '
                    'period \u2014 reset.' % self.dsa_date_to
                )
                self.dsa_date_to = False

        if self.dsa_date_from and self.dsa_date_to:
            if self.dsa_date_from > self.dsa_date_to:
                warning_msgs.append(
                    '  \u2022 "From" cannot be after "To" \u2014 "To" reset.'
                )
                self.dsa_date_to = False

        if warning_msgs:
            allowed_to = last_dsa_date or travel_from
            return {
                'warning': {
                    'title': '\u26a0\ufe0f Invalid Accommodation Date',
                    'message': (
                        'The following date(s) were invalid and cleared:\n\n'
                        + '\n'.join(warning_msgs)
                        + '\n\nAllowed range:  %s  \u2192  %s'
                        '  (the last travel day, %s, is never a DSA day)'
                        % (travel_from, allowed_to, parent.travel_to)
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
                    'Accommodation dates %s to %s overlap with existing entry %s to %s.'
                    % (
                        line.dsa_date_from, line.dsa_date_to,
                        overlap.dsa_date_from, overlap.dsa_date_to,
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
                last_dsa_date = parent._get_last_dsa_date()
                if line.dsa_date_from and line.dsa_date_from < parent.travel_from:
                    raise ValidationError(
                        'Accommodation "From" date (%s) cannot be before '
                        'travel start date (%s).'
                        % (line.dsa_date_from, parent.travel_from)
                    )
                if line.dsa_date_to and last_dsa_date and line.dsa_date_to > last_dsa_date:
                    raise ValidationError(
                        'Accommodation "To" date (%s) cannot be after the '
                        'last eligible DSA date (%s). The final travel day '
                        '(%s) is not counted as a DSA day.'
                        % (line.dsa_date_to, last_dsa_date, parent.travel_to)
                    )