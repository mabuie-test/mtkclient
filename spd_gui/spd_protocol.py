# -*- coding: utf-8 -*-
"""
spd_protocol.py

Reimplementação em Python (pyusb) do protocolo usado pelo `spd_dump`
(projeto open-source de Ilya Kurdyukov: spreadtrum_flash) para telefones
com chipset Spreadtrum/Unisoc (SC6530, SC6531DA, SC6531E, UMS9117...).

Este módulo cobre apenas a camada de comunicação (framing HDLC, checksum,
handshake FDL1, leitura de flash). A tradução foi feita linha a linha a
partir de spd_dump.c / spd_cmd.h para preservar exatamente o comportamento
do protocolo original.

Uso típico (telefone feature phone SC6531E/SC6530/SC6531DA):

    io = SpdIO(log_cb=print)
    io.open_usb(timeout_s=60)                   # modo USB/libusb (Zadig)
    # -- ou, sem precisar trocar driver --
    # io.open_serial("COM5", wait_s=60)          # modo porta COM/serial
    chip_id, secure = io.load_fdl1("nor_fdl1.bin", 0x40004000)
    info = identify_chip(chip_id)
    with open("flash.bin", "wb") as f:
        io.read_flash(0x80000003, 0, 0x400000, out_file=f,
                       progress_cb=lambda done, total: print(done, total))
    io.close()
"""

import json
import os
import struct
import time

try:
    import usb.core
    import usb.util
    HAVE_PYUSB = True
except Exception:  # pragma: no cover - ambiente sem pyusb instalado
    HAVE_PYUSB = False

try:
    import serial
    import serial.tools.list_ports
    HAVE_PYSERIAL = True
except Exception:  # pragma: no cover - ambiente sem pyserial instalado
    HAVE_PYSERIAL = False


# --------------------------------------------------------------------------
# Constantes do protocolo (spd_cmd.h)
# --------------------------------------------------------------------------

VENDOR_ID = 0x1782
PRODUCT_ID = 0x4d00

HDLC_HEADER = 0x7e
HDLC_ESCAPE = 0x7d

FLAGS_CRC16 = 1
FLAGS_TRANSCODE = 2

CHK_FIXZERO = 1
CHK_ORIG = 2

RECV_BUF_LEN = 8192
DEFAULT_TIMEOUT_MS = 3000
_SERIAL_POLL_INTERVAL = 0.02  # 20ms - ver SerialTransport.read()

# Comando de extensão não-oficial (só existe em FDL1 compilados com o
# patch em custom_fdl_patch/ deste projeto - ver read_jedec_id()).
MABUIE_CMD_READ_JEDEC_ID = 0x50

JEDEC_MANUFACTURERS = {
    0xEF: "Winbond",
    0xC8: "GigaDevice",
    0xC2: "Macronix",
    0x20: "Micron/ST",
    0x1F: "Adesto/Atmel",
    0x85: "Puya",
    0xA1: "Fudan Micro",
    0x0B: "XTX",
    0x68: "Boya (BOHONG)",
    0x9D: "ISSI",
}


def decode_jedec_id(raw_id):
    """
    Decodifica um JEDEC ID de 3 bytes (fabricante, tipo, capacidade),
    conforme devolvido pela extensão MABUIE_CMD_READ_JEDEC_ID: os 3 bytes
    significativos ficam nos bits 23:0 de um inteiro de 32 bits
    (fabricante nos bits 23:16 - mesma convenção já usada internamente
    pelo firmware para reconhecer Winbond/GigaDevice/Macronix).

    O terceiro byte (capacidade) segue a convenção comum a esses
    fabricantes: tamanho em bytes = 2^capacidade (ex.: 0x16 -> 4 MiB).
    """
    manufacturer = (raw_id >> 16) & 0xff
    mem_type = (raw_id >> 8) & 0xff
    capacity = raw_id & 0xff
    size_bytes = None
    if 10 <= capacity <= 27:  # faixa plausível (~1KB a 128MB)
        size_bytes = 1 << capacity
    return {
        "raw": raw_id,
        "manufacturer_id": manufacturer,
        "manufacturer_name": JEDEC_MANUFACTURERS.get(manufacturer, "desconhecido"),
        "mem_type": mem_type,
        "capacity_code": capacity,
        "size_bytes": size_bytes,
    }


class BSL:
    """Comandos e respostas do protocolo BSL (bootloader Spreadtrum)."""
    CMD_CONNECT = 0x00
    CMD_START_DATA = 0x01
    CMD_MIDST_DATA = 0x02
    CMD_END_DATA = 0x03
    CMD_EXEC_DATA = 0x04
    CMD_NORMAL_RESET = 0x05
    CMD_READ_FLASH = 0x06
    CMD_READ_CHIP_TYPE = 0x07
    CMD_READ_NVITEM = 0x08
    CMD_CHANGE_BAUD = 0x09
    CMD_ERASE_FLASH = 0x0A
    CMD_REPARTITION = 0x0B
    CMD_READ_FLASH_TYPE = 0x0C
    CMD_READ_FLASH_INFO = 0x0D
    CMD_READ_SECTOR_SIZE = 0x0F
    CMD_READ_START = 0x10
    CMD_READ_MIDST = 0x11
    CMD_READ_END = 0x12
    CMD_KEEP_CHARGE = 0x13
    CMD_EXTTABLE = 0x14
    CMD_READ_FLASH_UID = 0x15
    CMD_READ_SOFTSIM_EID = 0x16
    CMD_POWER_OFF = 0x17
    CMD_CHECK_ROOT = 0x19
    CMD_READ_CHIP_UID = 0x1A
    CMD_ENABLE_WRITE_FLASH = 0x1B
    CMD_ENABLE_SECUREBOOT = 0x1C
    CMD_IDENTIFY_START = 0x1D
    CMD_IDENTIFY_END = 0x1E
    CMD_READ_CU_REF = 0x1F
    CMD_READ_REFINFO = 0x20
    CMD_DISABLE_TRANSCODE = 0x21
    CMD_WRITE_DATETIME = 0x22
    CMD_CUST_DUMMY = 0x23
    CMD_READ_RF_TRANSCEIVER_TYPE = 0x24
    CMD_SET_DEBUGINFO = 0x25
    CMD_DDR_CHECK = 0x26
    CMD_SELF_REFRESH = 0x27
    CMD_WRITE_RAW_DATA_ENABLE = 0x28
    CMD_READ_NAND_BLOCK_INFO = 0x29
    CMD_SET_FIRST_MODE = 0x2A
    CMD_READ_PARTITION = 0x2D
    CMD_DLOAD_RAW_START = 0x31
    CMD_WRITE_FLUSH_DATA = 0x32
    CMD_DLOAD_RAW_START2 = 0x33
    CMD_READ_LOG = 0x35
    CMD_CHECK_BAUD = 0x7E
    CMD_END_PROCESS = 0x7F

    REP_ACK = 0x80
    REP_VER = 0x81
    REP_INVALID_CMD = 0x82
    REP_UNKNOW_CMD = 0x83
    REP_OPERATION_FAILED = 0x84
    REP_NOT_SUPPORT_BAUDRATE = 0x85
    REP_DOWN_NOT_START = 0x86
    REP_DOWN_MULTI_START = 0x87
    REP_DOWN_EARLY_END = 0x88
    REP_DOWN_DEST_ERROR = 0x89
    REP_DOWN_SIZE_ERROR = 0x8A
    REP_VERIFY_ERROR = 0x8B
    REP_NOT_VERIFY = 0x8C
    PHONE_NOT_ENOUGH_MEMORY = 0x8D
    PHONE_WAIT_INPUT_TIMEOUT = 0x8E
    PHONE_SUCCEED = 0x8F
    PHONE_VALID_BAUDRATE = 0x90
    PHONE_REPEAT_CONTINUE = 0x91
    PHONE_REPEAT_BREAK = 0x92
    REP_READ_FLASH = 0x93
    REP_READ_CHIP_TYPE = 0x94
    REP_READ_NVITEM = 0x95
    REP_INCOMPATIBLE_PARTITION = 0x96
    REP_SIGN_VERIFY_ERROR = 0xA6
    REP_READ_CHIP_UID = 0xAB
    REP_READ_PARTITION = 0xBA
    REP_READ_LOG = 0xBB
    REP_UNSUPPORTED_COMMAND = 0xFE
    REP_LOG = 0xFF


