# -*- coding: utf-8 -*-
"""
Teste offline do leitor/extrator de .pac (spd_pac.py) - monta um arquivo
.pac sintético em memória (sem depender de firmware real) e verifica que
o diretório é lido corretamente e que a extração reproduz os bytes
originais.
"""
import struct
import sys
import tempfile
import os

sys.path.insert(0, ".")
import spd_pac as pac


def _u16(s, n):
    b = s.encode("utf-16-le")
    return b + b"\x00" * (n * 2 - len(b))


def _make_entry(name, data_offset, size, type_, addr0):
    id_ = _u16("FDL2" if type_ == 0x101 else "DATA", 256)
    name_b = _u16(name, 256)
    unknown1 = b"\x00" * 504
    addr = struct.pack("<5I", addr0, 0, 0, 0, 0)
    unknown2 = b"\x00" * 996
    return struct.pack(pac.FILE_FMT, pac.FILE_SIZE, id_, name_b, unknown1,
                        0, 0, size, type_, 1, data_offset, 0, 1, addr, unknown2)


def build_fake_pac(path, fw_name="MeuFirmwareTeste"):
    pac_version = _u16("PAC_TEST_1.0", 24)
    fw_name_raw = _u16(fw_name, 256)
    fw_version = _u16("1.0.0", 256)
    fw_alias = _u16("Teste", 100)

    head = struct.pack(
        pac.HEAD_FMT, pac_version, 0, fw_name_raw, fw_version,
        2, pac.HEAD_SIZE, b"\x00" * 20, fw_alias, b"\x00" * 12, b"\x00" * 800,
        pac.PAC_MAGIC, 0, 0,
    )
    assert len(head) == pac.HEAD_SIZE

    payload1 = b"FDL2_CONTENT_" + b"X" * 100
    payload2 = b"OTHER_FILE_" + b"Y" * 50
    data1_offset = pac.HEAD_SIZE + 2 * pac.FILE_SIZE
    data2_offset = data1_offset + len(payload1)

    entry1 = _make_entry("fdl2.bin", data1_offset, len(payload1), 0x101, 0x14000000)
    entry2 = _make_entry("splloader.bin", data2_offset, len(payload2), 1, 0)

    with open(path, "wb") as f:
        f.write(head)
        f.write(entry1)
        f.write(entry2)
        f.write(payload1)
        f.write(payload2)

    return payload1, payload2


def test_pac_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        pac_path = os.path.join(tmp, "fake.pac")
        payload1, payload2 = build_fake_pac(pac_path)

        info, entries = pac.read_pac_directory(pac_path)
        assert info["fw_name"] == "MeuFirmwareTeste"
        assert len(entries) == 2
        assert entries[0].name == "fdl2.bin" and entries[0].is_fdl
        assert entries[0].load_addr == 0x14000000
        assert entries[1].name == "splloader.bin" and not entries[1].is_fdl

        out_path = os.path.join(tmp, "extracted_fdl2.bin")
        n = pac.extract_pac_entry(pac_path, entries[0], out_path)
        with open(out_path, "rb") as f:
            data = f.read()
        assert data == payload1
        assert n == len(payload1)
        print("OK: leitura de diretório e extração de .pac batem byte a byte")


def test_pac_bad_magic():
    with tempfile.TemporaryDirectory() as tmp:
        bad_path = os.path.join(tmp, "bad.pac")
        with open(bad_path, "wb") as f:
            f.write(b"\x00" * pac.HEAD_SIZE)
        try:
            pac.read_pac_directory(bad_path)
            raise AssertionError("deveria ter rejeitado assinatura inválida")
        except pac.SpdError as e:
            print("OK: assinatura inválida rejeitada corretamente:", e)


if __name__ == "__main__":
    test_pac_roundtrip()
    test_pac_bad_magic()
    print("\nTodos os testes do spd_pac.py passaram.")
