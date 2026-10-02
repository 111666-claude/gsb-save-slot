import unittest

from saves.core import SaveError, SlotStore


class BasicTest(unittest.TestCase):
    def test_empty_store_has_no_slots(self):
        self.assertEqual(SlotStore().slots(), [])

    def test_load_missing_slot_raises(self):
        with self.assertRaises(SaveError):
            SlotStore().load("nope")

    def test_round_trip(self):
        store = SlotStore()
        store.save("a", "one", 0)
        self.assertEqual(store.load("a"), "one")


class SlotListTest(unittest.TestCase):
    def test_slots_sorted_by_last_write(self):
        store = SlotStore()
        store.save("a", "1", 10)
        store.save("b", "2", 20)
        self.assertEqual(store.slots(), ["b", "a"])

    def test_no_eviction_within_limit(self):
        store = SlotStore(max_slots=3)
        for index in range(3):
            store.save("s%d" % index, "x", index)
        self.assertEqual(len(store.slots()), 3)
        self.assertEqual(store.evicted, 0)


class AtomicWriteTest(unittest.TestCase):
    def test_crash_keeps_previous_save(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.crash_after = 11
        with self.assertRaises(SaveError):
            store.save("a", "two", 10)
        self.assertEqual(store.load("a"), "one")

    def test_crash_leaves_only_tmp_file(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.crash_after = 5
        with self.assertRaises(SaveError):
            store.save("a", "two", 10)
        self.assertIn("a.tmp", store.files)
        self.assertEqual(store.files["a.dat"], store._encode("one"))

    def test_crash_on_first_save_raises_on_load(self):
        store = SlotStore()
        store.crash_after = 3
        with self.assertRaises(SaveError):
            store.save("a", "one", 0)
        with self.assertRaises(SaveError):
            store.load("a")


class BackupFallbackTest(unittest.TestCase):
    def test_corrupt_main_falls_back_to_backup(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        store.files["a.dat"] = "00000000|xxx"
        self.assertEqual(store.load("a"), "one")
        self.assertEqual(store.fallbacks, 1)

    def test_both_corrupt_raises(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        store.files["a.dat"] = "00000000|xxx"
        store.files["a.bak"] = "ffffffff|yyy"
        with self.assertRaises(SaveError):
            store.load("a")

    def test_truncated_main_falls_back(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        store.files["a.dat"] = store.files["a.dat"][:6]
        self.assertEqual(store.load("a"), "one")

    def test_backup_rotates_with_intact_main(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        store.save("a", "three", 20)
        self.assertEqual(store.files["a.bak"], store._encode("two"))


class AutosaveTest(unittest.TestCase):
    def test_same_body_not_written(self):
        store = SlotStore()
        self.assertTrue(store.autosave("a", "same", 0))
        self.assertFalse(store.autosave("a", "same", 5000))
        self.assertEqual(store.writes, 1)

    def test_interval_throttle(self):
        store = SlotStore(interval_ms=1000)
        self.assertTrue(store.autosave("a", "x", 0))
        self.assertFalse(store.autosave("a", "y", 500))
        self.assertTrue(store.autosave("a", "y", 1000))
        self.assertEqual(store.writes, 2)

    def test_repeated_autosave_loads_last_body(self):
        store = SlotStore()
        for tick in range(100):
            store.autosave("a", "same", tick)
        self.assertEqual(store.writes, 1)
        self.assertEqual(store.load("a"), "same")

    def test_scale_only_writes_on_change(self):
        store = SlotStore()
        for index in range(1000000):
            body = "body" if index == 999999 else "same"
            store.autosave("a", body, index * 1000)
        self.assertEqual(store.writes, 2)
        self.assertEqual(store.load("a"), "body")


class EvictionTest(unittest.TestCase):
    def test_evicts_oldest_beyond_max_slots(self):
        store = SlotStore(max_slots=3)
        for index in range(5):
            store.save("s%d" % index, "data-%d" % index, index * 10)
        self.assertEqual(len(store.slots()), 3)
        self.assertEqual(store.evicted, 2)
        self.assertEqual(store.slots(), ["s4", "s3", "s2"])

    def test_evicted_slot_files_removed(self):
        store = SlotStore(max_slots=2)
        store.save("a", "1", 0)
        store.save("a", "2", 1)
        store.save("b", "1", 2)
        store.save("c", "1", 3)
        self.assertNotIn("a.dat", store.files)
        self.assertNotIn("a.bak", store.files)
        with self.assertRaises(SaveError):
            store.load("a")

    def test_rewrite_existing_slot_no_eviction(self):
        store = SlotStore(max_slots=2)
        store.save("a", "1", 0)
        store.save("b", "1", 1)
        store.save("a", "2", 2)
        self.assertEqual(store.evicted, 0)
        self.assertEqual(store.slots(), ["a", "b"])


class ChecksumTest(unittest.TestCase):
    def test_record_format_crc32(self):
        import zlib
        store = SlotStore()
        store.save("a", "one", 0)
        head, body = store.files["a.dat"].split("|", 1)
        self.assertEqual(body, "one")
        self.assertEqual(head, "%08x" % zlib.crc32(b"one"))

    def test_empty_body_checksum(self):
        store = SlotStore()
        store.save("a", "", 0)
        self.assertEqual(store.files["a.dat"], "00000000|")
        self.assertEqual(store.load("a"), "")


if __name__ == "__main__":
    unittest.main()
