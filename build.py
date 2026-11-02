"""Build Medal & Super Credit Markers into a mod zip (Modocracy, HD2 Arsenal, HD2MM).

    python build.py     -> dist/Medal & Super Credit Markers v<version>.zip

One plain-text Lua resource, mods/codex/medal_credit_markers, and its icons as textures of the same patch, which Chef
Shared Loader finds, starts and draws. The archive writer (SCAFFOLD, murmur64, write_module) is taken from Boot Mod
Loader's build.py, https://github.com/pat-pat-patrick/boot-mod-loader (MIT); the texture rows come from Extended Pickup
Icons Range, the sister mod. Nothing here is shared with it at run time: its own GUID, resource, globals, log and keys.
"""
import json
import os
import re
import shutil
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "src", "medal_credit_markers.lua")
ICON = os.path.join(HERE, "src", "icon.png")
DIST = os.path.join(HERE, "dist")
NAME = "Medal & Super Credit Markers"
FOLDER = "Addon"
RESOURCE = "mods/codex/medal_credit_markers"
LUA_SOURCE_FLAG = 2
ICON_TABLE = "{}"   # the baked icons' Lua table (icon_textures), set by build()

SCAFFOLD = bytes.fromhex(
    "110000f0010000000100000000000000ce09f5f4000000006e0b41bab993fecf0040170300000000"
    "00cc5600000000000000000000000000000000000000000000000000000000000000000000000000"
    "e217d12cfa8d4ea101000000000000001000000040000000b1d0e27de00d175ce217d12cfa8d4ea1"
    "b8000000000000000000000000000000000000000000000000b000000000000000c1070000000000"
    "f3af00000000000000000000100000004000000001000000")

MANIFEST = {
    "Version": 1,
    "Guid": "656499dd-f565-4308-a346-7740f1e662db",
    "Name": NAME,
    "Description": "Medals and super credits marked from far away, with the game's icons and their distance. "
                   "Requires Chef Shared Loader.",
    "IconPath": "icon.png",
    "Options": [{"Name": NAME, "Description": "Requires Chef Shared Loader.", "Include": [FOLDER]}],
}

README = """Medal & Super Credit Markers v{version}
================================

Medals and super credits lying about the map, marked from far away with the game's own
currency icons and their distance.

Press F9 in the game (Chef Shared Loader's options menu) and pick Medal & Super Credit Markers:
show medals, show super credits, distance (2000 m: a whole map), show distance.

Requires Chef Shared Loader. Give it the highest priority in your mod manager (in Arsenal, by
default, the bottom of the list). Works beside Extended Pickup Icons Range.
Log: %APPDATA%\\Arrowhead\\Helldivers2\\MedalCreditMarkers.log
"""


def murmur64(data, seed=0):
    """MurmurHash64A, as the engine names resources."""
    m, r, mask = 0xc6a4a7935bd1e995, 47, 0xFFFFFFFFFFFFFFFF
    h = (seed ^ (len(data) * m)) & mask
    whole = len(data) - len(data) % 8
    for at in range(0, whole, 8):
        k = int.from_bytes(data[at:at + 8], "little")
        k = (k * m) & mask
        k ^= k >> r
        k = (k * m) & mask
        h = ((h ^ k) * m) & mask
    tail = data[whole:]
    if tail:
        h ^= int.from_bytes(tail, "little")
        h = (h * m) & mask
    h ^= h >> r
    h = (h * m) & mask
    h ^= h >> r
    return h


LUA_TYPE = murmur64(b"lua")
TEXTURE_TYPE = murmur64(b"texture")


def texture_part(width, height):
    """A texture resource's main part for width x height RGBA8 pixels, one mip, the pixels in .gpu_resources: the
    engine's 192-byte texture header (no streaming), then a DDS header with the DX10 extension (R8G8B8A8_UNORM, 2D)."""
    engine = struct.pack("<III", 0, 0, 0xFFFFFFFF) + bytes(180)
    flags = 0x1 | 0x2 | 0x4 | 0x8 | 0x1000          # caps, height, width, pitch, pixel format
    dds = b"DDS " + struct.pack("<7I", 124, flags, height, width, width * 4, 0, 1) + bytes(44)
    dds += struct.pack("<2I4s5I", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)   # pixel format: FourCC DX10
    dds += struct.pack("<5I", 0x1000, 0, 0, 0, 0)                   # caps: texture
    dds += struct.pack("<5I", 28, 3, 0, 1, 0)                       # DXGI R8G8B8A8_UNORM, a 2D texture, one of it
    return engine + dds


