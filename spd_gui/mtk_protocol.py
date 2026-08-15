# -*- coding: utf-8 -*-
"""
mtk_protocol.py

Reimplementação em Python do protocolo MediaTek BROM (Boot ROM) usado
pelo `mtk_dump` (projeto "mediatek_flash", mesmo autor do
`spreadtrum_flash` que já usamos). Cobre MT6260/MT6261 - chips de
feature phone, não smartphones.

Duas camadas de comando:
- Comandos do BROM (sempre disponíveis assim que conecta): handshake,
  connect, ler/escrever memória, carregar um "DA" (Download Agent -
  equivalente ao FDL do mundo Spreadtrum) em RAM e executá-lo.
- Comandos do payload custom (só depois de carregar o DA que vem junto
  do projeto original, em payload/): ler o JEDEC ID da flash SPI, ler,
  apagar e gravar a flash.

Reaproveita UsbTransport/SerialTransport e as exceções de
spd_protocol.py - são genéricas o bastante (framing HDLC é só do lado
SPD; aqui usamos os mesmos objetos só para enviar/receber bytes).

Uso típico:

    io = MtkIO(log_cb=print)
    io.open_usb(timeout_s=60)                 # espera o telefone conectar
    info = io.connect()                        # handshake + info do chip
    with open("payload.bin", "rb") as f:
        io.simple_da(f.read(), 0x70008000)      # carrega e executa o payload
    jedec = io.flash_id()
    with open("flash.bin", "wb") as f:
        io.read_flash(0, 0x400000, out_file=f, progress_cb=...)
    io.close()
"""

import struct
import time

from spd_protocol import (
    HAVE_PYUSB, HAVE_PYSERIAL,
    UsbTransport, SerialTransport, list_serial_ports,
    SpdError, SpdTimeout, SpdCancelled,
    decode_jedec_id,
)

try:
    import usb.core
except Exception:
    pass

MTK_VENDOR_ID = 0x0e8d
MTK_PRODUCT_ID = 0x0003

DEFAULT_TIMEOUT_MS = 3000
RECV_BUF_LEN = 4096


class CMD:
    """Comandos do BROM (mtk_cmd.h)."""
    SEND_IMAGE = 0x70
    BOOT_IMAGE = 0x71
    STAY_STILL = 0x80

    LEGACY_WRITE = 0xa1
    LEGACY_READ = 0xa2

    READ16 = 0xd0
    READ32 = 0xd1
    WRITE16 = 0xd2
    WRITE16_NO_ECHO = 0xd3
    WRITE32 = 0xd4
    JUMP_DA = 0xd5
    JUMP_BL = 0xd6
    SEND_DA = 0xd7
    GET_TARGET_CONFIG = 0xd8
    SEND_EPP = 0xd9
    UART1_LOG_EN = 0xdb
    SET_BAUD = 0xdc

    SEND_CERT = 0xe0
    GET_ME_ID = 0xe1
    SEND_AUTH = 0xe2
    GET_SOC_ID = 0xe7

    ZEROIZATION = 0xf0
    GET_PL_CAP = 0xfb
    GET_HW_SW_VER = 0xfc
    GET_HW_CODE = 0xfd
    GET_BL_VER = 0xfe
    GET_VERSION = 0xff


# IDs de chip conhecidos (MT6260/MT6261 - os únicos suportados pelo
# payload custom original).
KNOWN_CHIPS = {
    0x6260: "MT6260",
    0x6261: "MT6261",
}


def mtk_checksum(data):
    """XOR de palavras de 16 bits little-endian (usado no envio do DA)."""
    chk = 0
    n = len(data) - (len(data) & 1)
    for i in range(0, n, 2):
        chk ^= data[i] | (data[i + 1] << 8)
    if len(data) & 1:
        chk ^= data[-1]
    return chk & 0xffff


def _sfi_checksum(data):
    """
    Checksum usado nos comandos SFI do payload custom (spd_checksum em
    custom_cmd.h - diferente do checksum do protocolo Spreadtrum apesar
    do nome igual no C original): soma palavras de 16 bits little-endian,
    dobra o carry duas vezes, complemento de um.
    """
    n = len(data) - (len(data) & 1)
    crc = 0
    for i in range(0, n, 2):
        crc += data[i] | (data[i + 1] << 8)
    crc = (crc >> 16) + (crc & 0xffff)
    crc += crc >> 16
    return (~crc) & 0xffff


