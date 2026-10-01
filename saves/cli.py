"""命令行入口：跑存档槽样例。"""

import argparse

from .core import SaveError, SlotStore


def build_parser():
    parser = argparse.ArgumentParser(prog="save-slot", description="存档槽")
    parser.add_argument("--sample", default="crash",
                        help="crash / corrupt / autosave / slots / crc / scale")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "crash":
        store = SlotStore()
        store.save("a", "one", 0)
        store.crash_after = 11
        try:
            store.save("a", "two", 10)
        except SaveError:
            pass
        print("value=%r" % store.load("a"))
    elif args.sample == "corrupt":
        store = SlotStore()
        store.save("a", "one", 0)
        store.save("a", "two", 10)
        store.files["a.dat"] = "00000000|xxx"
        print("value=%r" % store.load("a"))
    elif args.sample == "autosave":
        store = SlotStore()
        for tick in range(100):
            store.autosave("a", "same", tick)
        print("writes=%d" % store.writes)
    elif args.sample == "slots":
        store = SlotStore(max_slots=3)
        for index in range(5):
            store.save("s%d" % index, "data-%d" % index, index * 10)
        print("size=%d evicted=%d" % (len(store.slots()), store.evicted))
    elif args.sample == "crc":
        import zlib
        store = SlotStore()
        store.save("a", "one", 0)
        stored = int(store.files["a.dat"].split("|", 1)[0], 16)
        print("matches=%s" % str(stored == zlib.crc32(b"one")).lower())
    elif args.sample == "scale":
        store = SlotStore()
        for _ in range(200000):
            store.autosave("a", "same", 0)
        print("writes=%d" % store.writes)
    else:
        raise SystemExit("需要 --sample crash|corrupt|autosave|slots|crc|scale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
