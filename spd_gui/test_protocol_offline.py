# -*- coding: utf-8 -*-
"""
Teste offline (sem telefone conectado) do framing HDLC + checksum.
Monta um pacote com SpdIO._encode(...) e alimenta os bytes de volta no
parser _recv_msg1() simulando a leitura USB, para garantir que
encode/decode são simétricos e o checksum bate - antes de testar em
hardware real.
"""
import sys
import struct
import pytest
sys.path.insert(0, ".")

from spd_protocol import SpdIO, BSL, FLAGS_TRANSCODE, FLAGS_CRC16, spd_crc16, spd_checksum, spd_transcode


class FakeIO(SpdIO):
    """Substitui a E/S USB real por um buffer em memória para teste."""
    def __init__(self, feed_bytes, **kw):
        # não chama super().__init__ (evita exigir pyusb/dispositivo real)
        self.dev = None
        self.ep_in = self.ep_out = None
        self.ep_out_wmax = 0
        self.flags = FLAGS_TRANSCODE
        self.verbose = 0
        self.timeout = 1000
        self._rx_buf = b""
        self._rx_pos = 0
        self.raw_buf = b""
        self._log_cb = print
        self._feed = feed_bytes
        self._sent = bytearray()

    def _write(self, pkt):
        self._sent.extend(pkt)

    def _fill_rx(self):
        if not self._feed:
            return False
        # simula chegar em pedacos de 37 bytes, como pacotes USB reais
        chunk, self._feed = self._feed[:37], self._feed[37:]
        self._rx_buf = chunk
        self._rx_pos = 0
        return len(chunk) > 0


@pytest.mark.parametrize("flags,label", [(FLAGS_TRANSCODE, "transcode"), (FLAGS_CRC16, "crc16")])
def test_roundtrip(flags, label):
    io = FakeIO(b"")
    io.flags = flags
    payload = bytes(range(256)) * 3 + bytes([0x7e, 0x7d, 0x7e, 0x7d, 0x00, 0xff])
    pkt = io._encode(BSL.CMD_MIDST_DATA, payload)

    # agora finge que essa mensagem foi "recebida" do telefone
    io2 = FakeIO(pkt)
    io2.flags = flags
    raw = io2.recv_msg()
    assert raw is not None, "%s: recv retornou None (falhou)" % label
    got_type = int.from_bytes(raw[0:2], "big")
    got_len = int.from_bytes(raw[2:4], "big")
    got_data = raw[4:4 + got_len]
    assert got_type == BSL.CMD_MIDST_DATA, "%s: tipo incorreto" % label
    assert got_data == payload, "%s: payload não bate (tamanho %d vs %d)" % (label, len(got_data), len(payload))
    print("OK:", label, "- payload de", len(payload), "bytes íntegro, tipo=0x%02x" % got_type)


def test_checkbaud_and_ver():
    # Simula uma resposta BSL_REP_VER do telefone, como after checkbaud
    io = FakeIO(b"")
    io.flags = FLAGS_CRC16
    ver_payload = b"SPRD3\x00"
    pkt = io._encode(BSL.REP_VER, ver_payload)
    io2 = FakeIO(pkt)
    io2.flags = FLAGS_CRC16
    raw = io2.recv_msg()
    assert raw is not None
    assert io2._recv_type() == BSL.REP_VER
    n = int.from_bytes(raw[2:4], "big")
    assert raw[4:4+n] == ver_payload
    print("OK: BSL_REP_VER simulado decodificado corretamente:", raw[4:4+n])


def test_checksum_matches_manual():
    data = b"\x00\x01\x00\x04\xde\xad\xbe\xef"
    chk = spd_checksum(0, data, 1)
    # cálculo manual: soma palavras de 16 bits little-endian, complemento
    total = 0
    for i in range(0, len(data), 2):
        total += data[i+1] << 8 | data[i]
    total = (total >> 16) + (total & 0xffff)
    total += total >> 16
    total = (~total) & 0xffff
    remainder = len(data) % 2  # 0 pois len(data)=8 (par) -> entra no swap (0 < 1)
    if remainder < 1:
        total = (total >> 8) | ((total & 0xff) << 8)
    assert chk == total, (chk, total)
    print("OK: spd_checksum bate com cálculo manual (0x%04x)" % chk)


def test_partition_encoding():
    io = SpdIO.__new__(SpdIO)
    name_bytes = io._encode_partition_name("boot")
    assert len(name_bytes) == 72
    assert name_bytes[:8] == "boot".encode("utf-16-le")

    pkt = io._build_partition_pkt("boot", 0x100000, False)
    assert len(pkt) == 76
    assert struct.unpack("<I", pkt[72:76])[0] == 0x100000

    pkt64 = io._build_partition_pkt("userdata", 0x100000000, True)
    assert len(pkt64) == 88
    lo, hi = struct.unpack("<II", pkt64[72:80])
    assert lo == 0 and hi == 1
    print("OK: codificação de pacotes de partição (32-bit e 64-bit)")


def test_partition_list_parsing():
    def make_entry(name, size):
        n = name.encode("utf-16-le")
        n += b"\x00" * (72 - len(n))
        return n + struct.pack("<I", size)

    entries_raw = make_entry("boot", 0x200000) + make_entry("userdata", 0xffffffff)
    body = struct.pack(">HH", BSL.REP_READ_PARTITION, len(entries_raw)) + entries_raw

    size = struct.unpack(">H", body[2:4])[0]
    n = size // 0x4c
    result = []
    b = body[4:4 + size]
    for i in range(n):
        chunk = b[i * 0x4c:(i + 1) * 0x4c]
        nm = chunk[:72].decode("utf-16-le", errors="replace").split(chr(0))[0]
        sz = struct.unpack("<I", chunk[72:76])[0]
        result.append({"name": nm, "size_raw": sz})
    assert result == [
        {"name": "boot", "size_raw": 0x200000},
        {"name": "userdata", "size_raw": 0xffffffff},
    ]
    print("OK: parser de listagem de partições ->", result)


def test_jedec_decode():
    import spd_protocol as _spd
    # Winbond W25Q32 (32Mbit/4MB): EF 40 16
    raw = (0xEF << 16) | (0x40 << 8) | 0x16
    d = _spd.decode_jedec_id(raw)
    assert d["manufacturer_name"] == "Winbond"
    assert d["size_bytes"] == 4 * 1024 * 1024

    # GigaDevice GD25Q64 (64Mbit/8MB): C8 40 17
    raw2 = (0xC8 << 16) | (0x40 << 8) | 0x17
    d2 = _spd.decode_jedec_id(raw2)
    assert d2["manufacturer_name"] == "GigaDevice"
    assert d2["size_bytes"] == 8 * 1024 * 1024
    print("OK: decode_jedec_id bate com chips reais conhecidos (Winbond 4MB, GigaDevice 8MB)")


if __name__ == "__main__":
    test_roundtrip(FLAGS_TRANSCODE, "transcode ligado (FDL1)")
    test_roundtrip(FLAGS_TRANSCODE | FLAGS_CRC16, "transcode+crc16 (bootloader)")
    test_roundtrip(0, "sem transcode (disable_transcode)")
    test_checkbaud_and_ver()
    test_checksum_matches_manual()
    test_partition_encoding()
    test_partition_list_parsing()
    test_jedec_decode()
    print("\nTodos os testes offline passaram.")
