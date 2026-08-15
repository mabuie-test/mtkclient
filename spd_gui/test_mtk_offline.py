# -*- coding: utf-8 -*-
"""
Teste offline do mtk_protocol.py - simula um "telefone" que ecoa bytes
(igual ao protocolo real) para validar handshake, checksum do DA, e o
protocolo SFI (flash) sem precisar de hardware.
"""
import struct
import sys
sys.path.insert(0, ".")

import mtk_protocol as mtk


class FakeMtkIO(mtk.MtkIO):
    """Substitui o transporte real por uma fila de bytes/respostas
    programadas, para testar a lógica de protocolo isoladamente."""

    def __init__(self, script):
        self.transport = None
        self.verbose = 0
        self.timeout = 1000
        self.erase_blk = 0x1000
        self.erase_cmd = 0x20
        self._log_cb = lambda m: None
        self._script = list(script)  # lista de (esperado_enviado, resposta) ou callable
        self._sent_log = []

    def _send(self, data):
        self._sent_log.append(bytes(data))

    def _recv(self, n):
        if not self._script:
            return b""
        expected_sent, response = self._script.pop(0)
        if callable(response):
            response = response(self._sent_log[-1])
        return response[:n] if response else b""


def test_handshake_ok():
    seq = bytes([0xa0, 0x0a, 0x50, 0x05])
    script = [(None, bytes([b ^ 0xff])) for b in seq]
    io = FakeMtkIO(script)
    result = io.handshake()
    assert result is True
    print("OK: handshake normal (4 bytes trocados corretamente)")


def test_handshake_already_done():
    script = [(None, bytes([0xa0]))]  # eco == byte enviado (sem XOR 0xff)
    io = FakeMtkIO(script)
    result = io.handshake()
    assert result is False
    print("OK: handshake 'já feito' detectado corretamente")


def test_mtk_checksum():
    data = bytes(range(256)) * 4
    chk = mtk.mtk_checksum(data)
    # cálculo manual de referência
    ref = 0
    for i in range(0, len(data) - (len(data) & 1), 2):
        ref ^= data[i] | (data[i + 1] << 8)
    assert chk == ref
    print("OK: mtk_checksum bate com cálculo manual (0x%04x)" % chk)


def test_sfi_checksum_self_consistent():
    # o checksum de [dados + seu próprio checksum] deve dar 0
    data = bytes([0x9f, 0x01, 0x02, 0x03, 0x04, 0x05])
    chk = mtk._sfi_checksum(data)
    combined = data + struct.pack("<H", chk)
    assert mtk._sfi_checksum(combined) == 0
    print("OK: _sfi_checksum é auto-consistente (dados+checksum soma 0)")


def test_flash_cmp():
    # 0xff -> qualquer coisa: nunca precisa apagar (todos os bits já são 1)
    assert mtk._flash_cmp(b"\xff\xff\xff", b"\x12\x34\x56") is False
    # 0x00 -> não-zero: precisa apagar (bit querendo virar 1 onde já é 0)
    assert mtk._flash_cmp(b"\x00", b"\x01") is True
    # igual a igual: não precisa apagar
    assert mtk._flash_cmp(b"\xab\xcd", b"\xab\xcd") is False
    print("OK: _flash_cmp identifica corretamente quando apagar é necessário")


def test_jedec_reuse():
    # confirma que decode_jedec_id (reaproveitado de spd_protocol) funciona
    # igual para o flash_id do MTK
    from spd_protocol import decode_jedec_id
    d = decode_jedec_id((0xEF << 16) | (0x40 << 8) | 0x16)
    assert d["manufacturer_name"] == "Winbond"
    assert d["size_bytes"] == 4 * 1024 * 1024
    print("OK: decode_jedec_id reaproveitado corretamente para flash_id do MTK")


def test_sfi_cmd_roundtrip():
    """Simula uma resposta válida (com checksum correto) para um comando
    SFI e confere que sfi_cmd() decodifica certo - inclusive o eco do
    byte 0x55 que precede cada comando SFI."""
    # resposta simulada: 3 bytes de dados (JEDEC ID) + padding + checksum válido
    rlen = 3
    resp_data = bytes([0xEF, 0x40, 0x16])
    rlen2 = (rlen + 3) & ~1  # = 4
    padded = resp_data + b"\x00" * (rlen2 - len(resp_data) - 2)
    chk = mtk._sfi_checksum(padded)
    full_response = padded + struct.pack("<H", chk)
    assert len(full_response) == rlen2

    # script: primeiro _recv é o eco do byte 0x55, depois a resposta do comando
    script = [
        (None, b"\x55"),            # eco do echo8(0x55)
        (None, full_response),      # resposta do sfi_cmd em si
    ]
    io = FakeMtkIO(script)
    result = io.sfi_cmd(bytes([0x9f]), rlen)
    assert result == resp_data, result
    print("OK: sfi_cmd round-trip decodifica corretamente uma resposta simulada válida")


if __name__ == "__main__":
    test_handshake_ok()
    test_handshake_already_done()
    test_mtk_checksum()
    test_sfi_checksum_self_consistent()
    test_flash_cmp()
    test_jedec_reuse()
    test_sfi_cmd_roundtrip()
    print("\nTodos os testes offline do mtk_protocol.py passaram.")
