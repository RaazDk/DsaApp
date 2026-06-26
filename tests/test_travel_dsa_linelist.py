from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


def d(s):
    """Shorthand: d('2026-06-20') -> date(2026, 6, 20)"""
    return date.fromisoformat(s)


class TestDSADetails(TransactionCase):
    """
    Full test suite for dsa.details and dsa.details.line.
    Covers every constraint, compute, and edge case.
    """

    # =========================================================================
    # Setup
    # =========================================================================

    def setUp(self):
        super().setUp()

        self.job = self.env['hr.job'].create({'name': 'Test Officer'})

        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'job_id': self.job.id,
        })

        # A standard 3-day DSA record used as base for most tests
        self.dsa = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-001',
            'month': '6',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-22'),
            'travel_location_from': 'Kathmandu',
            'travel_location_to': 'Pokhara',
        })

    def _make_line(self, dsa, date_from, date_to, **kwargs):
        """Helper to create a dsa.details.line directly."""
        return self.env['dsa.details.line'].create({
            'dsa_id': dsa.id,
            'dsa_date_from': date_from,
            'dsa_date_to': date_to,
            **kwargs,
        })

    # =========================================================================
    # DSADetails — Required Fields
    # =========================================================================

    def test_missing_employee_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details'].create({
                'po_number': 'PO-X',
                'month': '1',
                'travel_from': d('2026-01-01'),
                'travel_to': d('2026-01-02'),
                'travel_location_from': 'A',
                'travel_location_to': 'B',
            })

    def test_missing_po_number_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details'].create({
                'employee_id': self.employee.id,
                'month': '1',
                'travel_from': d('2026-01-01'),
                'travel_to': d('2026-01-02'),
                'travel_location_from': 'A',
                'travel_location_to': 'B',
            })

    def test_missing_travel_location_from_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details'].create({
                'employee_id': self.employee.id,
                'po_number': 'PO-X',
                'month': '1',
                'travel_from': d('2026-01-01'),
                'travel_to': d('2026-01-02'),
                'travel_location_to': 'B',
            })

    def test_missing_travel_location_to_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details'].create({
                'employee_id': self.employee.id,
                'po_number': 'PO-X',
                'month': '1',
                'travel_from': d('2026-01-01'),
                'travel_to': d('2026-01-02'),
                'travel_location_from': 'A',
            })

    #--------------------------------------------
    # DSADetails — Travel Date Constraints
    #-----------------------------------------------

    def test_travel_to_before_travel_from_raises(self):
        with self.assertRaises(ValidationError):
            self.env['dsa.details'].create({
                'employee_id': self.employee.id,
                'po_number': 'PO-002',
                'month': '6',
                'travel_from': d('2026-06-22'),
                'travel_to': d('2026-06-20'),
                'travel_location_from': 'A',
                'travel_location_to': 'B',
            })

    def test_travel_to_same_as_travel_from_allowed(self):
        """Single-day travel is valid."""
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-003',
            'month': '6',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-20'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.total_travel_days, 1)

    def test_travel_dates_one_day_apart(self):
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-004',
            'month': '6',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-21'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.total_travel_days, 2)

    def test_update_travel_to_before_from_raises(self):
        """Updating an existing record to invalid dates should also raise."""
        with self.assertRaises(ValidationError):
            self.dsa.write({'travel_to': d('2026-06-19')})

#-----------------------------------------------------------------------
    # DSADetails — Compute: lines_remaining / total_travel_days
#---------------------------------------------------------------------
    def test_total_travel_days_three_day_trip(self):
        self.assertEqual(self.dsa.total_travel_days, 3)

    def test_lines_remaining_no_lines(self):
        self.assertEqual(self.dsa.lines_remaining, 3)

    def test_lines_remaining_decreases_as_lines_added(self):
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertEqual(self.dsa.lines_remaining, 2)

        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        self.assertEqual(self.dsa.lines_remaining, 1)

        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertEqual(self.dsa.lines_remaining, 0)

    def test_lines_remaining_never_negative(self):
        """lines_remaining floors at 0 even if somehow more lines exist."""
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertEqual(self.dsa.lines_remaining, 0)

    def test_lines_remaining_no_travel_dates(self):
        """Without travel dates, remaining should be 0."""
        rec = self.env['dsa.details'].new({
            'employee_id': self.employee.id,
            'po_number': 'PO-X',
            'month': '1',
        })
        self.assertEqual(rec.lines_remaining, 0)
        self.assertEqual(rec.total_travel_days, 0)

    #----------------------------------------------------------------
    # DSADetails — Line Count Constraint
