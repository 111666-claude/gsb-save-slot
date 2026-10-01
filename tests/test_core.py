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


if __name__ == "__main__":
    unittest.main()
