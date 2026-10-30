"""Offline tests for read-only calendar and holiday-exception parity."""
import unittest
from calendar_coverage import compare_calendar_coverage


def weekly(service="WD", friday="1", start="20260607", end="20271231"):
    return dict(service_id=service, start_date=start, end_date=end,
                monday="1", tuesday="1", wednesday="1", thursday="1",
                friday=friday, saturday="0", sunday="0")


class CalendarCoverageTests(unittest.TestCase):
    def audit(self, official=None, stored=None, official_ex=None, stored_ex=None):
        return compare_calendar_coverage(
            [weekly()] if official is None else official,
            [] if official_ex is None else official_ex,
            [weekly()] if stored is None else stored,
            [] if stored_ex is None else stored_ex)

    def test_identical_calendar_has_no_drift(self):
        r = self.audit()
        self.assertEqual(r["changed_weekly_service_id_count"], 0)
        self.assertEqual(r["official_only_exception_row_count"], 0)
        self.assertFalse(r["holiday_service_verified"])

    def test_weekday_flag_change_detected(self):
        r = self.audit(official=[weekly(friday="0")])
        self.assertEqual(r["changed_weekly_service_id_examples"], ["WD"])

    def test_date_range_change_detected(self):
        r = self.audit(official=[weekly(end="20261231")])
        self.assertEqual(r["changed_weekly_service_id_count"], 1)

    def test_added_and_removed_service_ids_detected(self):
        r = self.audit(official=[weekly("NEW")], stored=[weekly("OLD")])
        self.assertEqual(r["official_only_service_ids"], ["NEW"])
        self.assertEqual(r["stored_only_service_ids"], ["OLD"])

    def test_added_holiday_exception_detected(self):
        exception = {"service_id": "WD", "date": "20261126", "exception_type": "2"}
        r = self.audit(official_ex=[exception])
        self.assertEqual(r["official_only_exception_row_count"], 1)
        self.assertFalse(r["holiday_service_verified"])

    def test_changed_exception_type_detected_both_ways(self):
        a = {"service_id": "WD", "date": "20261126", "exception_type": "2"}
        b = dict(a, exception_type="1")
        r = self.audit(official_ex=[a], stored_ex=[b])
        self.assertEqual(r["official_only_exception_row_count"], 1)
        self.assertEqual(r["stored_only_exception_row_count"], 1)

    def test_row_order_does_not_create_drift(self):
        rows = [weekly("A"), weekly("B")]
        r = self.audit(official=list(reversed(rows)), stored=rows)
        self.assertEqual(r["changed_weekly_service_id_count"], 0)

    def test_duplicate_row_is_reported_as_drift(self):
        r = self.audit(official=[weekly(), weekly()])
        self.assertEqual(r["changed_weekly_service_id_count"], 1)

    def test_invalid_rows_are_counted_not_accepted(self):
        bad = weekly(friday="maybe", start="20261301")
        r = self.audit(official=[bad],
                       official_ex=[{"service_id": "WD", "date": "not-date", "exception_type": "9"}])
        self.assertEqual(r["official_invalid_calendar_rows"], 1)
        self.assertEqual(r["official_invalid_exception_rows"], 1)


if __name__ == "__main__":
    unittest.main()