#----------------------------------------------------------
    def test_line_count_exceeds_travel_days_raises(self):
        """Cannot add more lines than travel days."""
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))

    def test_exact_line_count_equals_travel_days_allowed(self):
        """Exactly one line per day is valid."""
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertEqual(len(self.dsa.line_ids), 3)

    def test_single_day_trip_only_one_line_allowed(self):
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-005',
            'month': '6',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-20'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self._make_line(rec, d('2026-06-20'), d('2026-06-20'))
        with self.assertRaises(ValidationError):
            self._make_line(rec, d('2026-06-20'), d('2026-06-20'))

#-----------------------------------------------
    # DSADetailsLine — Required Fields
#--------------------------------------------
    def test_line_missing_dsa_date_from_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details.line'].create({
                'dsa_id': self.dsa.id,
                'dsa_date_to': d('2026-06-20'),
            })

    def test_line_missing_dsa_date_to_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details.line'].create({
                'dsa_id': self.dsa.id,
                'dsa_date_from': d('2026-06-20'),
            })

    def test_line_missing_dsa_id_raises(self):
        with self.assertRaises(Exception):
            self.env['dsa.details.line'].create({
                'dsa_date_from': d('2026-06-20'),
                'dsa_date_to': d('2026-06-20'),
            })

    #-----------------------------------------------------------
    # DSADetailsLine — Date Range Constraint (within travel window)
