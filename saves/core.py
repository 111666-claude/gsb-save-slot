"""存档槽：原子写入、备份轮转、读档校验与自动存档节流。"""

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
        return zlib.crc32(data.encode("utf-8")) & 0xFFFFFFFF

    def _encode(self, data):
        return "%08x|%s" % (self._checksum(data), data)

    def _verify(self, payload):
        """核对校验和，返回正文；记录损坏或格式不对时返回 None。"""
        if not isinstance(payload, str) or "|" not in payload:
            return None
        head, body = payload.split("|", 1)
        if len(head) != 8:
            return None
        try:
            expected = int(head, 16)
        except ValueError:
            return None
        if self._checksum(body) != expected:
            return None
        return body

    def _evict(self, slot):
        for suffix in (".dat", ".bak", ".tmp"):
            self.files.pop(slot + suffix, None)
        self.last_write.pop(slot, None)
        self.last_body.pop(slot, None)
        self.evicted += 1

    def save(self, slot, data, now_ms=0):
        """原子写档：先写临时名，再轮转备份，最后替换主档。"""
        payload = self._encode(data)
        tmp_name = slot + ".tmp"
        dat_name = slot + ".dat"
        bak_name = slot + ".bak"

        if self.crash_after is not None:
            self.files[tmp_name] = payload[:self.crash_after]
            self.crash_after = None
            raise SaveError("写档中断")
        self.files[tmp_name] = payload

        existing = set(self.last_write)
        intact = self._verify(self.files.get(dat_name))
        if intact is not None:
            self.files[bak_name] = self.files[dat_name]

        self.files[dat_name] = self.files.pop(tmp_name)
        self.last_write[slot] = now_ms
        self.last_body[slot] = data
        self.writes += 1

        while slot not in existing and len(self.last_write) > self.max_slots:
            victim = min(self.last_write, key=self.last_write.get)
            self._evict(victim)
        return True

    def load(self, slot):
        """读档并核对校验和，主档损坏时回退备份。"""
        body = self._verify(self.files.get(slot + ".dat"))
        if body is not None:
            return body
        backup = self._verify(self.files.get(slot + ".bak"))
        if backup is not None:
            self.fallbacks += 1
            return backup
        raise SaveError("存档损坏或不存在")

    def autosave(self, slot, data, now_ms=0):
        """节流自动存档，返回是否真的落盘。"""
        if data == self.last_body.get(slot):
            return False
        last = self.last_write.get(slot)
        if last is not None and now_ms - last < self.interval_ms:
            return False
        self.save(slot, data, now_ms)
        return True

    def slots(self):
        """按最后写入时间从新到旧返回槽位名。"""
        return sorted(self.last_write, key=lambda s: -self.last_write[s])
