import unittest
from datetime import datetime
from src.phase0_foundations.models import Review, RunRecord
from src.phase0_foundations.run_log import RunLog
import os

class TestFoundations(unittest.TestCase):
    def setUp(self):
        import time
        self.db_path = f"test_run_log_{int(time.time() * 1000)}.db"
        self.log = RunLog(self.db_path)

    def tearDown(self):
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.db_path + suffix
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def test_run_record_creation(self):
        run = RunRecord(
            run_id="test_123",
            product="Groww",
            iso_week="2026-W17",
            status="success",
            review_count=10,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        self.log.create_run(run)
        
        fetched = self.log.get_run("Groww", "2026-W17")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.run_id, "test_123")
        self.assertEqual(fetched.status, "success")

    def test_exists(self):
        run = RunRecord(
            run_id="test_456",
            product="INDMoney",
            iso_week="2026-W17",
            status="success",
            started_at=datetime.now()
        )
        self.log.create_run(run)
        self.assertTrue(self.log.exists("INDMoney", "2026-W17"))
        self.assertFalse(self.log.exists("INDMoney", "2026-W18"))

if __name__ == "__main__":
    unittest.main()
