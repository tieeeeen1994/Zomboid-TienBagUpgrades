"""Read and write binary FBX 7.x files as a tree of nodes, keeping everything not touched byte for byte.

A node is a list [name, props, children, sentinel]:
  props     list of (type code, value); arrays keep their raw bytes until changed (value = ("raw", encoding,
            count, bytes)), so an unchanged file writes back identical
  children  list of nodes
  sentinel  whether the node ends with the 13 (or 25) zero byte null record

make_models.py takes a vanilla world item FBX as the template (its header, global settings, model transforms,
material and connections) and replaces only the geometry, so the game loads our mesh exactly the way it loads the
vanilla one.
"""

import struct
import zlib

_SCALAR = {"Y": "<h", "C": "<b", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}
_ARRAY = {"f": "f", "d": "d", "l": "q", "b": "b", "i": "i", "c": "B"}
HEADER = b"Kaydara FBX Binary  \x00\x1a\x00"


class Fbx:
    def __init__(self, version, nodes, footer):
        self.version = version
        self.nodes = nodes
        self.footer = footer

    def find(self, *path):
        """First node down a path of names, e.g. find("Objects", "Geometry")."""
        level = self.nodes
        node = None
        for name in path:
            node = next(n for n in level if n[0] == name)
            level = node[2]
        return node


def child(node, name):
    return next(c for c in node[2] if c[0] == name)


# --------------------------------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------------------------------

def _read_node(data, off, version):
    wide = version >= 7500
    if wide:
        end, nprops, _ = struct.unpack_from("<QQQ", data, off)
        off += 24
    else:
        end, nprops, _ = struct.unpack_from("<III", data, off)
        off += 12
    name_len = data[off]
    off += 1
    name = data[off:off + name_len].decode("utf-8", "replace")
    off += name_len
    if end == 0:
        return None, off

    props = []
    for _ in range(nprops):
        kind = chr(data[off])
        off += 1
        if kind in _SCALAR:
            fmt = _SCALAR[kind]
            props.append((kind, struct.unpack_from(fmt, data, off)[0]))
            off += struct.calcsize(fmt)
        elif kind in _ARRAY:
            count, encoding, length = struct.unpack_from("<III", data, off)
            off += 12
            props.append((kind, ("raw", encoding, count, data[off:off + length])))
            off += length
        elif kind in "SR":
            length = struct.unpack_from("<I", data, off)[0]
            off += 4
            props.append((kind, data[off:off + length]))
            off += length
        else:
            raise ValueError("unknown FBX property type %r" % kind)

    children = []
    sentinel = off < end
    while off < end:
        node, off = _read_node(data, off, version)
        if node is None:
            break
        children.append(node)
    return [name, props, children, sentinel], end


def read(path):
    data = open(path, "rb").read()
    if not data.startswith(HEADER):
        raise ValueError("not a binary FBX: " + path)
    version = struct.unpack_from("<I", data, 23)[0]
    off = 27
    nodes = []
    while True:
        node, off = _read_node(data, off, version)
        if node is None:
            break
        nodes.append(node)
    return Fbx(version, nodes, data[off:])


def array_values(prop):
    kind, value = prop
    if isinstance(value, tuple) and value[0] == "raw":
        _, encoding, count, raw = value
        if encoding == 1:
            raw = zlib.decompress(raw)
        return list(struct.unpack("<%d%s" % (count, _ARRAY[kind]), raw))
    return list(value)


# --------------------------------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------------------------------

def _props_bytes(props):
    out = bytearray()
    for kind, value in props:
        out += kind.encode()
        if kind in _SCALAR:
            out += struct.pack(_SCALAR[kind], value)
        elif kind in _ARRAY:
            if isinstance(value, tuple) and value[0] == "raw":
                _, encoding, count, raw = value
            else:
                plain = struct.pack("<%d%s" % (len(value), _ARRAY[kind]), *value)
                encoding, count, raw = 1, len(value), zlib.compress(plain)
            out += struct.pack("<III", count, encoding, len(raw)) + raw
        elif kind in "SR":
            out += struct.pack("<I", len(value)) + value
    return bytes(out)


def _write_node(node, out, version):
    name, props, children, sentinel = node
    wide = version >= 7500
    head = 24 if wide else 12
    null = b"\x00" * (25 if wide else 13)
    start = len(out)
    pb = _props_bytes(props)
    out += b"\x00" * head
    out += bytes([len(name)]) + name.encode()
    out += pb
    for c in children:
        _write_node(c, out, version)
    if children or sentinel:
        out += null
    end = len(out)
    fmt = "<QQQ" if wide else "<III"
    struct.pack_into(fmt, out, start, end, len(props), len(pb))


def write(fbx, path):
    out = bytearray(HEADER + struct.pack("<I", fbx.version))
    for node in fbx.nodes:
        _write_node(node, out, fbx.version)
    out += b"\x00" * (25 if fbx.version >= 7500 else 13)
    out += fbx.footer
    with open(path, "wb") as f:
        f.write(out)
