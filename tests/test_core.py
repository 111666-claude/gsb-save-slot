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


class RecordFormatTest(unittest.TestCase):
    def test_checksum_is_crc32_of_body(self):
        import zlib
        store = SlotStore()
        store.save("a", "one", 0)
        head, body = store.files["a.dat"].split("|", 1)
        self.assertEqual(body, "one")
        self.assertEqual(head, "%08x" % zlib.crc32(b"one"))

    def test_checksum_lowercase_zero_padded(self):
        store = SlotStore()
        store.save("a", "x", 0)
        head = store.files["a.dat"].split("|", 1)[0]
        self.assertEqual(len(head), 8)
        self.assertEqual(head, head.lower())
        int(head, 16)


class AtomicWriteTest(unittest.TestCase):
    def test_crash_keeps_previous_save(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.crash_after = 5
        with self.assertRaises(SaveError):
            store.save("a", "two", 10)
        self.assertEqual(store.load("a"), "one")

    def test_crash_writes_only_partial_tmp(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.crash_after = 4
        with self.assertRaises(SaveError):
            store.save("a", "two", 10)
        full = store._encode("two")
        self.assertEqual(store.files["a.tmp"], full[:4])
        self.assertEqual(store.files["a.dat"].split("|", 1)[1], "one")


class BackupFallbackTest(unittest.TestCase):
    def test_save_rotates_backup(self):
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        self.assertEqual(store.files["a.bak"].split("|", 1)[1], "one")

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
        store.files["a.dat"] = "garbage"
        store.files["a.bak"] = "garbage"
        with self.assertRaises(SaveError):
            store.load("a")


class AutosaveTest(unittest.TestCase):
    def test_same_body_not_written_again(self):
        store = SlotStore()
        self.assertTrue(store.autosave("a", "same", 0))
        for tick in range(1, 100):
            self.assertFalse(store.autosave("a", "same", tick))
        self.assertEqual(store.writes, 1)

    def test_interval_throttles_changed_body(self):
        store = SlotStore(interval_ms=1000)
        self.assertTrue(store.autosave("a", "one", 0))
        self.assertFalse(store.autosave("a", "two", 500))
        self.assertEqual(store.writes, 1)
        self.assertTrue(store.autosave("a", "two", 1000))
        self.assertEqual(store.writes, 2)

    def test_changed_body_after_interval_writes(self):
        store = SlotStore(interval_ms=10)
        store.autosave("a", "one", 0)
        self.assertTrue(store.autosave("a", "two", 10))
        self.assertEqual(store.load("a"), "two")


class EvictionTest(unittest.TestCase):
    def test_evicts_oldest_beyond_max_slots(self):
        store = SlotStore(max_slots=3)
        for index in range(5):
            store.save("s%d" % index, "data-%d" % index, index * 10)
        self.assertEqual(store.slots(), ["s4", "s3", "s2"])
        self.assertEqual(store.evicted, 2)

    def test_evicted_slot_files_removed(self):
        store = SlotStore(max_slots=2)
        store.save("a", "1", 0)
        store.save("a", "2", 1)
        store.save("b", "1", 2)
        store.save("c", "1", 3)
        with self.assertRaises(SaveError):
            store.load("a")
        self.assertNotIn("a.dat", store.files)
        self.assertNotIn("a.bak", store.files)


if __name__ == "__main__":
    unittest.main()
