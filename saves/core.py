"""存档槽：写入、读取、备份与自动存档节流。

缺陷：直接覆盖主档、没有备份轮转、读档不校验、自动存档不节流、槽位上限不生效、
校验和用长度顶替。
"""


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
        return len(data)

    def _encode(self, data):
        return "%08x|%s" % (self._checksum(data), data)

    def _decode(self, payload):
        return payload.split("|", 1)[1]

    def save(self, slot, data, now_ms=0):
        """写档。"""
        payload = self._encode(data)
        if self.crash_after is not None:
            self.files[slot + ".dat"] = payload[:self.crash_after]
            self.crash_after = None
            raise SaveError("写档中断")
        self.files[slot + ".dat"] = payload
        self.last_write[slot] = now_ms
        self.writes += 1
        return True

    def load(self, slot):
        """读档。"""
        name = slot + ".dat"
        if name not in self.files:
            raise SaveError("存档不存在")
        self.last_body[slot] = self.files[name]
        return self._decode(self.files[name])

    def autosave(self, slot, data, now_ms=0):
        """自动存档。"""
        self.save(slot, data, now_ms)
        return True

    def slots(self):
        """按最后写入时间从新到旧返回槽位名。"""
        return sorted(self.last_write, key=lambda s: -self.last_write[s])
