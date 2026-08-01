"""Compile the script into paginated, word-wrapped byte streams.

On-ROM format, one message: a stream of font tile indices (0..63) with control
codes $FE = newline, $FD = page break, $FF = end.

Banking: message id -> bank BANK_TEXT_BASE + (id >> 6); each text bank begins
with its own 64-entry address table, so no index table is needed in the fixed
engine bank.
"""
import font

COLS = 30
LINES = 4
NEWLINE = 0xFE
PAGEBRK = 0xFD
END = 0xFF
MSGS_PER_BANK = 64


def wrap(text):
    """-> list of pages, each a list of up to LINES strings of <= COLS chars."""
    pages = []
    lines = []
    cur = ""

    def flush_line():
        nonlocal cur, lines
        lines.append(cur)
        cur = ""
        if len(lines) == LINES:
            flush_page()

    def flush_page():
        nonlocal lines
        pages.append(lines)
        lines = []

    for para_i, para in enumerate(text.split("\f")):
        if para_i:
            if cur:
                flush_line()
            if lines:
                flush_page()
        for line_i, line in enumerate(para.split("\n")):
            if line_i and (cur or True):
                flush_line()
            for word in line.split(" "):
                if not word:
                    continue
                if len(word) > COLS:
                    raise ValueError(f"word too long: {word!r}")
                if not cur:
                    cur = word
                elif len(cur) + 1 + len(word) <= COLS:
                    cur += " " + word
                else:
                    flush_line()
                    cur = word
    if cur:
        flush_line()
    if lines:
        flush_page()
    return [p for p in pages if p]


def encode(text):
    pages = wrap(text)
    out = bytearray()
    for pi, page in enumerate(pages):
        if pi:
            out.append(PAGEBRK)
        for li, line in enumerate(page):
            if li:
                out.append(NEWLINE)
            out += bytes(font.encode(line))
    out.append(END)
    return bytes(out), len(pages)


def compile_all(messages):
    """messages: list of (ID, text) -> (ids, banks) where banks is a list of
    lists of (id, name, bytes)."""
    ids = {}
    banks = []
    for i, (name, text) in enumerate(messages):
        if name in ids:
            raise ValueError(f"duplicate message id {name}")
        ids[name] = i
        data, npages = encode(text)
        if npages > 3:
            raise ValueError(f"{name}: {npages} pages (max 3)")
        b = i // MSGS_PER_BANK
        while len(banks) <= b:
            banks.append([])
        banks[b].append((i, name, data))
    for b, entries in enumerate(banks):
        total = sum(len(d) for _, _, d in entries) + 2 * MSGS_PER_BANK
        if total > 8100:
            raise ValueError(f"text bank {b}: {total} bytes > 8100")
    return ids, banks


def emit(f, banks, base_bank):
    for b, entries in enumerate(banks):
        f.write(f'\n.segment "BANK{base_bank + b:02d}"\n')
        f.write(f"msg_tab_{b}:\n")
        have = {i % MSGS_PER_BANK: name for i, name, _ in entries}
        for slot in range(MSGS_PER_BANK):
            if slot in have:
                f.write(f"    .addr msg_{have[slot]}\n")
            else:
                f.write("    .addr 0\n")
        for _, name, data in entries:
            f.write(f"msg_{name}:\n")
            for j in range(0, len(data), 16):
                f.write("    .byte " +
                        ",".join(f"${x:02X}" for x in data[j:j + 16]) + "\n")
