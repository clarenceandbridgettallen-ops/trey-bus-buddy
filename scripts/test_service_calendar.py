import unittest
from service_calendar import audit_frequency_service_date


def week(sid='weekday'):
    return {'service_id':sid,'start_date':'20260101','end_date':'20261231',
            'monday':'1','tuesday':'1','wednesday':'1','thursday':'1','friday':'1',
            'saturday':'0','sunday':'0'}

class CalendarAuditTests(unittest.TestCase):
    def setUp(self):
        self.freq = [{'trip_id':'t'}]
        self.trips = {'t': {'service':'weekday'}}

    def audit(self, cal=None, exc=None, date='20261029'):
        return audit_frequency_service_date(self.freq,self.trips,cal if cal is not None else [week()],exc or [],date)

    def test_weekday_active(self):
        self.assertEqual(self.audit()['active_rows'],1)

    def test_weekend_inactive(self):
        self.assertEqual(self.audit(date='20261031')['inactive_rows'],1)

    def test_added_exception_overrides_weekend(self):
        e=[{'service_id':'weekday','date':'20261031','exception_type':'1'}]
        self.assertEqual(self.audit(exc=e,date='20261031')['active_rows'],1)

    def test_removed_exception_overrides_weekday(self):
        e=[{'service_id':'weekday','date':'20261029','exception_type':'2'}]
        self.assertEqual(self.audit(exc=e)['inactive_rows'],1)

    def test_exception_only_service(self):
        e=[{'service_id':'weekday','date':'20261029','exception_type':'1'}]
        self.assertEqual(self.audit(cal=[],exc=e)['active_rows'],1)

    def test_missing_service_is_uncertain(self):
        self.assertEqual(self.audit(cal=[])['uncertain_rows'],1)

    def test_conflicting_exceptions_are_uncertain(self):
        e=[{'service_id':'weekday','date':'20261029','exception_type':'1'},
           {'service_id':'weekday','date':'20261029','exception_type':'2'}]
        self.assertEqual(self.audit(exc=e)['uncertain_rows'],1)

    def test_invalid_weekday_flag_is_uncertain(self):
        c=week(); c['thursday']='bad'
        self.assertEqual(self.audit(cal=[c])['uncertain_rows'],1)
        self.assertEqual(self.audit(cal=[c])['invalid_calendar_rows'],1)

    def test_unknown_trip_is_uncertain(self):
        self.assertEqual(audit_frequency_service_date([{'trip_id':'missing'}],self.trips,[week()],[],'20261029')['uncertain_rows'],1)

    def test_overnight_service_date_not_clock_date(self):
        self.assertEqual(self.audit(date='20261030')['active_rows'],1)

if __name__ == '__main__': unittest.main()
