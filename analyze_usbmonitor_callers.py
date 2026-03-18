#!/usr/bin/env python3
import struct

import dnfile

TARGET_METHODS = {113, 114, 459, 461}


def method_body(pe: dnfile.dnPE, rva: int) -> bytes:
    if not rva:
        return b""
    data = pe.__data__
    offset = pe.get_offset_from_rva(rva)
    if offset >= len(data):
        return b""

    first = data[offset]
    fmt = first & 0x3
    if fmt == 2:
        size = first >> 2
        return data[offset + 1 : offset + 1 + size]
    if fmt == 3:
        flags_size = struct.unpack_from("<H", data, offset)[0]
        header_dwords = (flags_size >> 12) & 0xF
        code_size = struct.unpack_from("<I", data, offset + 4)[0]
        header_size = header_dwords * 4
        return data[offset + header_size : offset + header_size + code_size]
    return b""


def main() -> int:
    pe = dnfile.dnPE("Turing_Files_35/UsbMonitor.exe")
    methods = pe.net.mdtables.MethodDef.rows
    types = pe.net.mdtables.TypeDef.rows

    ownership = {}
    for type_index, trow in enumerate(types, start=1):
        type_name = getattr(trow.TypeName, "value", f"Type_{type_index}")
        type_ns = getattr(trow.TypeNamespace, "value", "")
        full_type = f"{type_ns}.{type_name}".strip(".")
        for md_index in (getattr(trow, "MethodList", []) or []):
            row_index = getattr(md_index, "row_index", None)
            if row_index is not None:
                ownership[row_index] = full_type

    def full_method_name(idx: int) -> str:
        m = methods[idx - 1]
        mname = getattr(m.Name, "value", f"Method_{idx}")
        return f"{ownership.get(idx, '?')}::{mname}"

    target_tokens = {0x06000000 | idx for idx in TARGET_METHODS}

    print("Target methods:")
    for idx in sorted(TARGET_METHODS):
        print(idx, hex(0x06000000 | idx), full_method_name(idx), "rva", hex(methods[idx - 1].Rva))

    print("\nDirect callers:")
    for idx, mrow in enumerate(methods, start=1):
        body = method_body(pe, mrow.Rva)
        if not body:
            continue
        pos = 0
        seen = set()
        while pos < len(body) - 4:
            op = body[pos]
            if op in (0x28, 0x6F):
                token = int.from_bytes(body[pos + 1 : pos + 5], "little")
                if token in target_tokens:
                    seen.add(token)
                pos += 5
            else:
                pos += 1
        if seen:
            called = ", ".join(hex(t) for t in sorted(seen))
            print(f"{idx:4d} {full_method_name(idx)} -> {called}")

    print("\nWrite-method body preview:")
    write_idx = 113
    write_body = method_body(pe, methods[write_idx - 1].Rva)
    print("len", len(write_body))
    print(write_body[:128].hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