# IDs de região usados pelo BSL_CMD_READ_FLASH (ver comentário no topo do
# spd_cmd.h original). Úteis para popular a interface.
KNOWN_REGIONS = [
    ("PS / Flash completa (uso comum p/ dump total)", 0x80000003),
    ("BOOTLOADER", 0x80000000),
    ("NV", 0x90000001),
    ("PHASE_CHECK", 0x90000002),
    ("FLASH", 0x90000003),
    ("MMI RES", 0x90000004),
    ("ERASE_UDISK", 0x90000005),
    ("UDISK_IMG", 0x90000006),
    ("DSP_CODE", 0x90000009),
]


class SpdError(Exception):
    """Erro genérico de protocolo/comunicação."""


class SpdTimeout(SpdError):
    """Nenhuma resposta do telefone dentro do tempo limite."""


class SpdCancelled(SpdError):
    """Operação cancelada pelo usuário."""


# --------------------------------------------------------------------------
# Funções puras do protocolo (checksum / crc16 / transcode)
# Traduzidas literalmente de spd_dump.c
# --------------------------------------------------------------------------

def spd_crc16(crc, data):
    crc &= 0xffff
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ ((0 - (crc >> 15)) & 0x11021)) & 0xffffffff
    return crc & 0xffff


def spd_checksum(crc, data, final):
    """final: 0 = não finalizar; CHK_FIXZERO(1) ou CHK_ORIG(2) = finalizar."""
    n = len(data)
    i = 0
    length = n
    while length > 1:
        crc += (data[i + 1] << 8) | data[i]
        i += 2
        length -= 2
    if length:
        crc += data[i]
    if final:
        crc = (crc >> 16) + (crc & 0xffff)
        crc += crc >> 16
        crc = ~crc & 0xffff
        if length < final:
            crc = (crc >> 8) | ((crc & 0xff) << 8)
    return crc


def spd_transcode(data):
    """Aplica o escape HDLC (0x7e/0x7d -> 0x7d + byte^0x20)."""
    out = bytearray()
    for b in data:
        if b == HDLC_HEADER or b == HDLC_ESCAPE:
            out.append(HDLC_ESCAPE)
            b ^= 0x20
        out.append(b)
    return bytes(out)


# --------------------------------------------------------------------------
# Identificação de chipset a partir do CHIP ID reportado pelo FDL1.
#
# A tabela de chipsets conhecidos fica em chips.json (mesma pasta deste
# arquivo), não hardcoded aqui - isso permite adicionar suporte a novos
# chips SPD sem mexer no código Python. Veja README.md, seção "Como
# adicionar suporte a outro chipset".
# --------------------------------------------------------------------------

_CHIP_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chips.json")

# Usada apenas se chips.json não existir/estiver corrompido (fallback).
_DEFAULT_CHIP_DB = [
    {
        "name": "SC6530 / SC6530C / SC6531",
        "id_xor": 0x65300000, "id_shift": 17,
        "fw_addr": 0x34000000, "ram_addr": 0x34000000, "fdl1_addr": 0x40004000,
        "notes": "FDL1 custom incluso no projeto original (pasta custom_fdl).",
    },
    {
        "name": "SC6531E",
        "id_xor": 0x65620000, "id_shift": 16,
        "fw_addr": 0x14000000, "ram_addr": 0x14000000, "fdl1_addr": 0x40004000,
        "notes": "FDL1 custom incluso no projeto original (pasta custom_fdl).",
    },
    {
        "name": "UMS9117 (T117/T107/T127 - 4G feature phone)",
        "id_xor": 0x98180000, "id_shift": 16,
        "fw_addr": None, "ram_addr": 0x80000000, "fdl1_addr": None,
        "notes": "Requer FDL1/FDL2 extraídos do firmware oficial (.pac); "
                 "endereço de gravação (fw_addr) ainda não mapeado neste projeto.",
    },
]


def _to_int_or_none(v):
    if v is None:
        return None
    if isinstance(v, str):
        return int(v, 0)
    return int(v)


