import unittest
from datetime import datetime, timedelta, timezone

from app import create_app, db
from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.models import DbUpdate


class DbUpdatePermitTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_only_first_caller_gets_permit_until_expiry(self):
        self.assertTrue(ask_dbupdate_permit('JOB', timedelta(hours=1)))
        self.assertFalse(ask_dbupdate_permit('JOB', timedelta(hours=1)))

    def test_permit_is_granted_again_after_expiry(self):
        self.assertTrue(ask_dbupdate_permit('JOB', timedelta(hours=1)))
        dbu = db.session.get(DbUpdate, 'JOB')
        dbu.expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()

        self.assertTrue(ask_dbupdate_permit('JOB', timedelta(hours=1)))
        self.assertEqual(db.session.get(DbUpdate, 'JOB').count, 2)

    def test_keys_do_not_block_each_other(self):
        self.assertTrue(ask_dbupdate_permit('JOB_A', timedelta(hours=1)))
        self.assertTrue(ask_dbupdate_permit('JOB_B', timedelta(hours=1)))

    def test_expiry_is_stored_in_utc(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        ask_dbupdate_permit('JOB', timedelta(hours=1))
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        expired = db.session.get(DbUpdate, 'JOB').expired
        self.assertGreaterEqual(expired, before + timedelta(hours=1))
        self.assertLessEqual(expired, after + timedelta(hours=1))

    def test_existing_row_with_null_expiry_gets_permit(self):
        db.session.add(DbUpdate(id='JOB', expired=None, count=5))
        db.session.commit()

        self.assertTrue(ask_dbupdate_permit('JOB', timedelta(hours=1)))
        self.assertEqual(db.session.get(DbUpdate, 'JOB').count, 6)


if __name__ == '__main__':
    unittest.main()
