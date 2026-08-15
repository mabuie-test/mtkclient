# -*- coding: utf-8 -*-
"""
spd_pac.py

Leitura e extração de arquivos de pacotes de firmware `.pac` da
Spreadtrum/Unisoc - reimplementação em Python, traduzida a partir de
`unpac/unpac.c` (parte do projeto spreadtrum_flash), incluindo layout de
struct, offsets e o campo `type` (0x101 = arquivo FDL) usados para achar
o FDL1/FDL2 oficiais dentro de um firmware.

Uso típico:

    info, entries = read_pac_directory("firmware.pac")
    fdl_entries = [e for e in entries if e.is_fdl]
    extract_pac_entry("firmware.pac", fdl_entries[0], "fdl2.bin")
"""

import struct

try:
    from spd_protocol import SpdError, SpdCancelled
except Exception:  # pragma: no cover - permite uso standalone sem spd_protocol
    class SpdError(Exception):
        pass

    class SpdCancelled(SpdError):
        pass


PAC_MAGIC = 0xFFFAFFFA  # ~0x50005 em 32 bits, conforme unpac.c

# Layout de sprd_head_t (little-endian, sem padding - verificado offset a
# offset a partir do unpac.c original):
#   pac_version[24]   48 bytes
#   pac_size          4
#   fw_name[256]      512
#   fw_version[256]   512
#   file_count        4
#   dir_offset        4
#   unknown1[5]       20
#   fw_alias[100]     200
#   unknown2[3]       12
#   unknown[200]      800
#   pac_magic         4
#   head_crc          2
#   data_crc          2
# total = 2124 bytes
HEAD_FMT = "<48sI512s512sII20s200s12s800sIHH"
HEAD_SIZE = struct.calcsize(HEAD_FMT)

# Layout de sprd_file_t:
#   struct_size       4
#   id[256]           512
#   name[256]         512
#   unknown1[252]     504
#   size_high         4
#   pac_offset_high   4
#   size              4
#   type              4   (0=operação, 1=arquivo, 2=xml, 0x101=fdl)
#   flash_use         4
#   pac_offset        4
#   omit_flag         4
#   addr_num          4
#   addr[5]           20
#   unknown2[249]     996
# total = 2580 bytes
FILE_FMT = "<I512s512s504sIIIIIIII20s996s"
FILE_SIZE = struct.calcsize(FILE_FMT)

FDL_TYPE = 0x101


def _decode_u16_str(raw):
    """Decodifica uma string UTF-16LE terminada em zero (campos wide-char
    do formato .pac)."""
    text = raw.decode("utf-16-le", errors="replace")
    return text.split("\x00", 1)[0]


class PacEntry:
    """Uma entrada do diretório de um arquivo .pac."""

    def __init__(self, id_, name, size, pac_offset, type_, flash_use, addrs):
        self.id = id_
        self.name = name
        self.size = size
        self.pac_offset = pac_offset
        self.type = type_
        self.flash_use = flash_use
        self.addrs = addrs  # até 5 endereços de carga (uint32); 0 = não usado

    @property
    def is_fdl(self):
        return self.type == FDL_TYPE

    @property
    def load_addr(self):
        """Primeiro endereço não-zero da entrada (endereço de carga), ou None."""
        for a in self.addrs:
            if a:
                return a
        return None

    def __repr__(self):
        return "PacEntry(name=%r, type=0x%x, size=0x%x, addr=%r)" % (
            self.name, self.type, self.size, self.load_addr
        )


def read_pac_directory(path):
    """
    Lê o cabeçalho e a lista de arquivos de um .pac, sem extrair nada.
    Retorna (info: dict, entries: list[PacEntry]).
    """
    with open(path, "rb") as f:
        head_raw = f.read(HEAD_SIZE)
        if len(head_raw) != HEAD_SIZE:
            raise SpdError("arquivo .pac truncado ou inválido (cabeçalho incompleto)")

        (pac_version_raw, pac_size, fw_name_raw, fw_version_raw, file_count,
         dir_offset, _unk1, fw_alias_raw, _unk2, _unk3, pac_magic,
         head_crc, data_crc) = struct.unpack(HEAD_FMT, head_raw)

        if pac_magic != PAC_MAGIC:
            raise SpdError(
                "assinatura inválida (0x%08x) - não parece ser um firmware "
                ".pac da Spreadtrum/Unisoc" % pac_magic
            )
        if dir_offset != HEAD_SIZE:
            raise SpdError(
                "deslocamento de diretório inesperado (%d, esperado %d) - "
                "formato de .pac incompatível" % (dir_offset, HEAD_SIZE)
            )
        if file_count >= 1024:
            raise SpdError("número de arquivos suspeito no .pac (%d)" % file_count)

        info = {
            "pac_version": _decode_u16_str(pac_version_raw),
            "fw_name": _decode_u16_str(fw_name_raw),
            "fw_version": _decode_u16_str(fw_version_raw),
            "fw_alias": _decode_u16_str(fw_alias_raw),
            "pac_size": pac_size,
            "file_count": file_count,
        }

        entries = []
        for i in range(file_count):
            raw = f.read(FILE_SIZE)
            if len(raw) != FILE_SIZE:
                raise SpdError(
                    "diretório do .pac truncado (arquivo %d de %d)" % (i, file_count)
                )
            (struct_size, id_raw, name_raw, _unk1, size_high, pac_off_high,
             size_lo, type_, flash_use, pac_off_lo, _omit_flag, addr_num,
             addr_raw, _unk2) = struct.unpack(FILE_FMT, raw)

            if struct_size != FILE_SIZE:
                raise SpdError(
                    "tamanho de struct inesperado no diretório do .pac "
                    "(0x%x, esperado 0x%x)" % (struct_size, FILE_SIZE)
                )

            name = _decode_u16_str(name_raw)
            id_ = _decode_u16_str(id_raw)
            size = (size_high << 32) | size_lo
            pac_offset = (pac_off_high << 32) | pac_off_lo
            addrs = struct.unpack("<5I", addr_raw)[:max(0, min(5, addr_num))] \
                if addr_num else ()

            if not name or not pac_offset or not size:
                continue  # entrada "operação" sem arquivo de verdade associado

            entries.append(PacEntry(id_, name, size, pac_offset, type_, flash_use, addrs))

        return info, entries


def extract_pac_entry(path, entry, out_path, chunk_size=1024 * 1024,
                       progress_cb=None, cancel_event=None):
    """
    Extrai uma única entrada (PacEntry) do .pac para out_path, lendo em
    streaming (não carrega o arquivo inteiro na memória).
    """
    with open(path, "rb") as f, open(out_path, "wb") as fo:
        f.seek(entry.pac_offset)
        remaining = entry.size
        written = 0
        while remaining:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            n = min(chunk_size, remaining)
            data = f.read(n)
            if len(data) != n:
                raise SpdError(
                    "arquivo .pac truncado ao extrair '%s' (esperava mais "
                    "%d bytes)" % (entry.name, n)
                )
            fo.write(data)
            remaining -= n
            written += n
            if progress_cb:
                progress_cb(written, entry.size)
    return written
