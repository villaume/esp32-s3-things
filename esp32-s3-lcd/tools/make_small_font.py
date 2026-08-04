"""Derive vga1_16x16.py from vga1_16x32.py.

The 16x32 font shipped with this board is a 16x16 face doubled vertically
(each glyph row appears twice), so dropping every other row recovers the
original 16x16 face losslessly.

This has to be a real .py module on the device rather than something built at
runtime: the GC9A01 driver's text() is C code that calls
mp_obj_module_get_globals() on its font argument, so passing anything that is
not an actual module crashes the board with LoadProhibited.

    python3 tools/make_small_font.py
"""
import importlib.util

SRC, DST = "vga1_16x32.py", "vga1_16x16.py"

spec = importlib.util.spec_from_file_location("src", SRC)
src = importlib.util.module_from_spec(spec)
spec.loader.exec_module(src)

data = bytes(src.FONT)
glyphs = (src.LAST - src.FIRST) + 1
per_row = src.WIDTH // 8
stride = src.HEIGHT * per_row

for g in range(glyphs):
    gl = data[g * stride:(g + 1) * stride]
    for r in range(0, src.HEIGHT, 2):
        a = gl[r * per_row:(r + 1) * per_row]
        b = gl[(r + 1) * per_row:(r + 2) * per_row]
        if a != b:
            raise SystemExit(f"{SRC} is not vertically doubled (glyph {g}, row {r})")

out = bytearray()
for g in range(glyphs):
    gl = data[g * stride:(g + 1) * stride]
    for r in range(0, src.HEIGHT, 2):
        out += gl[r * per_row:(r + 1) * per_row]

height = src.HEIGHT // 2
lines = [f"WIDTH = {src.WIDTH}", f"HEIGHT = {height}",
         f"FIRST = {src.FIRST:#04x}", f"LAST = {src.LAST:#04x}", "_FONT = \\"]
chunk = height * per_row
for g in range(glyphs):
    lines.append(repr(bytes(out[g * chunk:(g + 1) * chunk])) + "\\")
lines += ["", "FONT = memoryview(_FONT)"]

with open(DST, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"wrote {DST}: {glyphs} glyphs, {len(out)} bytes")
