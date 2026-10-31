import struct

PAGE = 0x4000
VM_BASE = 0x1_0000_0000
MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_EXECUTE = 2

MH_FLAGS = 0x1 | 0x4 | 0x80 | 0x200000

LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x2
LC_DYSYMTAB = 0xB
LC_LOAD_DYLIB = 0xC
LC_LOAD_DYLINKER = 0xE
LC_MAIN = 0x80000028

TEXT_OFFSET = 0x400
LINKEDIT_SIZE = 0x40

CODE = struct.pack("<II", 0xD2800000, 0xD65F03C0)


def _name16(text: str) -> bytes:
    return text.encode().ljust(16, b"\0")


def _segment(
    name: str,
    vmaddr: int,
    vmsize: int,
    fileoff: int,
    filesize: int,
    prot: int,
    sections: bytes = b"",
    nsects: int = 0,
) -> bytes:
    cmdsize = 72 + len(sections)
    head = struct.pack(
        "<II16sQQQQiiII",
        LC_SEGMENT_64,
        cmdsize,
        _name16(name),
        vmaddr,
        vmsize,
        fileoff,
        filesize,
        prot,
        prot,
        nsects,
        0,
    )
    return head + sections


def _padded_string_cmd(cmd: int, fixed: bytes, text: str) -> bytes:
    raw = text.encode() + b"\0"
    size = (len(fixed) + 8 + len(raw) + 7) & ~7
    body = struct.pack("<II", cmd, size) + fixed
    return (body + raw).ljust(size, b"\0")


def build_arm64_stub() -> bytes:
    text_section = struct.pack(
        "<16s16sQQIIIIIIII",
        _name16("__text"),
        _name16("__TEXT"),
        VM_BASE + TEXT_OFFSET,
        len(CODE),
        TEXT_OFFSET,
        2,
        0,
        0,
        0x80000400,
        0,
        0,
        0,
    )
    linkedit_off = PAGE
    strtab = b"\0 \0\0\0\0\0\0"
    commands = [
        _segment("__PAGEZERO", 0, VM_BASE, 0, 0, 0),
        _segment("__TEXT", VM_BASE, PAGE, 0, PAGE, 5, text_section, 1),
        _segment("__LINKEDIT", VM_BASE + PAGE, PAGE, linkedit_off, LINKEDIT_SIZE, 1),
        struct.pack(
            "<IIIIII", LC_SYMTAB, 24, linkedit_off, 0, linkedit_off, len(strtab)
        ),
        struct.pack("<II18I", LC_DYSYMTAB, 80, *([0] * 18)),
        _padded_string_cmd(LC_LOAD_DYLINKER, struct.pack("<I", 12), "/usr/lib/dyld"),
        struct.pack("<IIQQ", LC_MAIN, 24, TEXT_OFFSET, 0),
        _padded_string_cmd(
            LC_LOAD_DYLIB,
            struct.pack("<IIII", 24, 2, 0x10000, 0x10000),
            "/usr/lib/libSystem.B.dylib",
        ),
    ]
    blob = b"".join(commands)
    header = struct.pack(
        "<IiiIIIII",
        MH_MAGIC_64,
        CPU_TYPE_ARM64,
        0,
        MH_EXECUTE,
        len(commands),
        len(blob),
        MH_FLAGS,
        0,
    )
    image = bytearray(PAGE + LINKEDIT_SIZE)
    image[: len(header) + len(blob)] = header + blob
    image[TEXT_OFFSET : TEXT_OFFSET + len(CODE)] = CODE
    image[linkedit_off : linkedit_off + len(strtab)] = strtab
    return bytes(image)
