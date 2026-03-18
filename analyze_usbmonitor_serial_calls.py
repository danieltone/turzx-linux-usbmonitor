#!/usr/bin/env python3
import struct
from collections import defaultdict

import dnfile


TARGET_METHODS = {
    "Write",
    "WriteLine",
    "Open",
    "Close",
    "set_BaudRate",
    "set_PortName",
}


def get_method_body_bytes(pe: dnfile.dnPE, rva: int) -> bytes:
    if not rva:
        return b""
    offset = pe.get_offset_from_rva(rva)
    data = pe.__data__
    if offset >= len(data):
        return b""

    first = data[offset]
    fmt = first & 0x3

    if fmt == 2:
        size = first >> 2
        return data[offset + 1 : offset + 1 + size]

    if fmt == 3:
        if offset + 12 > len(data):
            return b""
        flags_size = struct.unpack_from("<H", data, offset)[0]
        header_dwords = (flags_size >> 12) & 0xF
        code_size = struct.unpack_from("<I", data, offset + 4)[0]
        header_size = header_dwords * 4
        start = offset + header_size
        return data[start : start + code_size]

    return b""


def main() -> int:
    pe = dnfile.dnPE("Turing_Files_35/UsbMonitor.exe")

    member_ref_tokens: dict[int, tuple[str, str]] = {}
    for index, row in enumerate(pe.net.mdtables.MemberRef.rows, start=1):
        name = getattr(row.Name, "value", "") if getattr(row, "Name", None) else ""
        class_name = ""
        try:
            cls = row.Class
            if hasattr(cls, "row") and cls.row:
                class_row = cls.row
                namespace = getattr(getattr(class_row, "TypeNamespace", None), "value", "")
                type_name = getattr(getattr(class_row, "TypeName", None), "value", "")
                class_name = f"{namespace}.{type_name}".strip(".")
        except Exception:
            pass

        if "SerialPort" in class_name and name in TARGET_METHODS:
            token = 0x0A000000 | index
            member_ref_tokens[token] = (class_name, name)

    print(f"serial_member_tokens={len(member_ref_tokens)}")
    for token, pair in sorted(member_ref_tokens.items())[:20]:
        print(f"  {hex(token)} -> {pair[0]}::{pair[1]}")

    methods = pe.net.mdtables.MethodDef.rows
    types = pe.net.mdtables.TypeDef.rows

    ownership: dict[int, str] = {}
    for type_index, trow in enumerate(types, start=1):
        type_name = getattr(trow.TypeName, "value", f"Type_{type_index}")
        type_ns = getattr(trow.TypeNamespace, "value", "")
        full_type = f"{type_ns}.{type_name}".strip(".")

        method_list = getattr(trow, "MethodList", []) or []
        for md_index in method_list:
            row_index = getattr(md_index, "row_index", None)
            if row_index is not None:
                ownership[row_index] = full_type

    callers: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for method_index, method_row in enumerate(methods, start=1):
        body = get_method_body_bytes(pe, method_row.Rva)
        if not body:
            continue

        i = 0
        while i < len(body) - 4:
            opcode = body[i]
            if opcode in (0x28, 0x6F):
                token = int.from_bytes(body[i + 1 : i + 5], "little")
                if token in member_ref_tokens:
                    callers[method_index].append(member_ref_tokens[token])
                i += 5
            else:
                i += 1

    print(f"caller_methods={len(callers)}")
    for method_index in sorted(callers.keys()):
        method_name = getattr(methods[method_index - 1].Name, "value", f"Method_{method_index}")
        type_name = ownership.get(method_index, "")
        unique_calls = sorted(set(call_name for _, call_name in callers[method_index]))
        print(f"{method_index:4d} {type_name}::{method_name} -> {','.join(unique_calls)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
