"""存档槽：写入、读取、备份与自动存档节流。"""

import zlib


class SaveError(Exception):
    """存档读写失败。"""


class SlotStore:
    """用内存文件表模拟存档目录。"""

    def __init__(self, max_slots=3, interval_ms=1000):
        self.max_slots = max_slots
        self.interval_ms = interval_ms
        self.files = {}
        self.last_write = {}
        self.last_body = {}
        self.crash_after = None
        self.writes = 0
        self.evicted = 0
        self.fallbacks = 0

    def _checksum(self, data):
        return zlib.crc32(data.encode("utf-8"))

    def _encode(self, data):
        return "%08x|%s" % (self._checksum(data), data)

    def _decode(self, payload):
        """校验并解出正文；损坏时返回 None。"""
        head, sep, body = payload.partition("|")
        if not sep or len(head) != 8:
            return None
        try:
            stored = int(head, 16)
        except ValueError:
            return None
        if stored != self._checksum(body):
            return None
        return body

    def save(self, slot, data, now_ms=0):
        """写档：先写临时名再替换主档，替换前把完好主档轮转成备份。"""
        payload = self._encode(data)
        tmp = slot + ".tmp"
        dat = slot + ".dat"
        bak = slot + ".bak"
        if self.crash_after is not None:
            self.files[tmp] = payload[:self.crash_after]
            self.crash_after = None
            raise SaveError("写档中断")
        self.files[tmp] = payload
        current = self.files.get(dat)
        if current is not None and self._decode(current) is not None:
            self.files[bak] = current
        self.files[dat] = self.files.pop(tmp)
        self.last_write[slot] = now_ms
        self.last_body[slot] = data
        self.writes += 1
        self._evict()
        return True

    def _evict(self):
        """槽位超出上限时淘汰最后写入最早的槽。"""
        while len(self.last_write) > self.max_slots:
            oldest = min(self.last_write, key=lambda s: self.last_write[s])
            del self.last_write[oldest]
            self.last_body.pop(oldest, None)
            for suffix in (".dat", ".bak", ".tmp"):
                self.files.pop(oldest + suffix, None)
            self.evicted += 1

    def load(self, slot):
        """读档：主档校验失败就回退备份，两份都坏才抛 SaveError。"""
        dat = self.files.get(slot + ".dat")
        if dat is not None:
            body = self._decode(dat)
            if body is not None:
                return body
        bak = self.files.get(slot + ".bak")
        if bak is not None:
            body = self._decode(bak)
            if body is not None:
                self.fallbacks += 1
                return body
        raise SaveError("存档不存在或已损坏")

    def autosave(self, slot, data, now_ms=0):
        """自动存档：正文相同或距上次落盘不足 interval_ms 时不写。"""
        if slot in self.last_write and self.last_body.get(slot) == data:
            return False
        last = self.last_write.get(slot)
        if last is not None and now_ms - last < self.interval_ms:
            return False
        return self.save(slot, data, now_ms)

    def slots(self):
        """按最后写入时间从新到旧返回槽位名。"""
        return sorted(self.last_write, key=lambda s: -self.last_write[s])
