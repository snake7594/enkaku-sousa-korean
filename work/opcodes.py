"""The interpreter's instruction-length rule, in one place.

Recovered from the two executors the main loop at 0x0884A9A4 calls:

  0x0884A030  the command executor.  Each handler ends with
                  lw $v1, 17016($a0) / addiu $v1, $v1, N / sw $v1, 17016($a0)
              so N -- the whole instruction length -- is written down in the code.

  0x0884A000  the default path.  It advances by $t0, the length the token decoder at
              0x0884BE84 returned, which is 2 for a Shift-JIS lead byte and 1 otherwise.
              A code with no handler is therefore an ordinary character, not a gap in
              the table.  This is what four rounds of statistical guessing never saw.

Both layers of the stream -- text and commands -- go through the same decoder, so one
rule covers the lot.
"""

from __future__ import annotations

# code -> total instruction length, read out of the handlers at 0x0884A030
TABLE = {
    0x0C: 1, 0x0F: 2, 0x10: 1, 0x11: 1, 0x12: 1, 0x16: 2,
    0x18: 3, 0x19: 3, 0x1A: 1, 0x1B: 3, 0x1C: 1, 0x1E: 5,
}

# handled by 0x0884A7C8, which never touches the script pointer: they end the loop and
# the caller steps over them, so they cost their own byte and nothing more
TERMINATORS = {0x00, 0x13, 0x14, 0x15}

RUBY = 0x0F


def token_length(code: int) -> int:
    """The decoder at 0x0884BE84: two bytes for a Shift-JIS lead, otherwise one."""
    return 2 if (0x81 <= code <= 0x9F or 0xE0 <= code <= 0xFC) else 1


def step(plain: bytes, pos: int, in_ruby: bool = False) -> tuple[int, bool]:
    """Advance one instruction.  Returns the next position and the new ruby state.

    Ruby is the one code whose length depends on state: `0F <digit> <reading> 0F` opens
    with a digit operand and closes without one, so the opening form is two bytes and the
    closing form is one.  A flat table entry cannot express that.
    """
    code = plain[pos]
    if code == RUBY:
        return (pos + 1, False) if in_ruby else (pos + 2, True)
    if code in TABLE:
        return pos + TABLE[code], in_ruby
    if code in TERMINATORS:
        return pos + 1, in_ruby
    return pos + token_length(code), in_ruby


REF = 0x01          # `01 <u32>` -- absolute offset into the stream
LITERAL = 0x10      # `10 <u32>` -- immediate value, never an address
WIDE = 5

# The MIPS handler for 0x10 advances the script pointer by one byte, and the emulator agrees:
# on a healthy title screen the engine's own pointer sat at stream offset 0x3763E, which is
# the third byte of what the five-byte reading treats as a single instruction.  That reading
# was adopted because it raised reference resolution from 79% to 96% -- a statistic allowed
# to overrule the code, which is exactly backwards.  Set True only to reproduce the old
# behaviour for comparison.
WIDE_LITERAL = False


def text_flags(plain: bytes, blocks: list) -> bytearray:
    """One byte per position, set where that byte is inside a text block.

    Both 0x01 and 0x10 mean something different inside text than outside it, so the parse
    needs to know which side of that line it is on.
    """
    flags = bytearray(len(plain))
    for block in blocks:
        flags[block.text:block.text_end] = b"\x01" * (block.text_end - block.text)
    return flags


def parse(plain: bytes, start: int, stop: int, flags: bytearray) -> list:
    """The canonical parse: (position, code, size) for every instruction.

    Outside text, 0x01 and 0x10 both carry a four-byte operand.  Inside text they are
    ordinary characters.  Getting 0x10 wrong is what made 21% of references resolve to
    nothing: `09 10 01 00 00 00` is one six-byte instruction, and a parse that walks into
    it finds an `01` that was never an instruction and invents a reference from the
    literal's bytes.
    """
    out, pos, in_ruby = [], start, False
    wide = {REF} if not WIDE_LITERAL else {REF, LITERAL}
    while pos < stop:
        code = plain[pos]
        if code in wide and not flags[pos] and pos + WIDE <= stop:
            out.append((pos, code, WIDE))
            pos += WIDE
        else:
            nxt, in_ruby = step(plain, pos, in_ruby)
            out.append((pos, code, nxt - pos))
            pos = nxt
    return out


def boundaries(plain: bytes, start: int, stop: int) -> set[int]:
    """Every instruction boundary the walk visits between `start` and `stop`."""
    seen = {start}
    pos, in_ruby = start, False
    while pos < stop:
        pos, in_ruby = step(plain, pos, in_ruby)
        seen.add(pos)
    return seen


def lands_on(plain: bytes, start: int, target: int) -> bool:
    """Whether walking from `start` hits `target` exactly rather than stepping over it."""
    pos, in_ruby = start, False
    while pos < target:
        nxt, in_ruby = step(plain, pos, in_ruby)
        if nxt <= pos:
            return False
        pos = nxt
    return pos == target