def _flash_cmp(existing, new):
    """True se algum bit em `new` precisar virar 1 onde `existing` tem 0
    (ou seja, se um apagamento é necessário antes de gravar)."""
    for a, b in zip(existing, new):
        if (~a & 0xff) & b:
            return True
    return False


class MtkIO:
    """Conexão com um telefone MediaTek em modo BROM (0e8d:0003)."""

    def __init__(self, log_cb=None):
        self.transport = None
        self.verbose = 0
        self.timeout = DEFAULT_TIMEOUT_MS
        self.erase_blk = 0x1000
        self.erase_cmd = 0x20
        self._log_cb = log_cb or (lambda msg: None)

    def _log(self, msg):
        try:
            self._log_cb(msg)
        except Exception:
            pass

    # -- ciclo de vida -----------------------------------------------------

    @staticmethod
    def wait_for_device_usb(timeout_s=60, poll_interval=0.5, cancel_event=None, log_cb=None):
        if not HAVE_PYUSB:
            raise SpdError("O pacote 'pyusb' não está instalado. Instale com: pip install pyusb")
        deadline = time.time() + timeout_s if timeout_s else None
        first = True
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            dev = usb.core.find(idVendor=MTK_VENDOR_ID, idProduct=MTK_PRODUCT_ID)
            if dev is not None:
                return dev
            if first and log_cb:
                log_cb("Aguardando o telefone conectar em modo BROM (0e8d:0003)...")
                first = False
            if deadline is not None and time.time() >= deadline:
                raise SpdTimeout("Tempo esgotado esperando o telefone conectar.")
            time.sleep(poll_interval)

    def open_usb(self, timeout_s=60, cancel_event=None):
        dev = self.wait_for_device_usb(timeout_s=timeout_s, cancel_event=cancel_event, log_cb=self._log)
        self.transport = UsbTransport.open(dev)
        self._log("Dispositivo conectado via USB (endpoints IN=0x%02x OUT=0x%02x)"
                   % (self.transport.ep_in, self.transport.ep_out))

    def open_serial(self, port, baudrate=115200, wait_s=0, poll_interval=0.5, cancel_event=None):
        deadline = time.time() + wait_s if wait_s else None
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            try:
                self.transport = SerialTransport.open(port, baudrate=baudrate)
                break
            except SpdError:
                if deadline is None or time.time() >= deadline:
                    raise
                time.sleep(poll_interval)
        self._log("Dispositivo conectado via porta serial %s (%d bps)" % (port, baudrate))

    def close(self):
        if self.transport is not None:
            self.transport.close()
        self.transport = None

    # -- E/S de baixo nível (protocolo por eco, sem framing HDLC) ----------

    def _send(self, data):
        if self.transport is None:
            raise SpdError("nenhuma conexão aberta")
        if self.verbose >= 2:
            self._log("send (%d): %s" % (len(data), data.hex()))
        self.transport.write(data, self.timeout)

    def _recv(self, n):
        """Lê exatamente até n bytes (ou menos, se o tempo esgotar)."""
        if self.transport is None:
            raise SpdError("nenhuma conexão aberta")
        deadline = time.time() + self.timeout / 1000.0
        buf = bytearray()
        while len(buf) < n:
            remaining_ms = int((deadline - time.time()) * 1000)
            if remaining_ms <= 0:
                break
            chunk = self.transport.read(n - len(buf), remaining_ms)
            if not chunk:
                break
            buf.extend(chunk)
        if self.verbose >= 2 and buf:
            self._log("recv (%d): %s" % (len(buf), bytes(buf).hex()))
        return bytes(buf)

    def _echo(self, data):
        self._send(data)
        got = self._recv(len(data))
        if got != data:
            raise SpdError(
                "eco inesperado do telefone (enviei %s, recebi %s) - "
                "conexão pode estar fora de sincronia" % (data.hex(), got.hex())
            )

    def _echo8(self, value):
        self._echo(bytes([value & 0xff]))

    def _echo16(self, value):
        self._echo(struct.pack(">H", value & 0xffff))

    def _echo32(self, value):
        self._echo(struct.pack(">I", value & 0xffffffff))

    def _recv8(self):
        raw = self._recv(1)
        if len(raw) != 1:
            raise SpdTimeout("tempo limite atingido aguardando resposta")
        return raw[0]

    def _recv16(self):
        raw = self._recv(2)
        if len(raw) != 2:
            raise SpdTimeout("tempo limite atingido aguardando resposta")
        return struct.unpack(">H", raw)[0]

    def _recv32(self):
        raw = self._recv(4)
        if len(raw) != 4:
            raise SpdTimeout("tempo limite atingido aguardando resposta")
        return struct.unpack(">I", raw)[0]

    def _status(self):
        raw = self._recv(2)
        if len(raw) != 2:
            raise SpdTimeout("tempo limite atingido aguardando status")
        status = struct.unpack(">H", raw)[0]
        if status >= 0xff:
            raise SpdError("status inesperado do telefone: %d (0x%04x)" % (status, status))
        return status

    # -- handshake / connect -------------------------------------------------

    def handshake(self):
        """Sequência de sincronização inicial do BROM (0xA0 0x0A 0x50 0x05,
        cada byte respondido com seu complemento)."""
        seq = bytes([0xa0, 0x0a, 0x50, 0x05])
        for i, b in enumerate(seq):
            self._send(bytes([b]))
            got = self._recv(1)
            if len(got) != 1:
                raise SpdTimeout("tempo limite atingido no handshake inicial")
            ret = got[0] ^ b
            if ret != 0xff:
                if ret == 0 and i == 0:
                    self._log("handshake já estava feito")
                    return False
                raise SpdError("resposta inesperada no handshake (byte %d)" % i)
        return True

    def connect(self):
        """
        Handshake completo + leitura de versão/identificação do chip
        (equivalente ao comando 'connect' do mtk_dump original). Também
        desliga o watchdog em MT6260/MT6261, como o original faz.
        """
        self.handshake()

        self._send(bytes([CMD.GET_VERSION]))
        b = self._recv8()
        brom_ver = None if b == CMD.GET_VERSION else b
        if brom_ver is not None and brom_ver < 5:
            raise SpdError("versão do BROM inesperada (0x%02x)" % brom_ver)

        self._send(bytes([CMD.GET_BL_VER]))
        b = self._recv8()
        bl_ver = None if b == CMD.GET_BL_VER else b

        info = []
        for i in range(4):
            self._echo8(CMD.LEGACY_READ)
            self._echo32(0x80000000 + i * 4)
            self._echo32(1)
            info.append(self._recv16())

        sw_ver, sw_ver2, hw_code, hw_ver = info
        chip_name = KNOWN_CHIPS.get(hw_code, "desconhecido (0x%04x)" % hw_code)

        if hw_code in (0x6260, 0x6261):
            self.write16(0xa0030000, 0x2200)  # desliga o watchdog

        return {
            "brom_ver": brom_ver, "bl_ver": bl_ver,
            "sw_ver": sw_ver, "sw_ver2": sw_ver2,
            "hw_code": hw_code, "hw_ver": hw_ver,
            "chip_name": chip_name,
        }

    # -- comandos simples do BROM --------------------------------------------

    def read32(self, addr):
        self._echo8(CMD.READ32)
        self._echo32(addr)
        self._echo32(1)
        self._status()
        val = self._recv32()
        self._status()
        return val

    def write16(self, addr, val):
        self._echo8(CMD.WRITE16)
        self._echo32(addr)
        self._echo32(1)
        self._status()
        self._echo16(val)
        self._status()

    def write32(self, addr, val):
        self._echo8(CMD.WRITE32)
        self._echo32(addr)
        self._echo32(1)
        self._status()
        self._echo32(val)
        self._status()

    def show_flash(self, chip_hw_code, enable):
        """Mapeia a flash SPI na memória em 0 (necessário antes de read32
        conseguir ler a flash diretamente, sem o payload custom)."""
        if chip_hw_code not in (0x6260, 0x6261):
            return
        addr = 0xa0510000
        val = self.read32(addr)
        val2 = (val | 2) if enable else (val & ~2)
        if val != val2:
            self.write32(addr, val2)

    def reboot(self, chip_hw_code):
        if chip_hw_code in (0x6260, 0x6261):
            self.write32(0xa003001c, 0x1209)

    def jump_bl(self):
        self._echo8(CMD.JUMP_BL)
        self._status()
        self._status()

    def get_meid(self):
        self._echo8(CMD.GET_ME_ID)
        size = self._recv32()
        raw = self._recv(size)
        if len(raw) != size:
            raise SpdError("resposta incompleta lendo o MEID")
        self._status()
        return raw

    def dump_mem(self, start, length, cmd=CMD.READ32, out_file=None, step=1024,
                 progress_cb=None, cancel_event=None):
        """Lê memória via READ16/READ32/LEGACY_READ (comandos sempre
        disponíveis no BROM, sem precisar de nenhum DA)."""
        legacy = (cmd == CMD.LEGACY_READ)
        unit_shift = 2 if cmd == CMD.READ32 else 1
        unit_size = 1 << unit_shift
        if (length | start) & (unit_size - 1):
            raise SpdError("leitura desalinhada (precisa múltiplo de %d bytes)" % unit_size)

        buf = bytearray() if out_file is None else None
        off = start
        end = start + length
        while off < end:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            n = min(step, end - off)
            self._echo8(cmd)
            self._echo32(off)
            self._echo32(n >> unit_shift)
            if not legacy:
                r = self._recv(2)
                if len(r) != 2 or struct.unpack(">H", r)[0] != 0:
                    raise SpdError("resposta inesperada durante leitura de memória")
            raw = bytearray(self._recv(n))
            if len(raw) != n:
                raise SpdError("resposta incompleta durante leitura (%d de %d bytes)" % (len(raw), n))
            if unit_shift == 1:
                for i in range(0, len(raw), 2):
                    a = (raw[i] << 8) | raw[i + 1]
                    raw[i] = a & 0xff
                    raw[i + 1] = (a >> 8) & 0xff
            else:
                for i in range(0, len(raw), 4):
                    a = struct.unpack_from(">I", raw, i)[0]
                    struct.pack_into("<I", raw, i, a)
            if out_file is not None:
                out_file.write(raw)
            else:
                buf.extend(raw)
            off += n
            if progress_cb:
                progress_cb(off - start, length)
        return off - start, (bytes(buf) if buf is not None else None)

    # -- carregar e executar um DA (Download Agent) --------------------------

    def _send_long(self, data, step=1024, progress_cb=None, cancel_event=None):
        sent = 0
        total = len(data)
        for i in range(0, total, step):
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            chunk = data[i:i + step]
            self._send(chunk)
            sent += len(chunk)
            if progress_cb:
                progress_cb(sent, total)

    def send_da(self, data, addr, sig_len=0, progress_cb=None, cancel_event=None):
        self._echo8(CMD.SEND_DA)
        self._echo32(addr)
        self._echo32(len(data))
        self._echo32(sig_len)
        self._status()

        chk2 = mtk_checksum(data)
        self._send_long(data, progress_cb=progress_cb, cancel_event=cancel_event)
        chk1 = self._recv16()
        if chk1 != chk2:
            raise SpdError(
                "checksum incorreto ao enviar o DA (recebido 0x%04x, "
                "esperado 0x%04x) - envio pode ter corrompido" % (chk1, chk2)
            )
        self._status()

    def jump_da(self, addr):
        self._echo8(CMD.JUMP_DA)
        self._echo32(addr)
        self._status()

    def simple_da(self, data, addr, progress_cb=None, cancel_event=None):
        """Carrega o DA/payload em RAM e já executa (equivalente a
        send_da + jump_da do mtk_dump original)."""
        self.send_da(data, addr, 0, progress_cb=progress_cb, cancel_event=cancel_event)
        self.jump_da(addr)

    # -- comandos do payload custom (SFI - flash SPI) ------------------------
    # Só funcionam depois de simple_da() com o payload deste projeto.

    def sfi_cmd(self, msg, rlen, qpi=False):
        mlen = len(msg)
        if mlen + rlen > 256 + 6:
            raise SpdError("tamanho de comando SFI inesperado")
        self._echo8(0x55)

        padded = bytearray(msg)
        if mlen & 1:
            padded.append(0)
        header = struct.pack("<HH", mlen | (0x8000 if qpi else 0), rlen)
        body = header + bytes(padded)
        chk = _sfi_checksum(body)
        self._send(body + struct.pack("<H", chk))

        rlen2 = (rlen + 3) & ~1
        raw = self._recv(rlen2)
        if len(raw) != rlen2:
            raise SpdError(
                "resposta inesperada do comando SFI (%d de %d bytes) - "
                "o payload/DA custom está carregado?" % (len(raw), rlen2)
            )
        if _sfi_checksum(raw) != 0:
            raise SpdError("checksum inválido na resposta do comando SFI")
        return raw[:rlen]

    def sfi_cmd_addr(self, cmd, addr, alen, rlen):
        msg = bytearray(5)
        msg[0] = cmd
        if alen > 3:
            msg[1] = (addr >> 24) & 0xff
        msg[alen - 2] = (addr >> 16) & 0xff
        msg[alen - 1] = (addr >> 8) & 0xff
        msg[alen] = addr & 0xff
        return self.sfi_cmd(bytes(msg[:alen + 1]), rlen)

    def sfi_read_status(self):
        raw = self.sfi_cmd(bytes([0x05]), 1)  # Read Status Register
        return raw[0]

    def sfi_read_sfdp(self, addr, size):
        result = bytearray()
        while len(result) < size:
            n = min(128, size - len(result))
            result.extend(self.sfi_cmd_addr(0x5a, addr << 8, 4, n))
            addr += n
        return bytes(result)

    def sfi_read(self, addr, size):
        result = bytearray()
        remaining = size
        while remaining:
            cmd, k = (0x13, 4) if (addr >> 24) else (0x03, 3)
            n = min(128, remaining)
            result.extend(self.sfi_cmd_addr(cmd, addr, k, n))
            addr += n
            remaining -= n
        return bytes(result)

    def sfi_write_enable(self):
        self.sfi_cmd(bytes([0x06]), 0)  # Write Enable
        while not (self.sfi_read_status() & 2):
            time.sleep(0.001)

    def sfi_erase(self, addr, cmd=None, addr_len=3):
        if cmd is None:
            cmd = self.erase_cmd
        self.sfi_write_enable()
        self.sfi_cmd_addr(cmd, addr, addr_len, 0)
        time.sleep(0.0005)
        while self.sfi_read_status() & 1:
            time.sleep(0.001)

    def sfi_write(self, addr, data):
        pos = 0
        total = len(data)
        while pos < total:
            k = 256 - (addr & 255)
            n = min(total - pos, k, 128)
            msg = bytearray()
            if addr >> 24:
                msg.append(0x12)
                msg.append((addr >> 24) & 0xff)
            else:
                msg.append(0x02)
            msg.append((addr >> 16) & 0xff)
            msg.append((addr >> 8) & 0xff)
            msg.append(addr & 0xff)
            msg.extend(data[pos:pos + n])
            self.sfi_write_enable()
            self.sfi_cmd(bytes(msg), 0)
            time.sleep(0.0005)
            while self.sfi_read_status() & 1:
                time.sleep(0.001)
            addr += n
            pos += n

    def sfi_write_cmp(self, addr, orig, src):
        """Grava src, mas só os bytes que realmente diferem de orig (ou de
        0xff se orig for None) - evita ciclos de escrita desnecessários."""
        pos = 0
        total = len(src)
        while pos < total:
            n = total - pos
            k = 256 - (addr & 255)
            if n > k:
                n = k
            i = 0
            if orig is not None:
                while i < n and orig[pos + i] == src[pos + i]:
                    i += 1
            else:
                while i < n and src[pos + i] == 0xff:
                    i += 1
            n -= i
            addr += i
            pos += i
            if n > 128:
                n = 128
            keep = n
            if orig is not None:
                while keep and orig[pos + keep - 1] == src[pos + keep - 1]:
                    keep -= 1
            else:
                while keep and src[pos + keep - 1] == 0xff:
                    keep -= 1
            if keep:
                self.sfi_write(addr, src[pos:pos + keep])
            addr += n
            pos += n

    # -- operações de alto nível na flash (payload custom) -------------------

    def flash_id(self):
        """Lê o JEDEC ID da flash SPI (fabricante, tipo, capacidade)."""
        raw = self.sfi_cmd(bytes([0x9f]), 3)  # Read JEDEC ID
        value = (raw[0] << 16) | (raw[1] << 8) | raw[2]
        return decode_jedec_id(value)

    def dump_flash(self, start, length, out_file=None, step=128,
                    progress_cb=None, cancel_event=None):
        off = start
        end = start + length
        buf = bytearray() if out_file is None else None
        while off < end:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            n = min(step, end - off)
            chunk = self.sfi_read(off, n)
            if out_file is not None:
                out_file.write(chunk)
            else:
                buf.extend(chunk)
            off += n
            if progress_cb:
                progress_cb(off - start, length)
        return off - start, (bytes(buf) if buf is not None else None)

    # alias mais descritivo, usado pela GUI
    read_flash = dump_flash

    def erase_flash(self, addr, size, progress_cb=None, cancel_event=None):
        if (addr | size) & (self.erase_blk - 1):
            raise SpdError(
                "apagamento desalinhado (precisa ser múltiplo de 0x%x bytes)" % self.erase_blk
            )
        end = addr + size
        a = addr
        while a < end:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            self.sfi_erase(a)
            a += self.erase_blk
            if progress_cb:
                progress_cb(a - addr, size)

    def write_flash_buf(self, data, addr, progress_cb=None, cancel_event=None):
        """
        Grava `data` a partir de `addr` na flash, apagando cada bloco de
        4 KB só quando necessário (se algum bit precisar ir de 0 para 1) -
        evita desgastar a flash e é bem mais rápido quando grande parte do
        conteúdo já é igual ao que está sendo gravado.
        """
        blk = self.erase_blk
        if blk > 0x1000:
            raise SpdError("tamanho de bloco de apagamento não suportado")
        size = len(data)
        end = addr + size
        mem_pos = 0
        while addr < end:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            k = (addr & ~(blk - 1)) + blk
            if k > end:
                k = end
            n = k - addr

            buf = bytearray(blk)
            mask = 0
            need_erase = False
            i = addr
            while i < k:
                t = i & ~127
                n2 = t + 128
                if n2 > k:
                    n2 = k
                n2 -= i
                l = t & (blk - 1)
                mask |= 1 << (l >> 7)
                buf[l:l + 128] = self.sfi_read(t, 128)
                off_buf = i & (blk - 1)
                off_mem = mem_pos + (i - addr)
                if _flash_cmp(buf[off_buf:off_buf + n2], data[off_mem:off_mem + n2]):
                    need_erase = True
                    break
                i += n2

            if need_erase:
                i = addr & ~(blk - 1)
                l_end = i + blk
                while i < l_end:
                    off = i & (blk - 1)
                    bit = off >> 7
                    if (i < addr or i + 128 > addr + n) and not (mask >> bit & 1):
                        buf[off:off + 128] = self.sfi_read(i, 128)
                    i += 128
                block_start = l_end - blk
                off_addr = addr & (blk - 1)
                buf[off_addr:off_addr + n] = data[mem_pos:mem_pos + n]
                self.sfi_erase(block_start)
                self.sfi_write_cmp(block_start, None, bytes(buf))
            else:
                off_addr = addr & (blk - 1)
                self.sfi_write_cmp(addr, bytes(buf[off_addr:off_addr + n]),
                                    data[mem_pos:mem_pos + n])

            mem_pos += n
            addr += n
            if progress_cb:
                progress_cb(mem_pos, size)

    def write_flash_file(self, addr, file_path, offset=0, size=None,
                          progress_cb=None, cancel_event=None):
        with open(file_path, "rb") as f:
            f.seek(offset)
            data = f.read(size) if size else f.read()
        if size and len(data) < size:
            raise SpdError("o arquivo tem menos dados do que o tamanho solicitado")
        if not data:
            raise SpdError("nada para gravar (arquivo vazio ou tamanho 0)")
        self.write_flash_buf(data, addr, progress_cb=progress_cb, cancel_event=cancel_event)
        return len(data)