def write_module(out_dir, resource_name, source, flag=LUA_SOURCE_FLAG, archive="9ba626afa44a3aa3.patch_0",
                 textures=()):
    """One Lua resource as a patch archive (plus its .gpu_resources and .stream); textures: (resource name, width,
    height, RGBA8 pixels) after it (write_with_textures). Without textures, the Lua-only archive."""
    encoded = source if isinstance(source, bytes) else source.encode("utf-8")
    payload = struct.pack("<2I", len(encoded), flag) + encoded
    if textures:
        return write_with_textures(out_dir, resource_name, payload, textures, archive)
    out = bytearray(SCAFFOLD)
    row = 0x48 + 32
    struct.pack_into("<3Q", out, row, murmur64(resource_name.encode("utf-8")), LUA_TYPE, len(SCAFFOLD))
    struct.pack_into("<I", out, row + 56, len(payload))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, archive)
    with open(path, "wb") as f:
        f.write(bytes(out) + payload)
    open(path + ".gpu_resources", "wb").close()
    open(path + ".stream", "wb").close()
    return path


def write_with_textures(out_dir, resource_name, payload, textures, archive):
    """The Lua row as in SCAFFOLD (its header bytes 12..72 too), then a texture type row and a row per texture, their
    pixels in .gpu_resources (64-byte aligned)."""
    n = 1 + len(textures)
    head = struct.pack("<III", 0xF0000011, 2, n) + SCAFFOLD[12:72]
    head += struct.pack("<QQQII", 0, LUA_TYPE, 1, 16, 64)
    head += struct.pack("<QQQII", 0, TEXTURE_TYPE, len(textures), 16, 64)
    cursor = len(head) + 80 * n
    rows, body, gpu = b"", b"", bytearray()
    rows += struct.pack("<7Q6I", murmur64(resource_name.encode("utf-8")), LUA_TYPE, cursor, 0, 0, 0, 0,
                        len(payload), 0, 0, 16, 64, 1)
    body += payload
    cursor += len(payload)
    for k, (name, width, height, pixels) in enumerate(textures, 2):
        pad = -cursor % 16
        body += bytes(pad)
        cursor += pad
        part = texture_part(width, height)
        gpu += bytes(-len(gpu) % 64)
        rows += struct.pack("<7Q6I", murmur64(name.encode("utf-8")), TEXTURE_TYPE, cursor, 0, len(gpu), 0, 0,
                            len(part), 0, len(pixels), 16, 64, k)
        gpu += pixels
        body += part
        cursor += len(part)
    out = head + rows + body
    out += bytes(-len(out) % 16)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, archive)
    with open(path, "wb") as f:
        f.write(out)
    with open(path + ".gpu_resources", "wb") as f:
        f.write(bytes(gpu))
    open(path + ".stream", "wb").close()
    return path


def icon_textures():
    """The baked icons as textures, and the Lua table the mod reads them from: icon name -> its sizes, smallest first,
    each {size along the longer side, texture id (hex), width, height}."""
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import make_icons
    textures, table = [], {}
    for name, size, width, height, rgba in make_icons.baked():
        resource = "%s/icons/%s_%d" % (RESOURCE, name, size)
        textures.append((resource, width, height, rgba))
        table.setdefault(name, []).append("{%d, '%016x', %d, %d}" % (size, murmur64(resource.encode("utf-8")), width, height))
    lua = "{\n" + "".join("    %s = {%s},\n" % (name, ", ".join(rows)) for name, rows in sorted(table.items())) + "}"
    return textures, lua


def built_source():
    """The mod's Lua with the icon table in its slot."""
    with open(SOURCE, encoding="utf-8") as f:
        source = f.read()
    if not source.startswith("-- HD2-Addon: " + RESOURCE + "\n-- HD2-Keep-On-Crash: yes\n"):
        raise SystemExit("the first lines must declare " + RESOURCE + " and keep-on-crash")
    if source.count('"@ICONS@"') != 1:
        raise SystemExit("no single \"@ICONS@\" slot")
    return source.replace('"@ICONS@"', ICON_TABLE)


def build():
    global ICON_TABLE
    textures, ICON_TABLE = icon_textures()
    source = built_source()
    version = re.search(r"local VERSION = '([^']+)'", source).group(1)
    out_dir = os.path.join(DIST, "%s v%s" % (NAME, version))
    if os.path.exists(out_dir):
        raise SystemExit("%s exists: bump VERSION or delete it" % out_dir)
    write_module(os.path.join(out_dir, FOLDER), RESOURCE, source, textures=textures)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README.format(version=version))
    shutil.copyfile(ICON, os.path.join(out_dir, "icon.png"))
    zip_path = out_dir + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _dirs, files in os.walk(out_dir):
            for name in sorted(files):
                full = os.path.join(base, name)
                z.write(full, os.path.relpath(full, out_dir))
    print("wrote %s" % zip_path)


if __name__ == "__main__":
    sys.exit(build())