#------------------------------------------------------------
    def test_line_date_from_before_travel_from_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-06-19'), d('2026-06-20'))

    def test_line_date_from_way_before_travel_from_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-01-01'), d('2026-06-20'))

    def test_line_date_to_after_travel_to_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-06-20'), d('2026-06-23'))

    def test_line_date_to_way_after_travel_to_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-06-20'), d('2026-12-31'))

    def test_line_both_dates_outside_travel_window_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-07-01'), d('2026-07-31'))

    def test_line_date_from_equals_travel_from_allowed(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertTrue(line.id)

    def test_line_date_to_equals_travel_to_allowed(self):
        line = self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertTrue(line.id)

    def test_line_spanning_full_travel_window_allowed(self):
        """A line from travel_from to travel_to is valid."""
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-22'))
        self.assertTrue(line.id)

    def test_line_date_from_after_date_to_raises(self):
        with self.assertRaises(ValidationError):
            self._make_line(self.dsa, d('2026-06-22'), d('2026-06-20'))

    def test_line_date_from_equals_date_to_allowed(self):
        """Same from and to date is valid (single day stay)."""
        line = self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        self.assertTrue(line.id)

#--------------------------------------------------------
    # DSADetailsLine — Unique Date Constraint
    #----------------------------------------------------

    def test_duplicate_dsa_date_from_same_dsa_raises(self):
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        with self.assertRaises(Exception):
            # _sql_constraints or _check_unique_date_per_dsa should catch this
            self._make_line(self.dsa, d('2026-06-20'), d('2026-06-21'))

    def test_same_date_on_different_dsa_records_allowed(self):
        """Same dsa_date_from is fine across different DSA records."""
        dsa2 = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-006',
            'month': '6',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-22'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        line2 = self._make_line(dsa2, d('2026-06-20'), d('2026-06-20'))
        self.assertTrue(line2.id)

    def test_different_dates_on_same_dsa_allowed(self):
        l1 = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        l2 = self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        l3 = self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertEqual(len(self.dsa.line_ids), 3)

#------------------------------------------------------
    # DSADetailsLine — Optional Fields
#-----------------------------------------------------
    def test_line_without_place_of_stay_allowed(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertFalse(line.place_of_stay)

    def test_line_with_all_optional_fields(self):
        line = self._make_line(
            self.dsa,
            d('2026-06-20'),
            d('2026-06-20'),
            place_of_stay='Hotel ABC',
            hotel_provided=True,
            lunch_provided=True,
        )
        self.assertEqual(line.place_of_stay, 'Hotel ABC')
        self.assertTrue(line.hotel_provided)
        self.assertTrue(line.lunch_provided)

    def test_line_hotel_provided_defaults_false(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertFalse(line.hotel_provided)

    def test_line_lunch_provided_defaults_false(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertFalse(line.lunch_provided)

#-----------------------------------------------
    # DSADetailsLine — lines_remaining Related Field
#--------------------------------------------s
    def test_line_lines_remaining_reflects_parent(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        # Parent had 3 days, 1 line added → 2 remaining
        self.assertEqual(line.lines_remaining, 2)

    def test_line_lines_remaining_zero_when_full(self):
        l1 = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        l2 = self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        l3 = self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self.assertEqual(l3.lines_remaining, 0)

    # =========================================================================
    # DSADetails — job_id Related Field
    # =========================================================================

    def test_job_id_auto_populated_from_employee(self):
        self.assertEqual(self.dsa.job_id, self.job)

    def test_job_id_updates_when_employee_changes(self):
        new_job = self.env['hr.job'].create({'name': 'Senior Officer'})
        new_employee = self.env['hr.employee'].create({
            'name': 'Another Employee',
            'job_id': new_job.id,
        })
        self.dsa.write({'employee_id': new_employee.id})
        self.assertEqual(self.dsa.job_id, new_job)

    def test_employee_without_job_gives_empty_job_id(self):
        emp_no_job = self.env['hr.employee'].create({'name': 'No Job Employee'})
        self.dsa.write({'employee_id': emp_no_job.id})
        self.assertFalse(self.dsa.job_id)

    # =========================================================================
    # DSADetails — Month Default
    # =========================================================================

    def test_month_default_is_current_month(self):
        from datetime import datetime
        expected = str(datetime.now().month)
        rec = self.env['dsa.details'].new({
            'employee_id': self.employee.id,
            'po_number': 'PO-X',
            'travel_from': d('2026-06-20'),
            'travel_to': d('2026-06-22'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.month, expected)

    # =========================================================================
    # DSADetails — Cascade Delete
    # =========================================================================

    def test_lines_deleted_when_parent_deleted(self):
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        dsa_id = self.dsa.id
        self.dsa.unlink()
        remaining = self.env['dsa.details.line'].search([
            ('dsa_id', '=', dsa_id)
        ])
        self.assertFalse(remaining)

    # =========================================================================
    # DSADetails — Write / Update Edge Cases
    # =========================================================================

    def test_shrink_travel_dates_with_existing_lines_raises(self):
        """Shrinking travel window so existing lines fall outside should raise."""
        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        with self.assertRaises(ValidationError):
            self.dsa.write({'travel_to': d('2026-06-21')})

    def test_extend_travel_dates_increases_lines_remaining(self):
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self.assertEqual(self.dsa.lines_remaining, 2)
        self.dsa.write({'travel_to': d('2026-06-24')})
        self.assertEqual(self.dsa.total_travel_days, 5)
        self.assertEqual(self.dsa.lines_remaining, 4)

    def test_update_line_date_to_valid_date_allowed(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        line.write({'dsa_date_from': d('2026-06-21'), 'dsa_date_to': d('2026-06-21')})
        self.assertEqual(line.dsa_date_from, d('2026-06-21'))

    def test_update_line_date_to_invalid_date_raises(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        with self.assertRaises(ValidationError):
            line.write({'dsa_date_from': d('2026-07-01'), 'dsa_date_to': d('2026-07-01')})

    def test_update_line_date_from_after_date_to_raises(self):
        line = self._make_line(self.dsa, d('2026-06-20'), d('2026-06-21'))
        with self.assertRaises(ValidationError):
            line.write({'dsa_date_from': d('2026-06-22')})

    # =========================================================================
    # DSADetails — Long trips / boundary values
    # =========================================================================

    def test_long_trip_30_days(self):
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-LONG',
            'month': '1',
            'travel_from': d('2026-01-01'),
            'travel_to': d('2026-01-30'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.total_travel_days, 30)
        self.assertEqual(rec.lines_remaining, 30)

    def test_long_trip_all_lines_filled(self):
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-LONG2',
            'month': '1',
            'travel_from': d('2026-01-01'),
            'travel_to': d('2026-01-05'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        for i in range(5):
            self._make_line(
                rec,
                d('2026-01-01') + timedelta(days=i),
                d('2026-01-01') + timedelta(days=i),
            )
        self.assertEqual(rec.lines_remaining, 0)
        with self.assertRaises(ValidationError):
            self._make_line(rec, d('2026-01-05'), d('2026-01-05'))

    def test_year_boundary_trip(self):
        """Trip spanning Dec 31 to Jan 1."""
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-NYE',
            'month': '12',
            'travel_from': d('2025-12-31'),
            'travel_to': d('2026-01-01'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.total_travel_days, 2)
        self._make_line(rec, d('2025-12-31'), d('2025-12-31'))
        self._make_line(rec, d('2026-01-01'), d('2026-01-01'))
        self.assertEqual(rec.lines_remaining, 0)

    def test_leap_year_feb_29(self):
        """Feb 29 on a leap year is a valid date."""
        rec = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-LEAP',
            'month': '2',
            'travel_from': d('2028-02-28'),
            'travel_to': d('2028-02-29'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self.assertEqual(rec.total_travel_days, 2)
        line = self._make_line(rec, d('2028-02-29'), d('2028-02-29'))
        self.assertTrue(line.id)

    # =========================================================================
    # DSADetails — Multiple Records Isolation
    # =========================================================================

    def test_two_dsa_records_independent_line_counts(self):
        dsa2 = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-007',
            'month': '7',
            'travel_from': d('2026-07-01'),
            'travel_to': d('2026-07-02'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(dsa2, d('2026-07-01'), d('2026-07-01'))

        self.assertEqual(self.dsa.lines_remaining, 2)
        self.assertEqual(dsa2.lines_remaining, 1)

    def test_same_employee_multiple_dsa_records(self):
        dsa2 = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-008',
            'month': '7',
            'travel_from': d('2026-07-10'),
            'travel_to': d('2026-07-12'),
            'travel_location_from': 'X',
            'travel_location_to': 'Y',
        })
        self.assertTrue(dsa2.id)
        self.assertEqual(dsa2.employee_id, self.employee)

    # =========================================================================
    # DSADetails — _order
    # =========================================================================

    def test_records_ordered_by_travel_from_desc(self):
        dsa2 = self.env['dsa.details'].create({
            'employee_id': self.employee.id,
            'po_number': 'PO-009',
            'month': '1',
            'travel_from': d('2026-01-01'),
            'travel_to': d('2026-01-03'),
            'travel_location_from': 'A',
            'travel_location_to': 'B',
        })
        records = self.env['dsa.details'].search([
            ('employee_id', '=', self.employee.id)
        ])
        self.assertEqual(records[0].travel_from, d('2026-06-20'))
        self.assertEqual(records[1].travel_from, d('2026-01-01'))

    # =========================================================================
    # DSADetailsLine — _order
    # =========================================================================

    def test_lines_ordered_by_dsa_date_from_asc(self):
        self._make_line(self.dsa, d('2026-06-22'), d('2026-06-22'))
        self._make_line(self.dsa, d('2026-06-20'), d('2026-06-20'))
        self._make_line(self.dsa, d('2026-06-21'), d('2026-06-21'))
        dates = self.dsa.line_ids.mapped('dsa_date_from')
        self.assertEqual(dates, sorted(dates))