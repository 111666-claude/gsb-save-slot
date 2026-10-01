# save-slot

存档槽：把每个槽位写成「校验和 + 正文」的一条记录，支持备份轮转、损坏回退与
自动存档节流。只用 Python 标准库。

```
python3 -m saves.cli --sample crash
python3 -m saves.cli --sample corrupt
python3 -m saves.cli --sample autosave
python3 -m saves.cli --sample slots
python3 -m saves.cli --sample crc
python3 -m saves.cli --sample scale
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **记录格式**：每条存档是 `8 位十六进制校验和 + "|" + 正文`，校验和取正文的
  CRC32（标准库 `zlib.crc32`），小写十六进制、左补零到 8 位。
- **原子写入**：先写临时名 `<slot>.tmp`，写完整再替换 `<slot>.dat`；
  中途失败（`crash_after` 注入）时 `<slot>.dat` 必须还是上一份完整存档。
- **备份轮转**：替换主档之前，把当前这份完好的主档复制成 `<slot>.bak`。
- **读档校验**：读 `<slot>.dat` 必须核对校验和；对不上就回退读 `<slot>.bak`，
  把 `fallbacks` 加一；两份都坏才抛 `SaveError`。
- **自动存档**：正文与上次落盘内容相同，或者距上次落盘不足 `interval_ms`，
  都不落盘；返回值表示这次是否真的写了。
- **槽位上限**：同时存在的槽位不超过 `max_slots`，超出时淘汰最后写入时间最早
  的那个槽，`evicted` 加一。
- **不变量**：任何一次写档中断后 `load(slot)` 仍能拿到上一份完整数据；
  同一份正文重复自动存档不增加 `writes`。
- **规模**：100 万次自动存档调用只在正文变化时落盘，内存 O(槽位数 + 一份存档)。

## 输出契约（不改格式）

```
value=..
writes=..
size=.. evicted=..
matches=..
```

## 目录

```
saves/core.py   写入、备份、读取与节流
saves/cli.py    命令行入口
tests/          unittest 用例
```