def _load_chip_db():
    if os.path.isfile(_CHIP_DB_PATH):
        try:
            with open(_CHIP_DB_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            db = []
            for e in raw:
                db.append({
                    "name": e["name"],
                    "id_xor": _to_int_or_none(e["id_xor"]),
                    "id_shift": int(e["id_shift"]),
                    "fw_addr": _to_int_or_none(e.get("fw_addr")),
                    "ram_addr": _to_int_or_none(e.get("ram_addr")),
                    "fdl1_addr": _to_int_or_none(e.get("fdl1_addr")),
                    "notes": e.get("notes", ""),
                })
            if db:
                return db
        except Exception:
            pass  # cai para o padrão embutido abaixo
    return list(_DEFAULT_CHIP_DB)


CHIP_DB = _load_chip_db()


def identify_chip(chip_id):
    """
    Procura chip_id na tabela CHIP_DB (carregada de chips.json). Cada
    entrada casa se ((chip_id ^ id_xor) >> id_shift) == 0 - mesma lógica
    de detecção usada no spd_dump.c original.
    """
    empty = {"name": "Desconhecido (sem CHIP ID)", "fw_addr": None,
             "ram_addr": None, "fdl1_addr": None, "notes": ""}
    if chip_id is None:
        return empty
    cid = chip_id & 0xffffffff
    for entry in CHIP_DB:
        if ((cid ^ entry["id_xor"]) >> entry["id_shift"]) == 0:
            return dict(entry)
    return {
        "name": "Desconhecido (CHIP ID = 0x%08x)" % cid,
        "fw_addr": None, "ram_addr": None, "fdl1_addr": None,
        "notes": "Nenhuma entrada em chips.json corresponde a este CHIP ID.",
    }


def check_custom_fdl_window(addr, size, fw_addr):
    """
    Verifica se addr está dentro da janela de 16 MB a partir de fw_addr que
    o FDL1 "custom" deste projeto (custom_fdl/main.c) trata como a flash
    SPI-NOR de verdade - confirmado lendo data_midst()/erase_flash() no
    código-fonte: fora dessa janela, uma gravação vira um memcpy comum em
    RAM (não persiste) e um apagamento é rejeitado (BSL_REP_INVALID_CMD,
    0x82). Isso é uma checagem incondicional do FDL1 custom - não tem
    relação com secure boot. Só se aplica a esse FDL1 custom de estágio
    único; não chame isto se estiver usando o FDL2 oficial do fabricante
    (endereçamento diferente).
    """
    if fw_addr is None:
        return
    if ((addr - fw_addr) & 0xffffffff) >= 0x1000000:
        raise SpdError(
            "Endereço 0x%08x fora do alcance de flash deste FDL1 custom "
            "(precisa estar entre 0x%08x e 0x%08x). Fora dessa faixa a "
            "gravação não persiste de verdade (vira escrita de RAM comum) "
            "e o apagamento é rejeitado pelo telefone. Confira o endereço "
            "ou se está usando o chipset certo." %
            (addr, fw_addr, (fw_addr + 0xFFFFFF) & 0xffffffff)
        )


# --------------------------------------------------------------------------
# Transportes: USB (libusb, exige driver WinUSB/libusbK via Zadig) e
# Serial/COM port (usa o driver de porta serial que já vier instalado -
# ex.: driver oficial "Spreadtrum U2S Diag"/VCOM - sem precisar do Zadig).
# Ambos expõem a mesma interface: write(data, timeout_ms) e
# read(max_len, timeout_ms) -> bytes (b"" em caso de timeout).
# --------------------------------------------------------------------------

class UsbTransport:
    def __init__(self, dev, ep_in, ep_out, ep_out_wmax):
        self.dev = dev
        self.ep_in = ep_in
        self.ep_out = ep_out
        self.ep_out_wmax = ep_out_wmax

    @classmethod
    def open(cls, dev):
        try:
            dev.set_configuration()
        except usb.core.USBError:
            pass  # já configurado

        cfg = dev.get_active_configuration()
        ep_in = ep_out = None
        ep_out_wmax = 0
        for intf in cfg:
            for ep in intf:
                if usb.util.endpoint_type(ep.bmAttributes) != usb.util.ENDPOINT_TYPE_BULK:
                    continue
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    if ep_in is not None:
                        raise SpdError("mais de um endpoint de entrada encontrado")
                    ep_in = ep.bEndpointAddress
                else:
                    if ep_out is not None:
                        raise SpdError("mais de um endpoint de saída encontrado")
                    ep_out = ep.bEndpointAddress
                    ep_out_wmax = ep.wMaxPacketSize
        if ep_in is None or ep_out is None:
            raise SpdError("não foi possível localizar os endpoints bulk do dispositivo")
        return cls(dev, ep_in, ep_out, ep_out_wmax)

    def write(self, data, timeout_ms):
        try:
            self.dev.write(self.ep_out, data, timeout=timeout_ms)
        except usb.core.USBError as e:
            raise SpdError("falha ao enviar dados USB: %s" % e)
        # Telefones UMS9117 esperam demais depois de um bloco de 512 bytes;
        # um pacote de tamanho 0 sinaliza o fim da transferência.
        if self.ep_out_wmax == 512 and len(data) % 512 == 0:
            try:
                self.dev.write(self.ep_out, b"", timeout=timeout_ms)
            except usb.core.USBError:
                pass

    def read(self, max_len, timeout_ms):
        try:
            data = self.dev.read(self.ep_in, max_len, timeout=timeout_ms)
        except usb.core.USBTimeoutError:
            return b""
        except usb.core.USBError as e:
            msg = str(e).lower()
            if "timed out" in msg or "timeout" in msg:
                return b""
            if "no such device" in msg or "device not found" in msg or "disconnected" in msg:
                raise SpdError("conexão com o telefone foi perdida")
            raise SpdError("falha ao ler dados USB: %s" % e)
        return bytes(data)

    def set_line_state(self, timeout_ms):
        """Necessário em alguns smartphones; inofensivo em feature phones."""
        try:
            self.dev.ctrl_transfer(0x21, 34, 0x601, 0, None, timeout=timeout_ms)
        except usb.core.USBError:
            pass

    def close(self):
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass


class SerialTransport:
    """
    Transporte via porta COM. Útil quando o telefone já é exposto como uma
    porta serial pelo driver oficial do fabricante (ex.: "Spreadtrum U2S
    Diag" / VCOM), evitando ter que trocar o driver com o Zadig.
    """

    def __init__(self, ser):
        self.ser = ser
        self._cached_write_timeout = None
        self._cached_read_timeout = None

    @classmethod
    def open(cls, port, baudrate=115200):
        if not HAVE_PYSERIAL:
            raise SpdError(
                "O pacote 'pyserial' não está instalado. Instale com: pip install pyserial"
            )
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baudrate
            ser.bytesize = serial.EIGHTBITS
            ser.parity = serial.PARITY_NONE
            ser.stopbits = serial.STOPBITS_ONE
            ser.xonxoff = False
            ser.rtscts = False
            ser.dsrdtr = False
            ser.timeout = _SERIAL_POLL_INTERVAL
            ser.write_timeout = 1.0
            ser.open()
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception as e:
            raise SpdError("não foi possível abrir a porta %s: %s" % (port, e))
        return cls(ser)

    def write(self, data, timeout_ms):
        try:
            wt = max(timeout_ms, 1) / 1000.0
            # Só reconfigura a porta se o valor realmente mudou - setar
            # ser.write_timeout sempre (mesmo com o mesmo valor) dispara uma
            # reconfiguração da porta a cada chamada, o que é desnecessário
            # e soma um custo real quando há milhares de blocos.
            if wt != self._cached_write_timeout:
                self.ser.write_timeout = wt
                self._cached_write_timeout = wt
            self.ser.write(data)
        except Exception as e:
            raise SpdError("falha ao enviar dados na porta serial: %s" % e)

    def read(self, max_len, timeout_ms):
        """
        Lê até max_len bytes, respeitando timeout_ms como prazo TOTAL.

        Importante: NÃO usamos ser.timeout = timeout_ms diretamente com um
        único ser.read(max_len). No Windows/pyserial, um read() com timeout
        fixo espera até acumular max_len bytes OU o timeout inteiro
        esgotar - ou seja, qualquer resposta menor que max_len (quase toda
        mensagem do protocolo, já que max_len usa um buffer grande) ficava
        bloqueada até o timeout completo (por padrão 1000ms) mesmo com os
        dados já disponíveis. Em milhares de blocos, isso sozinho explicava
        a maior parte da lentidão no modo serial.

        Em vez disso, fazemos polling com um intervalo curto
        (_SERIAL_POLL_INTERVAL): assim que o primeiro byte chega, drenamos
        imediatamente o que já estiver no buffer do SO (sem bloquear mais)
        e retornamos - o laço de parsing (recv_msg1) chama read() de novo
        se precisar de mais bytes.
        """
        if self._cached_read_timeout != _SERIAL_POLL_INTERVAL:
            self.ser.timeout = _SERIAL_POLL_INTERVAL
            self._cached_read_timeout = _SERIAL_POLL_INTERVAL

        deadline = time.time() + max(timeout_ms, 1) / 1000.0
        try:
            while True:
                data = self.ser.read(1)
                if data:
                    avail = self.ser.in_waiting
                    if avail:
                        extra_len = min(avail, max_len - 1)
                        if extra_len > 0:
                            data += self.ser.read(extra_len)
                    return data
                if time.time() >= deadline:
                    return b""
        except Exception as e:
            raise SpdError("falha ao ler dados da porta serial: %s" % e)

    def set_line_state(self, timeout_ms):
        pass  # não se aplica ao modo serial

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def list_serial_ports():
    """Lista as portas COM disponíveis (nome, descrição, hwid)."""
    if not HAVE_PYSERIAL:
        return []
    ports = []
    for p in serial.tools.list_ports.comports():
        ports.append({"device": p.device, "description": p.description, "hwid": p.hwid})
    return ports


def guess_serial_port():
    """
    Tenta achar automaticamente uma porta COM que corresponda ao VID:PID do
    telefone (1782:4d00) - funciona se o driver instalado preservar o
    VID/PID original no descritor USB (comum em drivers VCOM do fabricante).
    Retorna o nome da porta (ex.: 'COM5') ou None se não achar com certeza.
    """
    candidates = []
    for p in list_serial_ports():
        hwid = (p["hwid"] or "").upper()
        if "1782" in hwid and "4D00" in hwid:
            candidates.append(p["device"])
    return candidates[0] if len(candidates) == 1 else None


def probe_serial_ports(baudrate=921600, per_port_timeout_s=1.2,
                        cancel_event=None, log_cb=None, ports=None):
    """
    Detecção automática "de verdade": em vez de só olhar o VID/PID
    reportado pelo driver (que muitos drivers VCOM não preservam), testa
    cada porta COM disponível com um handshake curto de verdade (envia o
    ping de check-baud e espera uma resposta BSL_REP_VER válida) - o
    mesmo primeiro passo de load_fdl1(), sem carregar nada ainda.

    Retorna o nome da porta que respondeu (ex.: 'COM5'), ou None se
    nenhuma responder dentro do tempo testado.
    """
    if ports is None:
        ports = [p["device"] for p in list_serial_ports()]
    for port in ports:
        if cancel_event is not None and cancel_event.is_set():
            raise SpdCancelled()
        if log_cb:
            log_cb("Testando %s..." % port)
        try:
            transport = SerialTransport.open(port, baudrate=baudrate)
        except SpdError:
            continue
        try:
            io = SpdIO()
            io.transport = transport
            io.flags = FLAGS_TRANSCODE | FLAGS_CRC16
            io.timeout = int(per_port_timeout_s * 1000)
            io._send_check_baud(1)
            raw = io.recv_msg()
            if raw is not None and io._recv_type() == BSL.REP_VER:
                return port
        except SpdError:
            pass
        finally:
            transport.close()
    return None


# --------------------------------------------------------------------------
# Camada de E/S USB
# --------------------------------------------------------------------------

class SpdIO:
    """
    Gerencia a conexão USB com o telefone em modo boot (1782:4d00) e
    implementa o framing HDLC + handshake FDL do protocolo Spreadtrum.
    """

    def __init__(self, log_cb=None):
        self.transport = None
        self.flags = 0
        self.verbose = 0
        self.timeout = DEFAULT_TIMEOUT_MS
        self._rx_buf = b""
        self._rx_pos = 0
        self.raw_buf = b""
        self._log_cb = log_cb or (lambda msg: None)

    # -- ciclo de vida ----------------------------------------------------

    def _log(self, msg):
        try:
            self._log_cb(msg)
        except Exception:
            pass

    @staticmethod
    def wait_for_device_usb(timeout_s=60, poll_interval=0.5, cancel_event=None, log_cb=None):
        """Bloqueia até encontrar o dispositivo USB 1782:4d00 ou expirar o tempo."""
        if not HAVE_PYUSB:
            raise SpdError(
                "O pacote 'pyusb' não está instalado. Instale com: pip install pyusb"
            )
        deadline = time.time() + timeout_s if timeout_s else None
        first = True
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if dev is not None:
                return dev
            if first and log_cb:
                log_cb("Aguardando o telefone conectar em modo boot (1782:4d00)...")
                first = False
            if deadline is not None and time.time() >= deadline:
                raise SpdTimeout("Tempo esgotado esperando o telefone conectar.")
            time.sleep(poll_interval)

    def open(self, timeout_s=60, cancel_event=None):
        """Modo USB/libusb (requer driver WinUSB/libusbK - Zadig)."""
        self.open_usb(timeout_s=timeout_s, cancel_event=cancel_event)

    def open_usb(self, timeout_s=60, cancel_event=None):
        dev = self.wait_for_device_usb(timeout_s=timeout_s, cancel_event=cancel_event, log_cb=self._log)
        self.transport = UsbTransport.open(dev)
        self.flags = FLAGS_TRANSCODE
        self._rx_buf = b""
        self._rx_pos = 0
        self._log("Dispositivo conectado via USB (endpoints IN=0x%02x OUT=0x%02x)"
                   % (self.transport.ep_in, self.transport.ep_out))

    def open_serial(self, port, baudrate=115200, wait_s=0, poll_interval=0.5, cancel_event=None):
        """
        Modo porta COM - usa o driver serial que já estiver instalado
        (ex.: driver oficial "Spreadtrum U2S Diag"/VCOM), sem precisar do
        Zadig/WinUSB. `port` é o nome da porta (ex.: 'COM5').
        Se `wait_s` > 0, tenta reabrir a porta repetidamente até o telefone
        responder (útil se a porta só aparece quando o telefone está
        conectado em modo boot).
        """
        deadline = time.time() + wait_s if wait_s else None
        last_err = None
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            try:
                self.transport = SerialTransport.open(port, baudrate=baudrate)
                break
            except SpdError as e:
                last_err = e
                if deadline is None or time.time() >= deadline:
                    raise
                time.sleep(poll_interval)
        self.flags = FLAGS_TRANSCODE
        self._rx_buf = b""
        self._rx_pos = 0
        self._log("Dispositivo conectado via porta serial %s (%d bps)" % (port, baudrate))

    def close(self):
        if self.transport is not None:
            self.transport.close()
        self.transport = None

    # -- framing HDLC -------------------------------------------------------

    def _build_raw(self, cmd_type, data):
        if len(data) > 0xffff:
            raise SpdError("mensagem muito longa")
        raw = struct.pack(">HH", cmd_type, len(data)) + bytes(data)
        if self.flags & FLAGS_CRC16:
            chk = spd_crc16(0, raw)
        else:
            chk = spd_checksum(0, raw, CHK_FIXZERO)
        raw += struct.pack(">H", chk & 0xffff)
        return raw

    def _encode(self, cmd_type, data=b""):
        raw = self._build_raw(cmd_type, data)
        body = spd_transcode(raw) if (self.flags & FLAGS_TRANSCODE) else raw
        return bytes([HDLC_HEADER]) + body + bytes([HDLC_HEADER])

    def _write(self, pkt):
        if self.verbose >= 2:
            self._log("send (%d): %s" % (len(pkt), pkt.hex()))
        if self.transport is None:
            raise SpdError("nenhuma conexão aberta")
        self.transport.write(pkt, self.timeout)

    def _send(self, cmd_type, data=b""):
        self._write(self._encode(cmd_type, data))

    def _send_check_baud(self, n):
        self._write(bytes([HDLC_HEADER]) * n)

    # -- recepção -------------------------------------------------------

    def _fill_rx(self):
        if self.transport is None:
            raise SpdError("nenhuma conexão aberta")
        data = self.transport.read(RECV_BUF_LEN, self.timeout)
        self._rx_buf = data
        self._rx_pos = 0
        if self.verbose >= 2 and self._rx_buf:
            self._log("recv (%d): %s" % (len(self._rx_buf), self._rx_buf.hex()))
        return len(self._rx_buf) > 0

    def _recv_msg1(self):
        esc = 0
        head_found = False
        nread = 0
        plen = 6
        raw = bytearray()
        while True:
            if self._rx_pos >= len(self._rx_buf):
                if not self._fill_rx():
                    break
                if not self._rx_buf:
                    break
            a = self._rx_buf[self._rx_pos]
            self._rx_pos += 1

            if self.flags & FLAGS_TRANSCODE:
                if esc and a != (HDLC_HEADER ^ 0x20) and a != (HDLC_ESCAPE ^ 0x20):
                    raise SpdError("byte de escape inesperado (0x%02x)" % a)
                if a == HDLC_HEADER:
                    if not head_found:
                        head_found = True
                    elif not nread:
                        continue
                    elif nread < plen:
                        raise SpdError("mensagem recebida é muito curta")
                    else:
                        break
                elif a == HDLC_ESCAPE:
                    esc = 0x20
                else:
                    if not head_found:
                        continue
                    if nread >= plen:
                        raise SpdError("mensagem recebida é muito longa")
                    raw.append(a ^ esc)
                    nread += 1
                    esc = 0
            else:
                if not head_found and a == HDLC_HEADER:
                    head_found = True
                    continue
                if nread == plen:
                    if a != HDLC_HEADER:
                        raise SpdError("esperava-se o fim da mensagem")
                    break
                raw.append(a)
                nread += 1

            if nread == 4:
                plen = struct.unpack(">H", bytes(raw[2:4]))[0] + 6

        if not nread:
            return None

        if nread < 6:
            raise SpdError("mensagem recebida é muito curta")
        if nread != plen:
            raise SpdError("tamanho inválido (%d, esperado %d)" % (nread, plen))

        if self.flags & FLAGS_CRC16:
            chk = spd_crc16(0, bytes(raw[:plen - 2]))
        else:
            chk = spd_checksum(0, bytes(raw[:plen - 2]), CHK_ORIG)
        got = struct.unpack(">H", bytes(raw[plen - 2:plen]))[0]
        if got != (chk & 0xffff):
            raise SpdError("checksum inválido (0x%04x, esperado 0x%04x)" % (got, chk & 0xffff))
        return bytes(raw[:plen])

    def recv_msg(self):
        while True:
            raw = self._recv_msg1()
            if raw is None:
                return None
            self.raw_buf = raw
            if self._recv_type() != BSL.REP_LOG:
                return raw
            n = struct.unpack(">H", raw[2:4])[0]
            self._log("BSL_REP_LOG: %r" % raw[4:4 + n])

    def recv_msg_timeout(self, timeout_ms):
        old = self.timeout
        self.timeout = max(old, timeout_ms)
        try:
            return self.recv_msg()
        finally:
            self.timeout = old

    def _recv_type(self):
        if len(self.raw_buf) < 6:
            return -1
        return struct.unpack(">H", self.raw_buf[0:2])[0]

    def _send_and_check(self, cmd_type, data=b"", timeout_ms=None):
        self._send(cmd_type, data)
        if timeout_ms is not None:
            raw = self.recv_msg_timeout(timeout_ms)
        else:
            raw = self.recv_msg()
        if raw is None:
            raise SpdTimeout("tempo limite atingido aguardando resposta")
        t = self._recv_type()
        if t != BSL.REP_ACK:
            raise SpdError("resposta inesperada do telefone (0x%02x)" % t)
        return raw

    # -- operações de alto nível -----------------------------------------

    def send_buf(self, start_addr, data, end_data=True, step=528,
                 progress_cb=None, cancel_event=None):
        self._send_and_check(BSL.CMD_START_DATA, struct.pack(">II", start_addr, len(data)))
        total = len(data)
        for i in range(0, total, step):
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            chunk = data[i:i + step]
            self._send_and_check(BSL.CMD_MIDST_DATA, chunk)
            if progress_cb:
                progress_cb(min(i + step, total), total)
        if end_data:
            self._send_and_check(BSL.CMD_END_DATA)

    def load_fdl1(self, fdl_path, addr=0x40004000, progress_cb=None,
                   cancel_event=None):
        """
        Executa o handshake inicial completo: liga em modo CRC16, envia o
        FDL1 (custom_fdl/nor_fdl1.bin ou original), executa e troca para o
        modo de checksum do FDL1, lendo o CHIP ID reportado.

        Retorna (chip_id ou None, secure_boot: bool).
        """
        with open(fdl_path, "rb") as f:
            fdl_data = f.read()
        if not fdl_data:
            raise SpdError("arquivo FDL vazio ou não encontrado: %s" % fdl_path)

        # Necessário para smartphones; inofensivo em feature phones. Só se
        # aplica ao transporte USB (no modo serial é um no-op).
        self.transport.set_line_state(self.timeout)

        self.flags |= FLAGS_CRC16

        self._send_check_baud(1)
        raw = self.recv_msg()
        if raw is None:
            raise SpdTimeout("o telefone não respondeu ao ping inicial (checkbaud)")
        if self._recv_type() != BSL.REP_VER:
            raise SpdError("esperava-se BSL_REP_VER na resposta inicial")
        n = struct.unpack(">H", raw[2:4])[0]
        ver = raw[4:4 + n]
        self._log("BSL_REP_VER: %r" % ver)
        secure_boot = not (n == 6 and ver == b"SPRD3\x00")

        self._send_and_check(BSL.CMD_CONNECT)

        self.send_buf(addr, fdl_data, end_data=True, step=528,
                      progress_cb=progress_cb, cancel_event=cancel_event)

        self._send_and_check(BSL.CMD_EXEC_DATA)

        # FDL1 usa checksum simples (não CRC16).
        self.flags &= ~FLAGS_CRC16

        ping = bytes([HDLC_HEADER]) * 4
        raw = None
        for i in range(10):
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            self._write(ping)
            raw = self.recv_msg()
            if raw is not None:
                break
        if raw is None:
            raise SpdTimeout("o FDL1 não respondeu depois de carregado")
        if self._recv_type() != BSL.REP_VER:
            raise SpdError("esperava-se BSL_REP_VER depois do FDL1")

        n = struct.unpack(">H", raw[2:4])[0]
        ver = raw[4:4 + n]
        self._log("BSL_REP_VER (FDL1): %r" % ver)

        chip_id = None
        if n and ver.endswith(b"\x00"):
            text = ver.decode("latin1", errors="replace")
            marker = "CHIP ID = 0x"
            idx = text.find(marker)
            if idx != -1:
                rest = text[idx + len(marker):]
                digits = ""
                for ch in rest:
                    if ch in "0123456789abcdefABCDEF":
                        digits += ch
                    else:
                        break
                if digits:
                    chip_id = int(digits, 16)

        self._send_and_check(BSL.CMD_CONNECT)
        return chip_id, secure_boot

    def load_next_stage(self, fdl_path, addr, step=528, progress_cb=None,
                         cancel_event=None, exec_timeout_ms=15000):
        """Carrega um segundo estágio (FDL2) depois que load_fdl1() já rodou."""
        with open(fdl_path, "rb") as f:
            data = f.read()
        if not data:
            raise SpdError("arquivo FDL vazio ou não encontrado: %s" % fdl_path)
        self.send_buf(addr, data, end_data=True, step=step,
                      progress_cb=progress_cb, cancel_event=cancel_event)
        self._send(BSL.CMD_EXEC_DATA)
        raw = self.recv_msg_timeout(exec_timeout_ms)
        if raw is None:
            raise SpdTimeout("tempo limite atingido aguardando o segundo estágio iniciar")
        t = self._recv_type()
        if t == BSL.REP_INCOMPATIBLE_PARTITION:
            self._log("FDL2: partição incompatível (mensagem do telefone, geralmente pode ser ignorada)")
        elif t != BSL.REP_ACK:
            raise SpdError("resposta inesperada do telefone (0x%02x)" % t)

    def read_flash(self, addr, start, length, out_file=None, step=1024,
                    progress_cb=None, cancel_event=None):
        """
        Lê `length` bytes a partir de `start` na região `addr`
        (ex.: 0x80000003 = PS/flash completa). Se `out_file` for None,
        retorna os bytes lidos; senão escreve neles.
        """
        offset = start
        end = start + length
        buf = bytearray() if out_file is None else None
        while offset < end:
            if cancel_event is not None and cancel_event.is_set():
                raise SpdCancelled()
            n = min(step, end - offset)
            self._send(BSL.CMD_READ_FLASH, struct.pack(">III", addr, n, offset))
            raw = self.recv_msg()
            if raw is None:
                raise SpdTimeout("tempo limite atingido durante a leitura da flash")
            if self._recv_type() != BSL.REP_READ_FLASH:
                raise SpdError("resposta inesperada durante leitura (0x%02x)" % self._recv_type())
            nread = struct.unpack(">H", raw[2:4])[0]
            if n < nread:
                raise SpdError("tamanho de dados inesperado recebido do telefone")
            chunk = raw[4:4 + nread]
            if out_file is not None:
                out_file.write(chunk)
            else:
                buf.extend(chunk)
            offset += nread
            if progress_cb:
                progress_cb(offset - start, length)
            if n != nread:
                break
        return offset - start, (bytes(buf) if buf is not None else None)

    # -- partições (só FDL2 oficial do fabricante - custom_fdl não implementa) --

    @staticmethod
    def _encode_partition_name(name):
        """Nome da partição como usado pelo protocolo: 36 uint16 (72 bytes)
        em UTF-16LE, preenchido com zeros."""
        raw = name.encode("utf-16-le")
        if len(raw) > 72:
            raise SpdError("nome de partição muito longo (máx. 35 caracteres)")
        return raw + b"\x00" * (72 - len(raw))

    def _build_partition_pkt(self, name, size, mode64):
        name_bytes = self._encode_partition_name(name)
        if mode64:
            # nome(72) + size(4) + size_hi(4) + dummy(8), tudo little-endian
            return name_bytes + struct.pack("<IIQ", size & 0xffffffff,
                                             (size >> 32) & 0xffffffff, 0)
        return name_bytes + struct.pack("<I", size & 0xffffffff)

    def list_partitions(self):
        """
        Lista as partições reportadas pelo FDL2 (BSL_CMD_READ_PARTITION).
        Só funciona com o FDL2 oficial do fabricante carregado como
        segundo estágio - o FDL1 "custom" deste projeto não implementa
        esse comando (dá BSL_REP_UNKNOWN_CMD).

        Retorna uma lista de dicts {"name": str, "size_raw": int}. O
        tamanho já vem em bytes; a última partição normalmente representa
        "o resto do espaço" e seu valor não deve ser lido como tamanho
        literal (mesma convenção do spd_dump original).
        """
        self._send(BSL.CMD_READ_PARTITION)
        raw = self.recv_msg()
        if raw is None:
            raise SpdTimeout("tempo limite atingido listando partições")
        if self._recv_type() != BSL.REP_READ_PARTITION:
            raise SpdError(
                "resposta inesperada ao listar partições (0x%02x) - este "
                "comando só funciona com o FDL2 oficial do fabricante "
                "carregado como segundo estágio, não com o FDL1 custom "
                "deste projeto." % self._recv_type()
            )
        size = struct.unpack(">H", raw[2:4])[0]
        if size % 0x4c:
            raise SpdError("tamanho de resposta inválido (não é múltiplo de 0x4c)")
        n = size // 0x4c
        entries = []
        body = raw[4:4 + size]
        for i in range(n):
            chunk = body[i * 0x4c:(i + 1) * 0x4c]
            name = chunk[:72].decode("utf-16-le", errors="replace").split("\x00")[0]
            part_size = struct.unpack("<I", chunk[72:76])[0]
            entries.append({"name": name, "size_raw": part_size})
        return entries

    def read_partition(self, name, start, length, out_file=None, step=4096,
                        progress_cb=None, cancel_event=None):
        """
        Lê `length` bytes a partir de `start` dentro da partição `name`
        (BSL_CMD_READ_START/READ_MIDST/READ_END). Só funciona com o FDL2
        oficial do fabricante - ver list_partitions().
        """
        mode64 = ((start + length) >> 32) != 0
        pkt = self._build_partition_pkt(name, start + length, mode64)
        self._send_and_check(BSL.CMD_READ_START, pkt)

        offset = start
        end = start + length
        buf = bytearray() if out_file is None else None
        while offset < end:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    self._send_and_check(BSL.CMD_READ_END)
                except SpdError:
                    pass
                raise SpdCancelled()
            n = min(step, end - offset)
            if mode64:
                data = struct.pack("<III", n, offset & 0xffffffff, (offset >> 32) & 0xffffffff)
            else:
                data = struct.pack("<II", n, offset & 0xffffffff)
            self._send(BSL.CMD_READ_MIDST, data)
            raw = self.recv_msg()
            if raw is None:
                raise SpdTimeout("tempo limite atingido durante a leitura da partição")
            if self._recv_type() != BSL.REP_READ_FLASH:
                raise SpdError(
                    "resposta inesperada durante leitura da partição (0x%02x)"
                    % self._recv_type()
                )
            nread = struct.unpack(">H", raw[2:4])[0]
            if n < nread:
                raise SpdError("tamanho de dados inesperado recebido do telefone")
            chunk = raw[4:4 + nread]
            if out_file is not None:
                out_file.write(chunk)
            else:
                buf.extend(chunk)
            offset += nread
            if progress_cb:
                progress_cb(offset - start, length)
            if n != nread:
                break

        self._send_and_check(BSL.CMD_READ_END)
        return offset - start, (bytes(buf) if buf is not None else None)

    def erase_partition(self, name, mode64=False, timeout_ms=60000):
        """
        Apaga uma partição inteira pelo nome (equivalente ao
        'erase_partition' do spd_dump original) - reaproveita o mesmo
        comando BSL_CMD_ERASE_FLASH que erase_flash() usa para endereços
        brutos, mas com um payload de nome de partição (igual
        read_partition) em vez de addr+size; o FDL2 reconhece qual dos
        dois formatos é pelo tamanho do payload. O tamanho não precisa
        ser informado - o FDL2 já sabe o tamanho real da partição pela
        própria tabela de partições, o que torna isto mais preciso e
        seguro do que apagar um intervalo de endereços "no chute".

        Só funciona com o FDL2 oficial do fabricante - ver
        list_partitions(). Apagar pode demorar (mesmo motivo do
        erase_flash por endereço), por isso o timeout padrão é generoso.
        """
        pkt = self._build_partition_pkt(name, 0, mode64)
        self._send_and_check(BSL.CMD_ERASE_FLASH, pkt, timeout_ms=timeout_ms)

    def dump_flash_auto(self, addr, start, out_path, step=1024,
                         progress_cb=None, cancel_event=None):
        """
        Igual a read_flash, mas descobre o tamanho automaticamente a partir
        do cabeçalho da partição (DHTB, usado nos 4G T117/T107/T127, ou
        VNTS/NV). Equivalente ao modo 'auto' do spd_dump original.
        """
        with open(out_path, "wb") as fo:
            header_len = 0x34
            nread, _ = self.read_flash(addr, start, header_len, out_file=fo, step=step)
            if nread != header_len:
                raise SpdError("não foi possível ler o cabeçalho da partição")
            fo.flush()
            with open(out_path, "rb") as fchk:
                header = fchk.read(header_len)

            if header[0:4] == b"DHTB" and struct.unpack("<I", header[4:8])[0] == 1:
                length = struct.unpack("<I", header[0x30:0x34])[0]
                if length & 0x80000000:
                    raise SpdError("tamanho DHTB inesperado")
                length += 0x200
            elif header[0:4] == b"VNTS":
                nblk = struct.unpack("<H", header[12:14])[0]
                blk = struct.unpack("<H", header[14:16])[0]
                if nblk < 4:
                    raise SpdError("cabeçalho VNTS inesperado")
                if (blk & (blk - 1)) or blk < 0x100:
                    raise SpdError("tamanho de bloco VNTS inesperado")
                length = blk * nblk
            else:
                raise SpdError(
                    "não foi possível determinar o tamanho automaticamente "
                    "(cabeçalho desconhecido) - informe um tamanho manualmente"
                )

            more, _ = self.read_flash(addr, start + nread, length - nread,
                                       out_file=fo, step=step,
                                       progress_cb=progress_cb, cancel_event=cancel_event)
            nread += more
        return nread

    @staticmethod
    def _check_secure(addr, fw_addr, secure_boot):
        """
        Replica a macro CHECK_SECURE do spd_dump.c: recusa gravar/apagar
        muito perto do início da área de firmware (fw_addr) quando o
        telefone está com secure boot ativo, pois isso pode inutilizá-lo
        permanentemente.
        """
        if fw_addr is not None and secure_boot:
            if ((addr - fw_addr) & 0xffffffff) < 0x10000:
                raise SpdError(
                    "Esta gravação ficaria muito perto do início da área de "
                    "firmware (0x%08x) com secure boot ativo - isso pode "
                    "inutilizar o aparelho permanentemente. Operação "
                    "cancelada por segurança." % fw_addr
                )

    def write_flash(self, addr, data, step=528, fw_addr=None, secure_boot=False,
                     progress_cb=None, cancel_event=None):
        """
        Grava `data` a partir do endereço `addr` (tipicamente o endereço
        de firmware/flash mapeado em memória, ex.: fw_addr identificado
        por identify_chip - 0x34000000 p/ SC6530, 0x14000000 p/ SC6531E).
        Equivalente ao comando 'write_data' do spd_dump original.
        """
        self._check_secure(addr, fw_addr, secure_boot)
        self.send_buf(addr, data, end_data=True, step=step,
                      progress_cb=progress_cb, cancel_event=cancel_event)

    def write_flash_file(self, addr, file_path, offset=0, size=None, step=528,
                          fw_addr=None, secure_boot=False, progress_cb=None,
                          cancel_event=None):
        with open(file_path, "rb") as f:
            f.seek(offset)
            data = f.read(size) if size else f.read()
        if size and len(data) < size:
            raise SpdError("o arquivo tem menos dados do que o tamanho solicitado")
        if not data:
            raise SpdError("nada para gravar (arquivo vazio ou tamanho 0)")
        self.write_flash(addr, data, step=step, fw_addr=fw_addr, secure_boot=secure_boot,
                          progress_cb=progress_cb, cancel_event=cancel_event)
        return len(data)

    def erase_flash(self, addr, size, fw_addr=None, secure_boot=False, timeout_ms=None):
        """
        Equivalente ao comando 'erase_flash' do spd_dump original
        (BSL_CMD_ERASE_FLASH). Apagar flash NOR é uma operação de hardware
        bloqueante e pode ser bem lenta (o FDL1 só responde depois de
        apagar tudo) - por padrão usamos um timeout generoso, proporcional
        ao tamanho, em vez do timeout curto padrão das outras operações.
        """
        self._check_secure(addr, fw_addr, secure_boot)
        if timeout_ms is None:
            # ~500ms por bloco de 4KB no pior caso, mais uma margem base -
            # apagar NOR é bem mais lento que ler/gravar a mesma região.
            blocks = max(1, (size + 0xFFF) // 0x1000)
            timeout_ms = max(20000, 15000 + blocks * 500)
        self._send_and_check(BSL.CMD_ERASE_FLASH, struct.pack(">II", addr, size),
                              timeout_ms=timeout_ms)

    def keep_charge(self):
        self._send_and_check(BSL.CMD_KEEP_CHARGE)

    def disable_transcode(self):
        self._send_and_check(BSL.CMD_DISABLE_TRANSCODE)
        self.flags &= ~FLAGS_TRANSCODE

    def normal_reset(self):
        self._send_and_check(BSL.CMD_NORMAL_RESET)

    def power_off(self):
        self._send_and_check(BSL.CMD_POWER_OFF)

    def read_jedec_id(self):
        """
        Lê o JEDEC ID da flash SPI-NOR (fabricante + tipo + capacidade).

        Requer um FDL1 compilado com o patch de extensão do MabuiETool SPD
        (ver custom_fdl_patch/) - o FDL1 "custom" padrão do projeto
        original NÃO tem esse comando e vai responder "comando
        desconhecido"/"comando inválido", nesse caso levantamos SpdError
        com uma mensagem explicando isso, em vez de um código cru.
        """
        self._send(MABUIE_CMD_READ_JEDEC_ID)
        raw = self.recv_msg()
        if raw is None:
            raise SpdTimeout("tempo limite atingido lendo o JEDEC ID")
        t = self._recv_type()
        if t in (BSL.REP_UNKNOWN_CMD, BSL.REP_INVALID_CMD, BSL.REP_UNSUPPORTED_COMMAND):
            raise SpdError(
                "este FDL1 não suporta a leitura do JEDEC ID (0x%02x) - "
                "é preciso recompilar o FDL1 custom com o patch de extensão "
                "(ver custom_fdl_patch/README_PATCH_JEDEC.md)" % t
            )
        if t != BSL.REP_READ_FLASH:
            raise SpdError("resposta inesperada lendo o JEDEC ID (0x%02x)" % t)
        n = struct.unpack(">H", raw[2:4])[0]
        if n != 4:
            raise SpdError("tamanho de resposta inesperado para o JEDEC ID (%d bytes)" % n)
        value = struct.unpack(">I", raw[4:8])[0]
        return decode_jedec_id(value)
