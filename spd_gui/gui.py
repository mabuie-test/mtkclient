# -*- coding: utf-8 -*-
"""
gui.py - Interface gráfica (PySide6) para dump e gravação de firmware de
feature phones com chipset Spreadtrum/Unisoc (SC6530, SC6531DA, SC6531E,
UMS9117).

Usa spd_protocol.py como camada de comunicação. Toda a comunicação com o
telefone (USB ou porta COM) roda em uma QThread separada para não travar a
interface.
"""

import os
import sys
import threading
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QLineEdit, QPushButton, QLabel, QComboBox,
    QCheckBox, QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox,
    QSpinBox, QTabWidget, QScrollArea,
)

import spd_protocol as spd
import spd_pac
import mtk_protocol as mtk


APP_ORG = "MabuieTool"
APP_NAME = "MabuieTool_SPD"


# --------------------------------------------------------------------------
# Tema visual (QSS) - paleta escura/profissional.
# --------------------------------------------------------------------------

_STYLE_SHEET = """
QMainWindow, QScrollArea, QWidget#rootArea {
    background-color: #12141c;
}
QWidget {
    background-color: transparent;
    color: #e7e9f3;
    font-family: "Segoe UI", "Cantarell", "Ubuntu", sans-serif;
    font-size: 10pt;
}
QLabel {
    color: #cdd1e0;
}
QLabel#brandTitle {
    color: #35d0c0;
    font-size: 17pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#brandSubtitle {
    color: #8b90a8;
    font-size: 9pt;
    padding-bottom: 4px;
}
QLabel#statusLabel {
    color: #35d0c0;
    font-weight: 700;
    font-size: 10.5pt;
    padding: 2px 0;
}
QLabel#chipLabel {
    color: #c9a94a;
    font-weight: 600;
}
QGroupBox {
    background-color: #1a1d29;
    border: 1px solid #2b2f42;
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
    font-weight: 700;
    color: #9aa0bd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -2px;
    padding: 0 8px;
    color: #35d0c0;
    background-color: #12141c;
}
QTabWidget::pane {
    border: 1px solid #2b2f42;
    border-radius: 10px;
    background-color: #1a1d29;
    top: -1px;
}
QTabBar::tab {
    background-color: #1a1d29;
    color: #8b90a8;
    border: 1px solid #2b2f42;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #232741;
    color: #35d0c0;
}
QTabBar::tab:hover {
    color: #e7e9f3;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: #0d0f16;
    border: 1px solid #333750;
    border-radius: 6px;
    padding: 5px 7px;
    color: #f1f2f8;
    selection-background-color: #35d0c0;
    selection-color: #0d0f16;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: #5a5f78;
    background-color: #0d0e13;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #35d0c0;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QPlainTextEdit {
    font-family: "Consolas", "Cascadia Mono", monospace;
}
QPushButton {
    background-color: #232741;
    color: #e7e9f3;
    border: 1px solid #383c58;
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2b3050;
    border: 1px solid #35d0c0;
}
QPushButton:pressed {
    background-color: #1a1d29;
}
QPushButton:disabled {
    background-color: #191b24;
    color: #565a70;
    border: 1px solid #24263a;
}
QPushButton#primaryButton {
    background-color: #12746b;
    border: 1px solid #17a598;
    color: #eafffb;
    font-size: 10.5pt;
    padding: 10px 16px;
}
QPushButton#primaryButton:hover {
    background-color: #158b80;
}
QPushButton#dangerButton {
    background-color: #6e1a22;
    border: 1px solid #a3313c;
    color: #ffecec;
    font-size: 10.5pt;
    padding: 10px 16px;
}
QPushButton#dangerButton:hover {
    background-color: #8a212b;
}
QPushButton#dangerButton:disabled {
    background-color: #241418;
    color: #6b4249;
    border: 1px solid #3a2229;
}
QCheckBox, QRadioButton {
    color: #d5d8e6;
    spacing: 8px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #454a68;
    border-radius: 4px;
    background-color: #0d0f16;
}
QCheckBox::indicator:checked {
    background-color: #35d0c0;
    border: 1px solid #35d0c0;
}
QProgressBar {
    background-color: #0d0f16;
    border: 1px solid #2b2f42;
    border-radius: 6px;
    text-align: center;
    color: #e7e9f3;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #35d0c0;
    border-radius: 5px;
}
QScrollBar:vertical {
    background: #12141c;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2b2f42;
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #383c58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QMessageBox {
    background-color: #1a1d29;
}
"""


def _wrap(layout):
    w = QWidget()
    w.setLayout(layout)
    return w


def _form_layout(parent):
    """
    QFormLayout padronizado: rótulos alinhados à esquerda, campos esticando
    para preencher a largura disponível, espaçamento consistente - em vez
    do padrão do Qt (campos estreitos, sobra vazia à direita).
    """
    form = QFormLayout(parent)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(8)
    return form


def parse_int(text, field_name):
    text = text.strip()
    if not text:
        raise ValueError("%s não pode ficar vazio" % field_name)
    try:
        return int(text, 0)
    except ValueError:
        raise ValueError("%s inválido: %r (use decimal ou 0x hexadecimal)" % (field_name, text))


def parse_int_opt(text, field_name):
    """Como parse_int, mas retorna None se o campo estiver vazio."""
    text = text.strip()
    if not text:
        return None
    return parse_int(text, field_name)


def _connect_io(io, p, cancel_event):
    """Abre a conexão (USB ou porta serial) de acordo com os parâmetros."""
    if p["conn_mode"] == "usb":
        io.open_usb(timeout_s=p["wait_timeout"], cancel_event=cancel_event)
    else:
        if not p.get("com_port"):
            raise spd.SpdError("Selecione uma porta COM antes de continuar.")
        io.open_serial(p["com_port"], baudrate=p.get("baudrate", 115200),
                        wait_s=p["wait_timeout"], cancel_event=cancel_event)


def _chip_text(chip_id, secure_boot):
    info = spd.identify_chip(chip_id)
    txt = info["name"]
    if chip_id is not None:
        txt += "  (CHIP ID = 0x%08x)" % chip_id
    if secure_boot:
        txt += "  [secure boot]"
    return txt, info


# --------------------------------------------------------------------------
# Threads de trabalho: toda a comunicação acontece aqui.
# --------------------------------------------------------------------------

class DumpWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int)          # feito, total
    status = Signal(str)
    chip_detected = Signal(str)
    jedec_detected = Signal(dict)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        io = None
        try:
            p = self.params

            self.status.emit("Aguardando o telefone conectar...")
            self.log.emit(
                "Conecte o telefone segurando a tecla de boot (ou use um "
                "cabo boot com os pinos D+/D- em curto)."
            )
            io = spd.SpdIO(log_cb=lambda m: self.log.emit(m))
            io.verbose = p["verbose"]
            _connect_io(io, p, self.cancel_event)

            self.status.emit("Carregando FDL1...")
            chip_id, secure_boot = io.load_fdl1(
                p["fdl1_path"], p["fdl1_addr"],
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )
            chip_txt, _info = _chip_text(chip_id, secure_boot)
            self.chip_detected.emit(chip_txt)
            self.log.emit("Chipset identificado: %s" % chip_txt)

            if p["keep_charge"]:
                try:
                    io.keep_charge()
                except spd.SpdError as e:
                    self.log.emit(
                        "Aviso: este FDL1 não aceitou o comando 'manter "
                        "carregando' (%s) - continuando sem ele." % e
                    )

            if p["stage2_enabled"]:
                self.status.emit("Carregando segundo estágio (FDL2)...")
                io.load_next_stage(
                    p["stage2_path"], p["stage2_addr"],
                    progress_cb=lambda d, t: self.progress.emit(d, t),
                    cancel_event=self.cancel_event,
                )

            self.status.emit("Lendo memória flash...")
            self.progress.emit(0, 1)
            out_path = p["out_path"]
            size_mode = p.get("size_mode", "manual")

            if size_mode == "jedec":
                self.status.emit("Lendo JEDEC ID para detectar o tamanho...")
                jedec = io.read_jedec_id()
                self.jedec_detected.emit(jedec)
                if not jedec["size_bytes"]:
                    raise spd.SpdError(
                        "JEDEC ID lido (0x%06x), mas não foi possível decodificar "
                        "a capacidade do chip - informe o tamanho manualmente."
                        % jedec["raw"]
                    )
                read_size = jedec["size_bytes"]
                self.log.emit(
                    "Tamanho detectado pelo JEDEC ID: %d bytes (%.1f MB)"
                    % (read_size, read_size / (1024 * 1024))
                )
                self.status.emit("Lendo memória flash...")
                with open(out_path, "wb") as f:
                    nread, _ = io.read_flash(
                        p["region_addr"], p["start_offset"], read_size,
                        out_file=f, step=p["block_size"],
                        progress_cb=lambda d, t: self.progress.emit(d, t),
                        cancel_event=self.cancel_event,
                    )
            elif p["auto_size"]:
                nread = io.dump_flash_auto(
                    p["region_addr"], p["start_offset"], out_path,
                    step=p["block_size"],
                    progress_cb=lambda d, t: self.progress.emit(d, t),
                    cancel_event=self.cancel_event,
                )
            else:
                with open(out_path, "wb") as f:
                    nread, _ = io.read_flash(
                        p["region_addr"], p["start_offset"], p["size"],
                        out_file=f, step=p["block_size"],
                        progress_cb=lambda d, t: self.progress.emit(d, t),
                        cancel_event=self.cancel_event,
                    )

            if p["power_off_after"]:
                try:
                    io.power_off()
                except spd.SpdError as e:
                    self.log.emit("Aviso: não foi possível desligar o telefone: %s" % e)

            self.status.emit("Concluído")
            self.finished_ok.emit(
                "Dump concluído: %d bytes salvos em\n%s" % (nread, out_path)
            )
        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except spd.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa - queremos capturar tudo para não travar a GUI
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))
        finally:
            if io is not None:
                io.close()


class WriteWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)
    chip_detected = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        io = None
        try:
            p = self.params

            self.status.emit("Aguardando o telefone conectar...")
            self.log.emit(
                "Conecte o telefone segurando a tecla de boot (ou use um "
                "cabo boot com os pinos D+/D- em curto)."
            )
            io = spd.SpdIO(log_cb=lambda m: self.log.emit(m))
            io.verbose = p["verbose"]
            _connect_io(io, p, self.cancel_event)

            self.status.emit("Carregando FDL1...")
            chip_id, secure_boot = io.load_fdl1(
                p["fdl1_path"], p["fdl1_addr"],
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )
            chip_txt, info = _chip_text(chip_id, secure_boot)
            self.chip_detected.emit(chip_txt)
            self.log.emit("Chipset identificado: %s" % chip_txt)

            fw_addr = info.get("fw_addr")
            target_addr = p["write_addr"] if p["write_addr"] is not None else fw_addr
            if target_addr is None:
                raise spd.SpdError(
                    "Não foi possível determinar o endereço de gravação "
                    "automaticamente para este chipset - informe manualmente "
                    "o endereço de gravação na aba 'Gravar firmware'."
                )

            file_size = os.path.getsize(p["file_path"])
            write_size = p["file_size"] or (file_size - p["file_offset"])

            if not p["stage2_enabled"]:
                # FDL1 custom de estágio único: valida a janela de flash
                # antes de mandar qualquer coisa, para dar um erro claro em
                # vez do 0x82/0x83 cru do telefone.
                spd.check_custom_fdl_window(target_addr, write_size, fw_addr)

            if p["erase_first"]:
                self.status.emit("Apagando região antes de gravar (pode demorar)...")
                erase_size = p["erase_size"] or write_size
                self.log.emit(
                    "Apagando 0x%x bytes a partir de 0x%08x - apagar flash NOR é "
                    "lento, isso pode levar de dezenas de segundos a alguns "
                    "minutos, sem sinal de progresso (o telefone só responde "
                    "quando termina)..." % (erase_size, target_addr)
                )
                self.progress.emit(0, 0)  # indeterminado
                io.erase_flash(target_addr, erase_size, fw_addr=fw_addr, secure_boot=secure_boot)

            self.status.emit("Gravando firmware...")
            self.progress.emit(0, 1)
            nwritten = io.write_flash_file(
                target_addr, p["file_path"], offset=p["file_offset"], size=p["file_size"] or None,
                step=p["block_size"], fw_addr=fw_addr, secure_boot=secure_boot,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )

            self.status.emit("Concluído")
            self.finished_ok.emit(
                "Gravação concluída: %d bytes enviados para 0x%08x" % (nwritten, target_addr)
            )
        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except spd.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))
        finally:
            if io is not None:
                io.close()


class UtilWorker(QThread):
    """
    Ações rápidas de utilidade: entrar em modo diagnóstico/download (só
    conecta e carrega o FDL1, sem ler/gravar nada), reiniciar o telefone
    (normal reset) ou hard reset (apagar dados de usuário/restaurar
    padrões de fábrica via erase_flash numa região lógica de dados).
    """
    log = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)
    chip_detected = Signal(str)
    jedec_detected = Signal(dict)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        io = None
        try:
            p = self.params
            action = p["action"]

            self.status.emit("Aguardando o telefone conectar...")
            self.log.emit(
                "Conecte o telefone segurando a tecla de boot (ou use um "
                "cabo boot com os pinos D+/D- em curto)."
            )
            io = spd.SpdIO(log_cb=lambda m: self.log.emit(m))
            io.verbose = p["verbose"]
            _connect_io(io, p, self.cancel_event)

            self.status.emit("Carregando FDL1...")
            chip_id, secure_boot = io.load_fdl1(
                p["fdl1_path"], p["fdl1_addr"],
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )
            chip_txt, info = _chip_text(chip_id, secure_boot)
            self.chip_detected.emit(chip_txt)
            self.log.emit("Chipset identificado: %s" % chip_txt)

            if action == "diag":
                self.status.emit("Lendo JEDEC ID da flash...")
                try:
                    jedec = io.read_jedec_id()
                    self.jedec_detected.emit(jedec)
                    size_txt = (
                        "%d bytes (%.1f MB)" % (jedec["size_bytes"], jedec["size_bytes"] / (1024 * 1024))
                        if jedec["size_bytes"] else "desconhecido"
                    )
                    self.log.emit(
                        "JEDEC ID: 0x%06x (fabricante: %s [0x%02x], tipo: 0x%02x, "
                        "capacidade estimada: %s)"
                        % (jedec["raw"], jedec["manufacturer_name"], jedec["manufacturer_id"],
                           jedec["mem_type"], size_txt)
                    )
                except spd.SpdError as e:
                    self.log.emit("JEDEC ID não disponível: %s" % e)

                self.status.emit("Em modo diagnóstico/download (BSL)")
                self.finished_ok.emit(
                    "Telefone conectado e em modo diagnóstico/download (FDL1 "
                    "carregado). Chipset: %s" % chip_txt
                )

            elif action == "reset":
                self.status.emit("Reiniciando o telefone...")
                io.normal_reset()
                self.status.emit("Concluído")
                self.finished_ok.emit("Comando de reinício enviado ao telefone.")

            elif action == "hard_reset":
                fw_addr = info.get("fw_addr")
                erase_addr = p["erase_addr"] if p["erase_addr"] is not None else fw_addr
                if erase_addr is None:
                    raise spd.SpdError(
                        "Não foi possível determinar o endereço automaticamente "
                        "para este chipset - informe manualmente na aba Utilitários."
                    )
                if not p["stage2_enabled"]:
                    spd.check_custom_fdl_window(erase_addr, p["erase_size"], fw_addr)
                self.status.emit("Fazendo hard reset (pode demorar)...")
                self.log.emit(
                    "Apagando 0x%x bytes a partir de 0x%08x - apagar flash NOR é "
                    "lento, isso pode levar de dezenas de segundos a alguns "
                    "minutos, sem sinal de progresso (o telefone só responde "
                    "quando termina)..." % (p["erase_size"], erase_addr)
                )
                self.progress.emit(0, 0)  # indeterminado
                io.erase_flash(erase_addr, p["erase_size"],
                                fw_addr=fw_addr, secure_boot=secure_boot)
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Hard reset concluído (região 0x%08x apagada)." % erase_addr
                )
            else:
                raise spd.SpdError("ação desconhecida: %r" % action)

        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except spd.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))
        finally:
            if io is not None:
                io.close()


class PartitionWorker(QThread):
    """
    Lista ou lê partições por nome (BSL_CMD_READ_PARTITION /
    READ_START/READ_MIDST/READ_END). Só funciona com o FDL2 oficial do
    fabricante carregado como segundo estágio - o FDL1 "custom" deste
    projeto não implementa esses comandos.
    """
    log = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)
    chip_detected = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    partitions_listed = Signal(list)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        io = None
        try:
            p = self.params

            self.status.emit("Aguardando o telefone conectar...")
            self.log.emit(
                "Conecte o telefone segurando a tecla de boot (ou use um "
                "cabo boot com os pinos D+/D- em curto)."
            )
            io = spd.SpdIO(log_cb=lambda m: self.log.emit(m))
            io.verbose = p["verbose"]
            _connect_io(io, p, self.cancel_event)

            self.status.emit("Carregando FDL1...")
            chip_id, secure_boot = io.load_fdl1(
                p["fdl1_path"], p["fdl1_addr"],
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )
            chip_txt, _info = _chip_text(chip_id, secure_boot)
            self.chip_detected.emit(chip_txt)
            self.log.emit("Chipset identificado: %s" % chip_txt)

            if not p["stage2_enabled"]:
                self.log.emit(
                    "Aviso: leitura de partições normalmente exige o FDL2 "
                    "oficial do fabricante (marque 'Carregar um segundo "
                    "estágio' com o FDL2 real). Sem ele, isso provavelmente "
                    "vai falhar com 'comando desconhecido' no FDL1 custom."
                )
            else:
                self.status.emit("Carregando segundo estágio (FDL2)...")
                io.load_next_stage(
                    p["stage2_path"], p["stage2_addr"],
                    progress_cb=lambda d, t: self.progress.emit(d, t),
                    cancel_event=self.cancel_event,
                )

            if p["action"] == "list":
                self.status.emit("Listando partições...")
                entries = io.list_partitions()
                self.partitions_listed.emit(entries)
                lines = "\n".join(
                    "  %s: 0x%x bytes" % (e["name"], e["size_raw"]) for e in entries
                )
                self.log.emit("Partições encontradas (%d):\n%s" % (len(entries), lines))
                self.status.emit("Concluído")
                self.finished_ok.emit("%d partição(ões) listada(s)." % len(entries))

            elif p["action"] == "read":
                self.status.emit("Lendo partição '%s'..." % p["part_name"])
                self.progress.emit(0, 1)
                with open(p["out_path"], "wb") as f:
                    nread, _ = io.read_partition(
                        p["part_name"], p["start_offset"], p["size"],
                        out_file=f, step=p["block_size"],
                        progress_cb=lambda d, t: self.progress.emit(d, t),
                        cancel_event=self.cancel_event,
                    )
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Partição '%s' lida: %d bytes salvos em\n%s"
                    % (p["part_name"], nread, p["out_path"])
                )

            elif p["action"] == "erase":
                self.status.emit("Apagando partição '%s' (pode demorar)..." % p["part_name"])
                self.log.emit(
                    "Apagando a partição '%s' - sem sinal de progresso, o "
                    "telefone só responde quando termina..." % p["part_name"]
                )
                self.progress.emit(0, 0)  # indeterminado
                io.erase_partition(p["part_name"])
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Partição '%s' apagada (definições de fábrica restauradas nela)."
                    % p["part_name"]
                )
            else:
                raise spd.SpdError("ação desconhecida: %r" % p["action"])

        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except spd.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))
        finally:
            if io is not None:
                io.close()


class PortProbeWorker(QThread):
    """Testa cada porta COM disponível com um handshake real até achar
    uma que responda como o dispositivo SPD em modo boot."""
    log = Signal(str)
    status = Signal(str)
    found = Signal(str)      # nome da porta encontrada
    not_found = Signal()

    def __init__(self, baudrate=921600):
        super().__init__()
        self.baudrate = baudrate
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            port = spd.probe_serial_ports(
                baudrate=self.baudrate,
                cancel_event=self.cancel_event,
                log_cb=lambda m: self.log.emit(m),
            )
        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.not_found.emit()
            return
        except spd.SpdError as e:
            self.log.emit("Erro durante a detecção: %s" % e)
            port = None
        if port:
            self.found.emit(port)
        else:
            self.not_found.emit()


class PacWorker(QThread):
    """
    Lê o diretório de um firmware .pac ou extrai uma entrada dele. Não
    precisa do telefone conectado - é só processamento local do arquivo.
    """
    log = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    entries_listed = Signal(dict, list)
    chip_detected = Signal(str)  # não usado (sem telefone envolvido) - mantido por compatibilidade com _wire_worker

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            p = self.params
            if p["action"] == "list":
                self.status.emit("Lendo diretório do .pac...")
                info, entries = spd_pac.read_pac_directory(p["pac_path"])
                self.entries_listed.emit(info, entries)
                self.log.emit(
                    "Firmware: %s (%s) - %d arquivo(s)"
                    % (info["fw_name"], info["fw_version"], len(entries))
                )
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "%d arquivo(s) encontrado(s) em '%s' (%s)"
                    % (len(entries), info["fw_name"], info["fw_version"])
                )
            elif p["action"] == "extract":
                entry = p["entry"]
                self.status.emit("Extraindo '%s'..." % entry.name)
                nwritten = spd_pac.extract_pac_entry(
                    p["pac_path"], entry, p["out_path"],
                    progress_cb=lambda d, t: self.progress.emit(d, t),
                    cancel_event=self.cancel_event,
                )
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Extraído: %d bytes salvos em\n%s" % (nwritten, p["out_path"])
                )
            else:
                raise spd.SpdError("ação desconhecida: %r" % p["action"])
        except spd.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except spd.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))


class MtkWorker(QThread):
    """
    Ações para telefones MediaTek em modo BROM (0e8d:0003): conectar e
    mostrar informações (chip, JEDEC ID, MEID), dump, gravação e
    apagamento de flash via o payload custom (DA).
    """
    log = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)
    chip_detected = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def _connect_and_load_da(self, io, p):
        self.status.emit("Aguardando o telefone conectar...")
        self.log.emit(
            "Conecte o telefone MediaTek em modo BROM (geralmente segurando "
            "volume ou uma tecla específica ao ligar o cabo USB)."
        )
        if p["conn_mode"] == "usb":
            io.open_usb(timeout_s=p["wait_timeout"], cancel_event=self.cancel_event)
        else:
            if not p.get("com_port"):
                raise mtk.SpdError("Selecione uma porta COM antes de continuar.")
            io.open_serial(p["com_port"], baudrate=p.get("baudrate", 115200),
                            wait_s=p["wait_timeout"], cancel_event=self.cancel_event)

        self.status.emit("Conectando (handshake BROM)...")
        info = io.connect()
        chip_txt = info["chip_name"]
        if info["brom_ver"] is not None:
            chip_txt += "  (BROM 0x%02x)" % info["brom_ver"]
        self.chip_detected.emit(chip_txt)
        self.log.emit(
            "Conectado: %s - HW ver 0x%04x, SW ver 0x%04x/0x%04x"
            % (chip_txt, info["hw_ver"], info["sw_ver"], info["sw_ver2"])
        )

        if p.get("da_path"):
            self.status.emit("Carregando o payload/DA...")
            with open(p["da_path"], "rb") as f:
                da_data = f.read()
            io.simple_da(
                da_data, p["da_addr"],
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_event=self.cancel_event,
            )
            self.log.emit("Payload/DA carregado e executado em 0x%08x." % p["da_addr"])
        return info

    def run(self):
        io = None
        try:
            p = self.params
            io = mtk.MtkIO(log_cb=lambda m: self.log.emit(m))
            io.verbose = p["verbose"]
            self._connect_and_load_da(io, p)
            action = p["action"]

            if action == "info":
                try:
                    jedec = io.flash_id()
                    size_txt = (
                        "%.1f MB" % (jedec["size_bytes"] / (1024 * 1024))
                        if jedec["size_bytes"] else "desconhecida"
                    )
                    self.log.emit(
                        "JEDEC ID: 0x%06x (fabricante: %s, capacidade estimada: %s)"
                        % (jedec["raw"], jedec["manufacturer_name"], size_txt)
                    )
                except mtk.SpdError as e:
                    self.log.emit(
                        "JEDEC ID não disponível (%s) - carregue o payload/DA "
                        "custom para ler a flash." % e
                    )
                try:
                    meid = io.get_meid()
                    self.log.emit("MEID: %s" % meid.hex())
                except mtk.SpdError as e:
                    self.log.emit("MEID não disponível: %s" % e)
                self.status.emit("Concluído")
                self.finished_ok.emit("Telefone conectado e identificado.")

            elif action == "dump":
                self.status.emit("Lendo a flash...")
                self.progress.emit(0, 1)
                with open(p["out_path"], "wb") as f:
                    nread, _ = io.read_flash(
                        p["addr"], p["size"], out_file=f, step=p["block_size"],
                        progress_cb=lambda d, t: self.progress.emit(d, t),
                        cancel_event=self.cancel_event,
                    )
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Dump concluído: %d bytes salvos em\n%s" % (nread, p["out_path"])
                )

            elif action == "write":
                if p["erase_first"]:
                    self.status.emit("Apagando região antes de gravar (pode demorar)...")
                    self.log.emit(
                        "Apagando 0x%x bytes a partir de 0x%08x..." % (p["erase_size"], p["addr"])
                    )
                    self.progress.emit(0, 0)
                    io.erase_flash(p["addr"], p["erase_size"], cancel_event=self.cancel_event)
                self.status.emit("Gravando...")
                self.progress.emit(0, 1)
                nwritten = io.write_flash_file(
                    p["addr"], p["file_path"], offset=p["file_offset"], size=p["file_size"] or None,
                    progress_cb=lambda d, t: self.progress.emit(d, t),
                    cancel_event=self.cancel_event,
                )
                self.status.emit("Concluído")
                self.finished_ok.emit(
                    "Gravação concluída: %d bytes enviados para 0x%08x" % (nwritten, p["addr"])
                )

            elif action == "erase":
                self.status.emit("Apagando (pode demorar)...")
                self.log.emit(
                    "Apagando 0x%x bytes a partir de 0x%08x..." % (p["erase_size"], p["addr"])
                )
                self.progress.emit(0, 0)
                io.erase_flash(p["addr"], p["erase_size"], cancel_event=self.cancel_event)
                self.status.emit("Concluído")
                self.finished_ok.emit("Região apagada.")
            else:
                raise mtk.SpdError("ação desconhecida: %r" % action)

        except mtk.SpdCancelled:
            self.status.emit("Cancelado")
            self.failed.emit("Operação cancelada pelo usuário.")
        except mtk.SpdError as e:
            self.status.emit("Erro")
            self.failed.emit(str(e))
        except Exception as e:  # noqa
            self.status.emit("Erro")
            self.failed.emit("Erro inesperado: %s\n\n%s" % (e, traceback.format_exc()))
        finally:
            if io is not None:
                io.close()


# --------------------------------------------------------------------------
# Janela principal
# --------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + " - dump, gravação e utilitários para feature phones Spreadtrum/Unisoc")
        self.setMinimumSize(560, 400)
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.worker = None

        self._build_ui()
        self._load_settings()
        self._refresh_com_ports()
        self._fit_to_screen()

    def _fit_to_screen(self):
        """Redimensiona e centraliza a janela para caber no ecrã disponível
        (descontando barra de tarefas etc.), em vez de um tamanho fixo que
        pode ser maior que o ecrã do usuário."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(900, 700)
            return
        avail = screen.availableGeometry()
        margin = 40
        w = max(560, min(900, avail.width() - margin))
        h = max(400, min(700, avail.height() - margin))
        self.resize(w, h)
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        self.move(max(avail.x(), x), max(avail.y(), y))
        # Ecrãs pequenos (ex.: notebooks 1366x768 com barras/zoom do SO):
        # maximiza para aproveitar melhor o espaço em vez de deixar sobras.
        if avail.width() < 1000 or avail.height() < 750:
            self.showMaximized()

    # -- construção da interface -----------------------------------------

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setCentralWidget(scroll)

        central = QWidget()
        central.setObjectName("rootArea")
        scroll.setWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("MabuieTool_SPD")
        title.setObjectName("brandTitle")
        header.addWidget(title)
        self.status_label = QLabel("Dispositivo: aguardando ação do usuário")
        self.status_label.setObjectName("statusLabel")
        header.addWidget(self.status_label, stretch=1)
        header.addStretch(0)
        self.chip_label = QLabel("Chipset: -")
        self.chip_label.setObjectName("chipLabel")
        header.addWidget(self.chip_label)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_connection_tab(), "Conexão / FDL")
        self.tabs.addTab(self._build_dump_tab(), "Ler / Fazer dump")
        self.tabs.addTab(self._build_write_tab(), "Gravar firmware (flash)")
        self.tabs.addTab(self._build_utils_tab(), "Utilitários")
        self.tabs.addTab(self._build_partitions_tab(), "Partições (FDL2)")
        self.tabs.addTab(self._build_pac_tab(), "Extrair FDL2 (.pac)")
        self.tabs.addTab(self._build_mtk_tab(), "MediaTek (MTK)")
        root.addWidget(self.tabs, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        root.addWidget(self.progress_bar)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Consolas", 9))
        self.log_edit.setMinimumHeight(90)
        self.log_edit.setMaximumHeight(160)
        log_layout.addWidget(self.log_edit)
        root.addWidget(log_group)

    # -- grupo: conexão -----------------------------------------------------


    def _build_connection_tab(self):
        w = QWidget()
        root = QHBoxLayout(w)
        root.addWidget(self._build_connection_group(), stretch=1)
        root.addWidget(self._build_fdl_group(), stretch=1)
        return w

    def _build_connection_group(self):
        group = QGroupBox("Conexão com o telefone")
        form = _form_layout(group)

        self.conn_mode_combo = QComboBox()
        self.conn_mode_combo.addItem("USB (libusb / driver WinUSB via Zadig)", "usb")
        self.conn_mode_combo.addItem("Porta COM (serial - usa o driver já instalado, sem Zadig)", "serial")
        self.conn_mode_combo.currentIndexChanged.connect(self._toggle_conn_mode)
        form.addRow("Modo de conexão:", self.conn_mode_combo)

        com_row = QHBoxLayout()
        self.com_port_combo = QComboBox()
        self.com_port_combo.setEditable(True)
        btn_refresh = QPushButton("Atualizar lista")
        btn_refresh.clicked.connect(self._refresh_com_ports)
        btn_auto = QPushButton("Detectar automaticamente")
        btn_auto.clicked.connect(self._start_port_probe)
        self.port_probe_btn = btn_auto
        com_row.addWidget(self.com_port_combo, stretch=1)
        com_row.addWidget(btn_refresh)
        com_row.addWidget(btn_auto)
        self.com_port_row = _wrap(com_row)
        form.addRow("Porta COM:", self.com_port_row)

        self.baudrate_combo = QComboBox()
        self.baudrate_combo.setEditable(True)
        self.baudrate_combo.addItems(["921600", "460800", "230400", "115200", "57600", "9600"])
        form.addRow("Baud rate:", self.baudrate_combo)

        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(5, 3600)
        self.wait_spin.setValue(60)
        form.addRow("Tempo de espera do dispositivo (s):", self.wait_spin)

        self.verbose_combo = QComboBox()
        self.verbose_combo.addItems(["0 - normal", "1 - detalhado", "2 - completo (bytes crus)"])
        form.addRow("Verbosidade do log:", self.verbose_combo)

        note = QLabel(
            "Dica: se o telefone já aparece como uma porta COM no Gerenciador de "
            "Dispositivos (driver do fabricante já instalado), use o modo 'Porta "
            "COM' - não é preciso trocar o driver com o Zadig. \"Detectar "
            "automaticamente\" testa cada porta disponível com um handshake "
            "real (não só adivinha pelo driver) - conecte o telefone em modo "
            "boot antes de clicar."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b90a8; font-size: 9pt;")
        form.addRow(note)

        self._toggle_conn_mode(0)
        return group

    def _toggle_conn_mode(self, _index):
        is_serial = self.conn_mode_combo.currentData() == "serial"
        self.com_port_row.setEnabled(is_serial)
        self.baudrate_combo.setEnabled(is_serial)

    def _refresh_com_ports(self):
        current = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        ports = spd.list_serial_ports()
        if not ports:
            self.com_port_combo.addItem("")
        for p in ports:
            label = p["device"]
            if p["description"]:
                label += "  -  " + p["description"]
            self.com_port_combo.addItem(label, p["device"])
        guess = spd.guess_serial_port()
        if guess:
            for i in range(self.com_port_combo.count()):
                if self.com_port_combo.itemData(i) == guess:
                    self.com_port_combo.setCurrentIndex(i)
                    break
        elif current:
            self.com_port_combo.setCurrentText(current)

    def _selected_com_port(self):
        data = self.com_port_combo.currentData()
        if data:
            return data
        text = self.com_port_combo.currentText().strip()
        return text.split()[0] if text else ""

    def _start_port_probe(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "Aguarde", "Uma operação já está em andamento.")
            return
        baud = 921600
        try:
            baud = parse_int(self.baudrate_combo.currentText(), "Baud rate")
        except ValueError:
            pass
        self.port_probe_btn.setEnabled(False)
        self.status_label.setText("Dispositivo: detectando porta COM automaticamente...")
        self._append_log(
            "Testando portas COM disponíveis (conecte o telefone em modo "
            "boot agora, se ainda não conectou)..."
        )
        self.worker = PortProbeWorker(baudrate=baud)
        self.worker.log.connect(self._append_log)
        self.worker.found.connect(self._on_port_found)
        self.worker.not_found.connect(self._on_port_not_found)
        self.worker.start()

    def _on_port_found(self, port):
        self.port_probe_btn.setEnabled(True)
        self.status_label.setText("Dispositivo: porta detectada")
        self._append_log("Telefone encontrado em %s" % port)
        self._refresh_com_ports()
        found_idx = -1
        for i in range(self.com_port_combo.count()):
            if self.com_port_combo.itemData(i) == port:
                found_idx = i
                break
        if found_idx >= 0:
            self.com_port_combo.setCurrentIndex(found_idx)
        else:
            self.com_port_combo.setCurrentText(port)
        idx = self.conn_mode_combo.findData("serial")
        if idx >= 0:
            self.conn_mode_combo.setCurrentIndex(idx)
        QMessageBox.information(self, "Porta encontrada", "Telefone detectado em %s" % port)

    def _on_port_not_found(self):
        self.port_probe_btn.setEnabled(True)
        self.status_label.setText("Dispositivo: nenhuma porta respondeu")
        self._append_log("Nenhuma porta COM respondeu como dispositivo SPD.")
        QMessageBox.warning(
            self, "Não encontrado",
            "Nenhuma porta COM respondeu como o telefone. Confira se ele "
            "está conectado e em modo boot, ou tente o modo USB.",
        )

    # -- grupo: FDL (compartilhado entre leitura e gravação) ---------------

    def _build_fdl_group(self):
        group = QGroupBox("Estágio de inicialização (FDL)")
        form = _form_layout(group)

        self.fdl1_path_edit = QLineEdit()
        btn_fdl1 = QPushButton("Procurar...")
        btn_fdl1.clicked.connect(lambda: self._browse_file(self.fdl1_path_edit, "Selecione o nor_fdl1.bin"))
        row = QHBoxLayout()
        row.addWidget(self.fdl1_path_edit)
        row.addWidget(btn_fdl1)
        form.addRow("Arquivo FDL1 (nor_fdl1.bin):", _wrap(row))

        self.fdl1_addr_edit = QLineEdit("0x40004000")
        form.addRow("Endereço de carga do FDL1:", self.fdl1_addr_edit)

        self.stage2_check = QCheckBox("Carregar um segundo estágio (FDL2) - smartphones / 4G T117")
        self.stage2_check.toggled.connect(self._toggle_stage2)
        form.addRow(self.stage2_check)

        self.stage2_path_edit = QLineEdit()
        btn_fdl2 = QPushButton("Procurar...")
        btn_fdl2.clicked.connect(lambda: self._browse_file(self.stage2_path_edit, "Selecione o FDL2"))
        row2 = QHBoxLayout()
        row2.addWidget(self.stage2_path_edit)
        row2.addWidget(btn_fdl2)
        self.stage2_path_row = _wrap(row2)
        form.addRow("Arquivo FDL2:", self.stage2_path_row)

        self.stage2_addr_edit = QLineEdit("0x14000000")
        form.addRow("Endereço de carga do FDL2:", self.stage2_addr_edit)

        btn_chips = QPushButton("Ver chipsets configurados (chips.json)")
        btn_chips.clicked.connect(self._show_chip_db)
        form.addRow(btn_chips)

        self._toggle_stage2(False)
        return group

    def _show_chip_db(self):
        lines = []
        for e in spd.CHIP_DB:
            fw = "0x%08x" % e["fw_addr"] if e["fw_addr"] is not None else "-"
            fdl1 = "0x%08x" % e["fdl1_addr"] if e["fdl1_addr"] is not None else "-"
            lines.append(
                "%s\n  fw_addr=%s   fdl1_addr=%s\n  %s"
                % (e["name"], fw, fdl1, e.get("notes", ""))
            )
        QMessageBox.information(
            self, "Chipsets configurados",
            ("%d chipset(s) em chips.json:\n\n" % len(spd.CHIP_DB)) + "\n\n".join(lines),
        )

    def _toggle_stage2(self, checked):
        self.stage2_path_edit.setEnabled(checked)
        self.stage2_addr_edit.setEnabled(checked)

    # -- aba: dump (leitura) -------------------------------------------------

    def _build_dump_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        dump_group = QGroupBox("Leitura da memória flash")
        dump_form = _form_layout(dump_group)

        self.region_combo = QComboBox()
        for name, addr in spd.KNOWN_REGIONS:
            self.region_combo.addItem("%s  (0x%08x)" % (name, addr), addr)
        self.region_combo.addItem("Personalizado...", None)
        self.region_combo.currentIndexChanged.connect(self._toggle_custom_region)
        dump_form.addRow("Região:", self.region_combo)

        self.custom_region_edit = QLineEdit("0x80000003")
        self.custom_region_edit.setEnabled(False)
        dump_form.addRow("ID/endereço personalizado:", self.custom_region_edit)

        self.start_offset_edit = QLineEdit("0x0")
        dump_form.addRow("Deslocamento inicial:", self.start_offset_edit)

        self.size_mode_combo = QComboBox()
        self.size_mode_combo.addItem("Manual", "manual")
        self.size_mode_combo.addItem("Automático (cabeçalho DHTB/VNTS - 4G T117)", "dhtb")
        self.size_mode_combo.addItem("Automático (JEDEC ID - chip inteiro, requer FDL1 com patch)", "jedec")
        self.size_mode_combo.currentIndexChanged.connect(self._toggle_size_mode)
        dump_form.addRow("Tamanho a ler:", self.size_mode_combo)

        self.size_edit = QLineEdit("0x400000")
        dump_form.addRow("Tamanho (modo manual):", self.size_edit)

        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(64, 65024)
        self.block_size_spin.setSingleStep(64)
        self.block_size_spin.setValue(4000)
        dump_form.addRow("Tamanho do bloco (step):", self.block_size_spin)

        speed_note = QLabel(
            "Dica de velocidade: bloco maior = menos idas-e-voltas (mais "
            "rápido), até ~4000 bytes com o FDL1 custom. No modo Porta COM, "
            "tente também um baud rate mais alto (ex.: 921600) na seção "
            "Conexão - a leitura via serial costuma ser bem mais lenta que "
            "via USB."
        )
        speed_note.setWordWrap(True)
        speed_note.setStyleSheet("color: #8b90a8; font-size: 9pt;")
        dump_form.addRow(speed_note)

        out_row = QHBoxLayout()
        self.out_path_edit = QLineEdit(os.path.join(os.getcwd(), "flash.bin"))
        btn_out = QPushButton("Salvar como...")
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_path_edit)
        out_row.addWidget(btn_out)
        dump_form.addRow("Salvar dump em:", _wrap(out_row))

        root.addWidget(dump_group)

        opt_group = QGroupBox("Opções")
        opt_row = QHBoxLayout(opt_group)
        self.keep_charge_check = QCheckBox("Manter carregando durante a operação (nem todo FDL1 aceita)")
        self.keep_charge_check.setChecked(False)
        self.power_off_check = QCheckBox("Desligar o telefone ao terminar")
        opt_row.addWidget(self.keep_charge_check)
        opt_row.addWidget(self.power_off_check)
        opt_row.addStretch(1)
        root.addWidget(opt_group)

        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Aguardar telefone e iniciar dump")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self._start_dump)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)
        return w

    def _toggle_custom_region(self, _index):
        custom = self.region_combo.currentData() is None
        self.custom_region_edit.setEnabled(custom)

    def _toggle_size_mode(self, _index):
        self.size_edit.setEnabled(self.size_mode_combo.currentData() == "manual")

    # -- aba: gravação (flash) -----------------------------------------------

    def _build_write_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        warn = QLabel(
            "\u26a0\ufe0f Gravar firmware pode INUTILIZAR o telefone permanentemente se o "
            "arquivo, o endereço ou o chipset estiverem errados. Só grave um "
            "dump feito no MESMO aparelho/modelo (ou um firmware oficial "
            "compatível). Não desconecte o cabo nem desligue o PC durante a "
            "gravação."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #ffb4b4; font-weight: bold; padding: 8px; "
                            "background-color: #2a1418; "
                            "border: 1px solid #a3313c; border-radius: 6px;")
        root.addWidget(warn)

        write_group = QGroupBox("Arquivo a gravar")
        form = _form_layout(write_group)

        file_row = QHBoxLayout()
        self.write_file_edit = QLineEdit()
        btn_file = QPushButton("Procurar...")
        btn_file.clicked.connect(lambda: self._browse_file(self.write_file_edit, "Selecione o arquivo a gravar"))
        file_row.addWidget(self.write_file_edit)
        file_row.addWidget(btn_file)
        form.addRow("Arquivo (.bin):", _wrap(file_row))

        self.write_file_offset_edit = QLineEdit("0x0")
        form.addRow("Deslocamento dentro do arquivo:", self.write_file_offset_edit)

        self.write_file_size_edit = QLineEdit("")
        self.write_file_size_edit.setPlaceholderText("vazio = arquivo inteiro")
        form.addRow("Tamanho a gravar:", self.write_file_size_edit)

        self.write_addr_edit = QLineEdit("")
        self.write_addr_edit.setPlaceholderText("vazio = detectar automaticamente pelo chipset (fw_addr)")
        form.addRow("Endereço de gravação:", self.write_addr_edit)

        self.write_block_size_spin = QSpinBox()
        self.write_block_size_spin.setRange(64, 65024)
        self.write_block_size_spin.setSingleStep(64)
        self.write_block_size_spin.setValue(4000)
        form.addRow("Tamanho do bloco (step):", self.write_block_size_spin)

        root.addWidget(write_group)

        erase_group = QGroupBox("Apagar antes de gravar (opcional)")
        erase_form = _form_layout(erase_group)
        self.erase_first_check = QCheckBox("Apagar a região antes de gravar (BSL_CMD_ERASE_FLASH)")
        erase_form.addRow(self.erase_first_check)
        self.erase_size_edit = QLineEdit("")
        self.erase_size_edit.setPlaceholderText("vazio = mesmo tamanho do que será gravado")
        erase_form.addRow("Tamanho a apagar:", self.erase_size_edit)
        root.addWidget(erase_group)

        confirm_group = QGroupBox()
        confirm_layout = QVBoxLayout(confirm_group)
        self.confirm_write_check = QCheckBox(
            "Entendo os riscos e quero gravar firmware neste telefone."
        )
        self.confirm_write_check.toggled.connect(self._toggle_confirm_write)
        confirm_layout.addWidget(self.confirm_write_check)
        root.addWidget(confirm_group)

        action_row = QHBoxLayout()
        self.write_start_btn = QPushButton("Aguardar telefone e gravar firmware")
        self.write_start_btn.setObjectName("dangerButton")
        self.write_start_btn.setEnabled(False)
        self.write_start_btn.clicked.connect(self._start_write)
        self.write_cancel_btn = QPushButton("Cancelar")
        self.write_cancel_btn.setEnabled(False)
        self.write_cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.write_start_btn)
        action_row.addWidget(self.write_cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)
        return w

    def _toggle_confirm_write(self, checked):
        self.write_start_btn.setEnabled(checked)

    # -- aba: utilitários (diag / reset / hard reset) ------------------------

    def _build_utils_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        diag_group = QGroupBox("Modo diagnóstico / download (BSL)")
        diag_layout = QVBoxLayout(diag_group)
        diag_note = QLabel(
            "Conecta ao telefone e carrega o FDL1, deixando-o pronto no modo "
            "de download/diagnóstico (BSL) - identifica o chipset sem ler ou "
            "gravar nada na flash. Útil para testar a conexão/driver/FDL1 "
            "antes de um dump ou gravação."
        )
        diag_note.setWordWrap(True)
        diag_layout.addWidget(diag_note)
        self.diag_start_btn = QPushButton("Aguardar telefone e entrar em modo diagnóstico")
        self.diag_start_btn.setObjectName("primaryButton")
        self.diag_start_btn.clicked.connect(self._start_diag)
        diag_layout.addWidget(self.diag_start_btn)
        root.addWidget(diag_group)

        reset_group = QGroupBox("Reiniciar telefone")
        reset_layout = QVBoxLayout(reset_group)
        reset_note = QLabel(
            "Conecta, carrega o FDL1 e envia o comando de reinício normal "
            "(BSL_CMD_NORMAL_RESET) - equivalente a religar o telefone."
        )
        reset_note.setWordWrap(True)
        reset_layout.addWidget(reset_note)
        self.reset_start_btn = QPushButton("Aguardar telefone e reiniciar")
        self.reset_start_btn.setObjectName("primaryButton")
        self.reset_start_btn.clicked.connect(self._start_reset)
        reset_layout.addWidget(self.reset_start_btn)
        root.addWidget(reset_group)

        hard_group = QGroupBox("Restaurar definições de fábrica (Hard reset - apagar dados de usuário)")
        hard_form = _form_layout(hard_group)

        hard_warn = QLabel(
            "\u26a0\ufe0f Esta é a função de restaurar definições de fábrica: apaga "
            "configurações, contatos, mensagens e outros dados salvos no "
            "telefone, sem precisar de nenhum arquivo. "
            "A opção 'automático' apaga dentro da faixa de flash real do "
            "FDL1 custom (endereço do chipset detectado) - confirmado no "
            "código-fonte do custom_fdl. As opções ERASE_UDISK/UDISK_IMG só "
            "funcionam com o FDL2 oficial do fabricante (segundo estágio), "
            "não com o FDL1 custom sozinho. Recomendamos fazer um dump de "
            "backup antes (aba 'Ler / Fazer dump').\n\n"
            "Se você tiver o FDL2 oficial carregado, a aba \"Partições (FDL2)\" "
            "tem uma versão mais precisa desta mesma função - apaga a "
            "partição pelo nome (ex.: 'userdata') em vez de um intervalo de "
            "endereços estimado."
        )
        hard_warn.setWordWrap(True)
        hard_warn.setStyleSheet("color: #ffb4b4; font-weight: bold; padding: 8px; "
                                 "background-color: #2a1418; "
                                 "border: 1px solid #a3313c; border-radius: 6px;")
        hard_form.addRow(hard_warn)

        self.hard_reset_region_combo = QComboBox()
        self.hard_reset_region_combo.addItem(
            "Automático (dentro da flash real do FDL1 custom, pelo chipset detectado)", "auto")
        self.hard_reset_region_combo.addItem(
            "ERASE_UDISK (0x90000005) - só com FDL2 oficial do fabricante", 0x90000005)
        self.hard_reset_region_combo.addItem(
            "UDISK_IMG (0x90000006) - só com FDL2 oficial do fabricante", 0x90000006)
        self.hard_reset_region_combo.addItem("Personalizado...", None)
        self.hard_reset_region_combo.currentIndexChanged.connect(self._toggle_hard_reset_custom)
        hard_form.addRow("Região a apagar:", self.hard_reset_region_combo)

        self.hard_reset_custom_addr_edit = QLineEdit("0x90000005")
        self.hard_reset_custom_addr_edit.setEnabled(False)
        hard_form.addRow("Endereço/ID personalizado:", self.hard_reset_custom_addr_edit)

        self.hard_reset_size_edit = QLineEdit("0x100000")
        hard_form.addRow("Tamanho a apagar:", self.hard_reset_size_edit)

        self.confirm_hard_reset_check = QCheckBox(
            "Entendo que isso apaga os dados de usuário e quero continuar."
        )
        self.confirm_hard_reset_check.toggled.connect(self._toggle_confirm_hard_reset)
        hard_form.addRow(self.confirm_hard_reset_check)

        self.hard_reset_start_btn = QPushButton("Aguardar telefone e fazer hard reset")
        self.hard_reset_start_btn.setObjectName("dangerButton")
        self.hard_reset_start_btn.setEnabled(False)
        self.hard_reset_start_btn.clicked.connect(self._start_hard_reset)
        hard_form.addRow(self.hard_reset_start_btn)

        root.addWidget(hard_group)

        action_row = QHBoxLayout()
        self.util_cancel_btn = QPushButton("Cancelar")
        self.util_cancel_btn.setEnabled(False)
        self.util_cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.util_cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)
        return w

    def _toggle_hard_reset_custom(self, _index):
        custom = self.hard_reset_region_combo.currentData() is None
        self.hard_reset_custom_addr_edit.setEnabled(custom)

    def _toggle_confirm_hard_reset(self, checked):
        self.hard_reset_start_btn.setEnabled(checked)

    def _start_diag(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        params["action"] = "diag"
        self._save_settings()
        self._begin_operation()
        self.worker = UtilWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _start_reset(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        params["action"] = "reset"
        self._save_settings()
        self._begin_operation()
        self.worker = UtilWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _start_hard_reset(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        erase_addr_data = self.hard_reset_region_combo.currentData()
        try:
            if erase_addr_data == "auto":
                erase_addr = None  # resolvido no worker a partir do chipset detectado
            elif erase_addr_data is None:
                erase_addr = parse_int(self.hard_reset_custom_addr_edit.text(), "Endereço/ID personalizado")
            else:
                erase_addr = erase_addr_data
            erase_size = parse_int(self.hard_reset_size_edit.text(), "Tamanho a apagar")
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        params["action"] = "hard_reset"
        params["erase_addr"] = erase_addr
        params["erase_size"] = erase_size

        addr_desc = ("0x%08x" % erase_addr) if erase_addr is not None else "(automático pelo chipset detectado)"
        resp = QMessageBox.warning(
            self, "Confirmar hard reset",
            "Isso vai APAGAR os dados de usuário do telefone "
            "(região %s, 0x%x bytes).\n\nDeseja continuar?" % (addr_desc, erase_size),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self._save_settings()
        self._begin_operation()
        self.worker = UtilWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    # -- aba: partições (FDL2 oficial) ---------------------------------------

    def _build_partitions_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        warn = QLabel(
            "\u2139\ufe0f Esta aba só funciona com o FDL2 oficial do fabricante "
            "carregado como segundo estágio (marque 'Carregar um segundo "
            "estágio (FDL2)' na seção FDL, acima, com o arquivo real). O "
            "FDL1 custom deste projeto não implementa leitura de partição "
            "por nome - só a leitura por região/endereço já disponível na "
            "aba 'Ler / Fazer dump'."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #cdd1e0; padding: 8px; "
                            "background-color: #1a2230; "
                            "border: 1px solid #2b3a55; border-radius: 6px;")
        root.addWidget(warn)

        list_group = QGroupBox("Listar partições")
        list_layout = QVBoxLayout(list_group)
        self.partition_list_btn = QPushButton("Aguardar telefone e listar partições")
        self.partition_list_btn.setObjectName("primaryButton")
        self.partition_list_btn.clicked.connect(self._start_partition_list)
        list_layout.addWidget(self.partition_list_btn)
        self.partition_list_view = QPlainTextEdit()
        self.partition_list_view.setReadOnly(True)
        self.partition_list_view.setFont(QFont("Consolas", 9))
        self.partition_list_view.setMaximumHeight(120)
        self.partition_list_view.setPlaceholderText(
            "As partições listadas aparecem aqui (nome: tamanho em bytes)."
        )
        list_layout.addWidget(self.partition_list_view)
        root.addWidget(list_group)

        read_group = QGroupBox("Ler uma partição")
        read_form = _form_layout(read_group)

        self.partition_name_combo = QComboBox()
        self.partition_name_combo.setEditable(True)
        self.partition_name_combo.setPlaceholderText("ex.: boot, recovery, userdata...")
        read_form.addRow("Nome da partição:", self.partition_name_combo)

        self.partition_start_edit = QLineEdit("0x0")
        read_form.addRow("Deslocamento inicial:", self.partition_start_edit)

        self.partition_size_edit = QLineEdit("")
        self.partition_size_edit.setPlaceholderText(
            "tamanho em bytes - use 'Listar partições' para preencher automaticamente"
        )
        read_form.addRow("Tamanho a ler:", self.partition_size_edit)

        self.partition_block_size_spin = QSpinBox()
        self.partition_block_size_spin.setRange(64, 65024)
        self.partition_block_size_spin.setSingleStep(64)
        self.partition_block_size_spin.setValue(4096)
        read_form.addRow("Tamanho do bloco (step):", self.partition_block_size_spin)

        out_row = QHBoxLayout()
        self.partition_out_path_edit = QLineEdit(os.path.join(os.getcwd(), "partition.bin"))
        btn_out = QPushButton("Salvar como...")
        btn_out.clicked.connect(lambda: self._browse_save(self.partition_out_path_edit))
        out_row.addWidget(self.partition_out_path_edit)
        out_row.addWidget(btn_out)
        read_form.addRow("Salvar em:", _wrap(out_row))

        self.partition_read_btn = QPushButton("Aguardar telefone e ler partição")
        self.partition_read_btn.setObjectName("primaryButton")
        self.partition_read_btn.clicked.connect(self._start_partition_read)
        read_form.addRow(self.partition_read_btn)

        root.addWidget(read_group)

        erase_group = QGroupBox("Restaurar definições de fábrica (apagar partição por nome)")
        erase_form = _form_layout(erase_group)

        erase_note = QLabel(
            "Mais preciso que o \"Hard reset\" da aba Utilitários: apaga "
            "exatamente a partição escolhida pelo nome (o FDL2 sabe o "
            "tamanho certo sozinho, pela própria tabela de partições) - em "
            "vez de um intervalo de endereços estimado. Sugestões comuns: "
            "userdata, cache, metadata, misc (varia por aparelho - use "
            "\"Listar partições\" acima para ver os nomes reais deste "
            "telefone)."
        )
        erase_note.setWordWrap(True)
        erase_note.setStyleSheet("color: #cdd1e0; font-size: 9pt;")
        erase_form.addRow(erase_note)

        self.partition_erase_combo = QComboBox()
        self.partition_erase_combo.setEditable(True)
        self.partition_erase_combo.addItems(["userdata", "cache", "metadata", "misc"])
        self.partition_erase_combo.setCurrentText("")
        self.partition_erase_combo.setPlaceholderText("nome da partição a apagar")
        erase_form.addRow("Partição a apagar:", self.partition_erase_combo)

        self.confirm_partition_erase_check = QCheckBox(
            "Entendo que isso apaga essa partição (dados de usuário/configurações) e quero continuar."
        )
        self.confirm_partition_erase_check.toggled.connect(
            lambda checked: self.partition_erase_btn.setEnabled(checked)
        )
        erase_form.addRow(self.confirm_partition_erase_check)

        self.partition_erase_btn = QPushButton("Aguardar telefone e restaurar definições de fábrica")
        self.partition_erase_btn.setObjectName("dangerButton")
        self.partition_erase_btn.setEnabled(False)
        self.partition_erase_btn.clicked.connect(self._start_partition_erase)
        erase_form.addRow(self.partition_erase_btn)

        root.addWidget(erase_group)

        action_row = QHBoxLayout()
        self.partition_cancel_btn = QPushButton("Cancelar")
        self.partition_cancel_btn.setEnabled(False)
        self.partition_cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.partition_cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)
        return w

    def _on_partitions_listed(self, entries):
        self.partition_list_view.setPlainText(
            "\n".join("%s: 0x%x bytes" % (e["name"], e["size_raw"]) for e in entries)
        )
        current = self.partition_name_combo.currentText()
        self.partition_name_combo.clear()
        self._partition_sizes = {e["name"]: e["size_raw"] for e in entries}
        for e in entries:
            self.partition_name_combo.addItem(e["name"])
        if current:
            self.partition_name_combo.setCurrentText(current)
        elif entries:
            self.partition_name_combo.setCurrentIndex(0)
            self.partition_size_edit.setText("0x%x" % entries[0]["size_raw"])

    def _start_partition_list(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        params["action"] = "list"

        self._save_settings()
        self._begin_operation()
        self.worker = PartitionWorker(params)
        self._wire_worker(self.worker)
        self.worker.partitions_listed.connect(self._on_partitions_listed)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _start_partition_read(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        part_name = self.partition_name_combo.currentText().strip()
        if not part_name:
            QMessageBox.warning(self, "Parâmetros inválidos", "Informe o nome da partição.")
            return
        try:
            start = parse_int(self.partition_start_edit.text(), "Deslocamento inicial")
            size = parse_int(self.partition_size_edit.text(), "Tamanho a ler")
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        out_path = self.partition_out_path_edit.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Parâmetros inválidos", "Informe onde salvar o arquivo.")
            return

        params.update({
            "action": "read",
            "part_name": part_name,
            "start_offset": start,
            "size": size,
            "block_size": self.partition_block_size_spin.value(),
            "out_path": out_path,
        })

        if os.path.exists(out_path):
            resp = QMessageBox.question(
                self, "Sobrescrever arquivo?",
                "O arquivo de saída já existe:\n%s\n\nDeseja sobrescrever?" % out_path,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self._save_settings()
        self._begin_operation()
        self.worker = PartitionWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _start_partition_erase(self):
        try:
            params = self._collect_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        part_name = self.partition_erase_combo.currentText().strip()
        if not part_name:
            QMessageBox.warning(self, "Parâmetros inválidos", "Informe o nome da partição a apagar.")
            return

        resp = QMessageBox.warning(
            self, "Confirmar restauração de fábrica",
            "Isso vai APAGAR a partição '%s' (dados de usuário/"
            "configurações). O telefone volta às definições de fábrica "
            "nela.\n\nSó funciona com o FDL2 oficial carregado como "
            "segundo estágio - com o FDL1 custom sozinho isso vai falhar.\n\n"
            "Deseja continuar?" % part_name,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        params.update({"action": "erase", "part_name": part_name})

        self._save_settings()
        self._begin_operation()
        self.worker = PartitionWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    # -- aba: extrair de firmware .pac ---------------------------------------

    def _build_pac_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        info_label = QLabel(
            "Extrai arquivos (incluindo FDL1/FDL2 oficiais) de um pacote de "
            "firmware .pac da Spreadtrum/Unisoc. Não precisa do telefone "
            "conectado - é só leitura do arquivo no seu PC. Entradas do tipo "
            "\"FDL\" (marcadas abaixo) já trazem o endereço de carga certo "
            "embutido no próprio .pac.\n\n"
            "Nota: isto só funciona com arquivos .pac (que têm essa estrutura "
            "de diretório interna) - um dump bruto (.bin) da flash não tem "
            "FDL1/FDL2 dentro para extrair. Para restaurar um dump, use-o "
            "diretamente na aba \"Gravar firmware (flash)\" (não precisa de "
            "FDL2 para isso - só o FDL1 já basta)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #cdd1e0; padding: 8px; "
                                  "background-color: #1a2230; "
                                  "border: 1px solid #2b3a55; border-radius: 6px;")
        root.addWidget(info_label)

        file_group = QGroupBox("Arquivo .pac")
        file_form = _form_layout(file_group)

        file_row = QHBoxLayout()
        self.pac_path_edit = QLineEdit()
        btn_pac = QPushButton("Procurar...")
        btn_pac.clicked.connect(self._browse_pac_file)
        file_row.addWidget(self.pac_path_edit)
        file_row.addWidget(btn_pac)
        file_form.addRow("Firmware (.pac):", _wrap(file_row))

        self.pac_list_btn = QPushButton("Listar arquivos do .pac")
        self.pac_list_btn.setObjectName("primaryButton")
        self.pac_list_btn.clicked.connect(self._start_pac_list)
        file_form.addRow(self.pac_list_btn)

        self.pac_info_label = QLabel("Nenhum .pac lido ainda.")
        self.pac_info_label.setWordWrap(True)
        file_form.addRow(self.pac_info_label)

        root.addWidget(file_group)

        entry_group = QGroupBox("Arquivo dentro do .pac")
        entry_form = _form_layout(entry_group)

        self.pac_entry_combo = QComboBox()
        self.pac_entry_combo.currentIndexChanged.connect(self._on_pac_entry_selected)
        entry_form.addRow("Arquivo:", self.pac_entry_combo)

        self.pac_entry_detail_label = QLabel("-")
        self.pac_entry_detail_label.setWordWrap(True)
        entry_form.addRow("Detalhes:", self.pac_entry_detail_label)

        out_row = QHBoxLayout()
        self.pac_out_path_edit = QLineEdit()
        btn_pac_out = QPushButton("Salvar como...")
        btn_pac_out.clicked.connect(lambda: self._browse_save(self.pac_out_path_edit, "Extrair arquivo do .pac como"))
        out_row.addWidget(self.pac_out_path_edit)
        out_row.addWidget(btn_pac_out)
        entry_form.addRow("Extrair para:", _wrap(out_row))

        self.pac_extract_btn = QPushButton("Extrair arquivo selecionado")
        self.pac_extract_btn.setObjectName("primaryButton")
        self.pac_extract_btn.clicked.connect(self._start_pac_extract)
        entry_form.addRow(self.pac_extract_btn)

        convenience_row = QHBoxLayout()
        self.pac_use_fdl1_btn = QPushButton("Extrair e usar como FDL1")
        self.pac_use_fdl1_btn.clicked.connect(lambda: self._pac_extract_and_use("fdl1"))
        self.pac_use_fdl2_btn = QPushButton("Extrair e usar como FDL2")
        self.pac_use_fdl2_btn.clicked.connect(lambda: self._pac_extract_and_use("fdl2"))
        convenience_row.addWidget(self.pac_use_fdl1_btn)
        convenience_row.addWidget(self.pac_use_fdl2_btn)
        entry_form.addRow(_wrap(convenience_row))

        root.addWidget(entry_group)

        action_row = QHBoxLayout()
        self.pac_cancel_btn = QPushButton("Cancelar")
        self.pac_cancel_btn.setEnabled(False)
        self.pac_cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.pac_cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)

        self._pac_entries = []
        return w

    def _browse_pac_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecione o firmware .pac", self.pac_path_edit.text(),
            "Firmware Spreadtrum (*.pac);;Todos os arquivos (*)",
        )
        if path:
            self.pac_path_edit.setText(path)

    def _on_pac_entry_selected(self, index):
        if index < 0 or index >= len(self._pac_entries):
            self.pac_entry_detail_label.setText("-")
            return
        e = self._pac_entries[index]
        addr_txt = ("0x%08x" % e.load_addr) if e.load_addr else "não informado no .pac"
        self.pac_entry_detail_label.setText(
            "tipo = %s, tamanho = 0x%x bytes, endereço de carga = %s"
            % ("FDL" if e.is_fdl else "0x%x" % e.type, e.size, addr_txt)
        )
        suggested = os.path.join(os.getcwd(), "fdl_files", e.name)
        self.pac_out_path_edit.setText(suggested)

    def _start_pac_list(self):
        pac_path = self.pac_path_edit.text().strip()
        if not pac_path or not os.path.isfile(pac_path):
            QMessageBox.warning(self, "Parâmetros inválidos", "Selecione um arquivo .pac válido.")
            return

        self._begin_operation()
        self.worker = PacWorker({"action": "list", "pac_path": pac_path})
        self._wire_worker(self.worker)
        self.worker.entries_listed.connect(self._on_pac_entries_listed)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _on_pac_entries_listed(self, info, entries):
        self._pac_entries = entries
        self.pac_info_label.setText(
            "Firmware: %s   Versão: %s   (%d arquivos)"
            % (info["fw_name"], info["fw_version"], len(entries))
        )
        self.pac_entry_combo.clear()
        for e in entries:
            tag = "[FDL] " if e.is_fdl else ""
            addr_txt = (" addr=0x%08x" % e.load_addr) if e.load_addr else ""
            self.pac_entry_combo.addItem(
                "%s%s (0x%x bytes%s)" % (tag, e.name, e.size, addr_txt)
            )
        if entries:
            self.pac_entry_combo.setCurrentIndex(0)

    def _current_pac_entry(self):
        idx = self.pac_entry_combo.currentIndex()
        if idx < 0 or idx >= len(self._pac_entries):
            return None
        return self._pac_entries[idx]

    def _start_pac_extract(self):
        pac_path = self.pac_path_edit.text().strip()
        entry = self._current_pac_entry()
        out_path = self.pac_out_path_edit.text().strip()
        if not pac_path or entry is None:
            QMessageBox.warning(self, "Parâmetros inválidos", "Liste o .pac e escolha um arquivo primeiro.")
            return
        if not out_path:
            QMessageBox.warning(self, "Parâmetros inválidos", "Informe onde salvar o arquivo extraído.")
            return
        self._extract_pac_entry_to(pac_path, entry, out_path, on_done=None)

    def _pac_extract_and_use(self, target):
        """target: 'fdl1' ou 'fdl2' - extrai a entrada selecionada e já
        preenche os campos de FDL correspondentes (caminho + endereço)."""
        pac_path = self.pac_path_edit.text().strip()
        entry = self._current_pac_entry()
        if not pac_path or entry is None:
            QMessageBox.warning(self, "Parâmetros inválidos", "Liste o .pac e escolha um arquivo primeiro.")
            return
        out_path = self.pac_out_path_edit.text().strip() or os.path.join(
            os.getcwd(), "fdl_files", entry.name)

        def on_done():
            if target == "fdl1":
                self.fdl1_path_edit.setText(out_path)
                if entry.load_addr:
                    self.fdl1_addr_edit.setText("0x%08x" % entry.load_addr)
                self._append_log("FDL1 definido a partir do .pac: %s" % out_path)
            else:
                self.stage2_path_edit.setText(out_path)
                if entry.load_addr:
                    self.stage2_addr_edit.setText("0x%08x" % entry.load_addr)
                self.stage2_check.setChecked(True)
                self._append_log("FDL2 definido a partir do .pac: %s" % out_path)

        self._extract_pac_entry_to(pac_path, entry, out_path, on_done=on_done)

    def _extract_pac_entry_to(self, pac_path, entry, out_path, on_done):
        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.warning(self, "Erro", "Não foi possível criar a pasta de destino: %s" % e)
                return

        if os.path.exists(out_path):
            resp = QMessageBox.question(
                self, "Sobrescrever arquivo?",
                "O arquivo já existe:\n%s\n\nDeseja sobrescrever?" % out_path,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self._begin_operation()
        self.worker = PacWorker({
            "action": "extract", "pac_path": pac_path,
            "entry": entry, "out_path": out_path,
        })
        self._wire_worker(self.worker)

        def finished(msg):
            self._end_operation(ok=True, msg=msg)
            if on_done:
                on_done()

        self.worker.finished_ok.connect(finished)
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    # -- aba: MediaTek (MTK) --------------------------------------------------

    def _build_mtk_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)

        intro = QLabel(
            "Suporte para telefones MediaTek (MT6260/MT6261 - feature phones) "
            "em modo BROM. Protocolo separado do Spreadtrum acima - conexão "
            "própria, USB 0e8d:0003."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #cdd1e0; padding: 6px;")
        root.addWidget(intro)

        conn_group = QGroupBox("Conexão MediaTek")
        conn_form = _form_layout(conn_group)

        self.mtk_conn_mode_combo = QComboBox()
        self.mtk_conn_mode_combo.addItem("USB (libusb)", "usb")
        self.mtk_conn_mode_combo.addItem("Porta COM (serial)", "serial")
        self.mtk_conn_mode_combo.currentIndexChanged.connect(self._toggle_mtk_conn_mode)
        conn_form.addRow("Modo de conexão:", self.mtk_conn_mode_combo)

        mtk_com_row = QHBoxLayout()
        self.mtk_com_port_combo = QComboBox()
        self.mtk_com_port_combo.setEditable(True)
        btn_mtk_refresh = QPushButton("Atualizar lista")
        btn_mtk_refresh.clicked.connect(self._refresh_mtk_com_ports)
        mtk_com_row.addWidget(self.mtk_com_port_combo, stretch=1)
        mtk_com_row.addWidget(btn_mtk_refresh)
        self.mtk_com_port_row = _wrap(mtk_com_row)
        conn_form.addRow("Porta COM:", self.mtk_com_port_row)

        self.mtk_baudrate_combo = QComboBox()
        self.mtk_baudrate_combo.setEditable(True)
        self.mtk_baudrate_combo.addItems(["115200", "921600", "460800", "230400", "57600"])
        conn_form.addRow("Baud rate:", self.mtk_baudrate_combo)

        self.mtk_wait_spin = QSpinBox()
        self.mtk_wait_spin.setRange(5, 3600)
        self.mtk_wait_spin.setValue(60)
        conn_form.addRow("Tempo de espera do dispositivo (s):", self.mtk_wait_spin)

        self.mtk_verbose_combo = QComboBox()
        self.mtk_verbose_combo.addItems(["0 - normal", "1 - detalhado", "2 - completo (bytes crus)"])
        conn_form.addRow("Verbosidade do log:", self.mtk_verbose_combo)

        self._toggle_mtk_conn_mode(0)
        root.addWidget(conn_group)

        da_group = QGroupBox("Payload / DA (necessário para ler/gravar/apagar a flash)")
        da_form = _form_layout(da_group)

        da_note = QLabel(
            "Equivalente ao FDL do Spreadtrum: um código pequeno que roda na "
            "RAM do telefone e implementa os comandos de flash. Vem do "
            "projeto original (pasta payload/, precisa compilar com o "
            "Android NDK - veja payload/README.md). Sem ele, só dá pra "
            "conectar e ver informações básicas do BROM (não dá pra ler "
            "JEDEC ID nem mexer na flash)."
        )
        da_note.setWordWrap(True)
        da_note.setStyleSheet("color: #8b90a8; font-size: 9pt;")
        da_form.addRow(da_note)

        da_row = QHBoxLayout()
        self.mtk_da_path_edit = QLineEdit()
        btn_da = QPushButton("Procurar...")
        btn_da.clicked.connect(lambda: self._browse_file(self.mtk_da_path_edit, "Selecione o payload/DA"))
        da_row.addWidget(self.mtk_da_path_edit)
        da_row.addWidget(btn_da)
        da_form.addRow("Arquivo do payload:", _wrap(da_row))

        self.mtk_da_addr_edit = QLineEdit("0x70008000")
        da_form.addRow("Endereço de carga:", self.mtk_da_addr_edit)

        root.addWidget(da_group)

        info_group = QGroupBox("Informações")
        info_layout = QVBoxLayout(info_group)
        self.mtk_info_btn = QPushButton("Aguardar telefone e conectar")
        self.mtk_info_btn.setObjectName("primaryButton")
        self.mtk_info_btn.clicked.connect(self._start_mtk_info)
        info_layout.addWidget(self.mtk_info_btn)
        root.addWidget(info_group)

        dump_group = QGroupBox("Ler flash (dump)")
        dump_form = _form_layout(dump_group)
        self.mtk_dump_addr_edit = QLineEdit("0x0")
        dump_form.addRow("Endereço inicial:", self.mtk_dump_addr_edit)
        self.mtk_dump_size_edit = QLineEdit("0x400000")
        dump_form.addRow("Tamanho a ler:", self.mtk_dump_size_edit)
        self.mtk_dump_block_spin = QSpinBox()
        self.mtk_dump_block_spin.setRange(64, 65024)
        self.mtk_dump_block_spin.setSingleStep(64)
        self.mtk_dump_block_spin.setValue(1024)
        dump_form.addRow("Tamanho do bloco (step):", self.mtk_dump_block_spin)
        mtk_out_row = QHBoxLayout()
        self.mtk_dump_out_edit = QLineEdit(os.path.join(os.getcwd(), "mtk_flash.bin"))
        btn_mtk_out = QPushButton("Salvar como...")
        btn_mtk_out.clicked.connect(lambda: self._browse_save(self.mtk_dump_out_edit, "Salvar dump MTK como"))
        mtk_out_row.addWidget(self.mtk_dump_out_edit)
        mtk_out_row.addWidget(btn_mtk_out)
        dump_form.addRow("Salvar em:", _wrap(mtk_out_row))
        self.mtk_dump_btn = QPushButton("Aguardar telefone e fazer dump")
        self.mtk_dump_btn.setObjectName("primaryButton")
        self.mtk_dump_btn.clicked.connect(self._start_mtk_dump)
        dump_form.addRow(self.mtk_dump_btn)
        root.addWidget(dump_group)

        write_group = QGroupBox("Gravar flash")
        write_form = _form_layout(write_group)
        write_warn = QLabel(
            "\u26a0\ufe0f Gravar firmware errado pode inutilizar o telefone. Só grave "
            "um arquivo compatível com este aparelho."
        )
        write_warn.setWordWrap(True)
        write_warn.setStyleSheet("color: #ffb4b4; font-weight: bold; padding: 6px; "
                                  "background-color: #2a1418; "
                                  "border: 1px solid #a3313c; border-radius: 6px;")
        write_form.addRow(write_warn)
        mtk_wfile_row = QHBoxLayout()
        self.mtk_write_file_edit = QLineEdit()
        btn_mtk_wfile = QPushButton("Procurar...")
        btn_mtk_wfile.clicked.connect(lambda: self._browse_file(self.mtk_write_file_edit, "Selecione o arquivo a gravar"))
        mtk_wfile_row.addWidget(self.mtk_write_file_edit)
        mtk_wfile_row.addWidget(btn_mtk_wfile)
        write_form.addRow("Arquivo (.bin):", _wrap(mtk_wfile_row))
        self.mtk_write_offset_edit = QLineEdit("0x0")
        write_form.addRow("Deslocamento no arquivo:", self.mtk_write_offset_edit)
        self.mtk_write_size_edit = QLineEdit("")
        self.mtk_write_size_edit.setPlaceholderText("vazio = arquivo inteiro")
        write_form.addRow("Tamanho a gravar:", self.mtk_write_size_edit)
        self.mtk_write_addr_edit = QLineEdit("0x0")
        write_form.addRow("Endereço de gravação:", self.mtk_write_addr_edit)
        self.mtk_write_erase_check = QCheckBox("Apagar a região antes de gravar")
        write_form.addRow(self.mtk_write_erase_check)
        self.mtk_write_erase_size_edit = QLineEdit("")
        self.mtk_write_erase_size_edit.setPlaceholderText("vazio = mesmo tamanho a gravar")
        write_form.addRow("Tamanho a apagar:", self.mtk_write_erase_size_edit)
        self.mtk_confirm_write_check = QCheckBox("Entendo os riscos e quero gravar firmware neste telefone.")
        self.mtk_confirm_write_check.toggled.connect(lambda c: self.mtk_write_btn.setEnabled(c))
        write_form.addRow(self.mtk_confirm_write_check)
        self.mtk_write_btn = QPushButton("Aguardar telefone e gravar")
        self.mtk_write_btn.setObjectName("dangerButton")
        self.mtk_write_btn.setEnabled(False)
        self.mtk_write_btn.clicked.connect(self._start_mtk_write)
        write_form.addRow(self.mtk_write_btn)
        root.addWidget(write_group)

        erase_group = QGroupBox("Apagar flash")
        erase_form = _form_layout(erase_group)
        self.mtk_erase_addr_edit = QLineEdit("0x0")
        erase_form.addRow("Endereço inicial:", self.mtk_erase_addr_edit)
        self.mtk_erase_size_edit = QLineEdit("0x1000")
        erase_form.addRow("Tamanho a apagar:", self.mtk_erase_size_edit)
        self.mtk_confirm_erase_check = QCheckBox("Entendo que isso apaga dados da flash e quero continuar.")
        self.mtk_confirm_erase_check.toggled.connect(lambda c: self.mtk_erase_btn.setEnabled(c))
        erase_form.addRow(self.mtk_confirm_erase_check)
        self.mtk_erase_btn = QPushButton("Aguardar telefone e apagar")
        self.mtk_erase_btn.setObjectName("dangerButton")
        self.mtk_erase_btn.setEnabled(False)
        self.mtk_erase_btn.clicked.connect(self._start_mtk_erase)
        erase_form.addRow(self.mtk_erase_btn)
        root.addWidget(erase_group)

        action_row = QHBoxLayout()
        self.mtk_cancel_btn = QPushButton("Cancelar")
        self.mtk_cancel_btn.setEnabled(False)
        self.mtk_cancel_btn.clicked.connect(self._cancel_current)
        action_row.addWidget(self.mtk_cancel_btn)
        root.addLayout(action_row)
        root.addStretch(1)
        return w

    def _toggle_mtk_conn_mode(self, _index):
        is_serial = self.mtk_conn_mode_combo.currentData() == "serial"
        self.mtk_com_port_row.setEnabled(is_serial)
        self.mtk_baudrate_combo.setEnabled(is_serial)

    def _refresh_mtk_com_ports(self):
        current = self.mtk_com_port_combo.currentText()
        self.mtk_com_port_combo.clear()
        for p in spd.list_serial_ports():
            label = p["device"]
            if p["description"]:
                label += "  -  " + p["description"]
            self.mtk_com_port_combo.addItem(label, p["device"])
        if current:
            self.mtk_com_port_combo.setCurrentText(current)

    def _selected_mtk_com_port(self):
        data = self.mtk_com_port_combo.currentData()
        if data:
            return data
        text = self.mtk_com_port_combo.currentText().strip()
        return text.split()[0] if text else ""

    def _collect_mtk_common_params(self):
        conn_mode = self.mtk_conn_mode_combo.currentData()
        params = {
            "conn_mode": conn_mode,
            "com_port": self._selected_mtk_com_port() if conn_mode == "serial" else "",
            "baudrate": parse_int(self.mtk_baudrate_combo.currentText(), "Baud rate") if conn_mode == "serial" else 115200,
            "wait_timeout": self.mtk_wait_spin.value(),
            "verbose": self.mtk_verbose_combo.currentIndex(),
            "da_path": self.mtk_da_path_edit.text().strip(),
            "da_addr": parse_int(self.mtk_da_addr_edit.text(), "Endereço do payload"),
        }
        if conn_mode == "serial" and not params["com_port"]:
            raise ValueError("Selecione (ou digite) uma porta COM.")
        if params["da_path"] and not os.path.isfile(params["da_path"]):
            raise ValueError("O arquivo do payload/DA informado não existe.")
        return params

    def _begin_mtk_operation(self):
        self._begin_operation()
        self.mtk_info_btn.setEnabled(False)
        self.mtk_dump_btn.setEnabled(False)
        self.mtk_write_btn.setEnabled(False)
        self.mtk_erase_btn.setEnabled(False)
        self.mtk_cancel_btn.setEnabled(True)

    def _end_mtk_operation(self, ok, msg):
        self._end_operation(ok, msg)
        self.mtk_info_btn.setEnabled(True)
        self.mtk_dump_btn.setEnabled(True)
        self.mtk_write_btn.setEnabled(self.mtk_confirm_write_check.isChecked())
        self.mtk_erase_btn.setEnabled(self.mtk_confirm_erase_check.isChecked())
        self.mtk_cancel_btn.setEnabled(False)

    def _start_mtk_info(self):
        try:
            params = self._collect_mtk_common_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        params["action"] = "info"
        self._begin_mtk_operation()
        self.worker = MtkWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_mtk_operation(True, msg))
        self.worker.failed.connect(lambda msg: self._end_mtk_operation(False, msg))
        self.worker.start()

    def _start_mtk_dump(self):
        try:
            params = self._collect_mtk_common_params()
            params.update({
                "action": "dump",
                "addr": parse_int(self.mtk_dump_addr_edit.text(), "Endereço inicial"),
                "size": parse_int(self.mtk_dump_size_edit.text(), "Tamanho"),
                "block_size": self.mtk_dump_block_spin.value(),
                "out_path": self.mtk_dump_out_edit.text().strip(),
            })
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return
        if not params["out_path"]:
            QMessageBox.warning(self, "Parâmetros inválidos", "Informe onde salvar o dump.")
            return
        if os.path.exists(params["out_path"]):
            resp = QMessageBox.question(
                self, "Sobrescrever arquivo?",
                "O arquivo já existe:\n%s\n\nDeseja sobrescrever?" % params["out_path"],
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self._begin_mtk_operation()
        self.worker = MtkWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_mtk_operation(True, msg))
        self.worker.failed.connect(lambda msg: self._end_mtk_operation(False, msg))
        self.worker.start()

    def _start_mtk_write(self):
        try:
            params = self._collect_mtk_common_params()
            file_path = self.mtk_write_file_edit.text().strip()
            if not file_path or not os.path.isfile(file_path):
                raise ValueError("Selecione um arquivo válido para gravar.")
            params.update({
                "action": "write",
                "file_path": file_path,
                "file_offset": parse_int(self.mtk_write_offset_edit.text(), "Deslocamento no arquivo"),
                "file_size": parse_int_opt(self.mtk_write_size_edit.text(), "Tamanho a gravar"),
                "addr": parse_int(self.mtk_write_addr_edit.text(), "Endereço de gravação"),
                "erase_first": self.mtk_write_erase_check.isChecked(),
                "erase_size": parse_int_opt(self.mtk_write_erase_size_edit.text(), "Tamanho a apagar"),
            })
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        resp = QMessageBox.warning(
            self, "Confirmar gravação",
            "Você está prestes a GRAVAR firmware no telefone MediaTek.\n\n"
            "Arquivo: %s\nEndereço: 0x%08x\n\nDeseja continuar?"
            % (params["file_path"], params["addr"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self._begin_mtk_operation()
        self.worker = MtkWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_mtk_operation(True, msg))
        self.worker.failed.connect(lambda msg: self._end_mtk_operation(False, msg))
        self.worker.start()

    def _start_mtk_erase(self):
        try:
            params = self._collect_mtk_common_params()
            params.update({
                "action": "erase",
                "addr": parse_int(self.mtk_erase_addr_edit.text(), "Endereço inicial"),
                "erase_size": parse_int(self.mtk_erase_size_edit.text(), "Tamanho a apagar"),
            })
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        resp = QMessageBox.warning(
            self, "Confirmar apagamento",
            "Isso vai APAGAR 0x%x bytes a partir de 0x%08x no telefone "
            "MediaTek.\n\nDeseja continuar?" % (params["erase_size"], params["addr"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self._begin_mtk_operation()
        self.worker = MtkWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_mtk_operation(True, msg))
        self.worker.failed.connect(lambda msg: self._end_mtk_operation(False, msg))
        self.worker.start()

    # -- diálogos de arquivo ------------------------------------------------

    def _browse_file(self, line_edit, title):
        path, _ = QFileDialog.getOpenFileName(self, title, line_edit.text(), "Arquivos BIN (*.bin);;Todos os arquivos (*)")
        if path:
            line_edit.setText(path)

    def _browse_save(self, line_edit, title="Salvar como"):
        path, _ = QFileDialog.getSaveFileName(self, title, line_edit.text(), "Arquivos BIN (*.bin);;Todos os arquivos (*)")
        if path:
            line_edit.setText(path)

    def _browse_output(self):
        self._browse_save(self.out_path_edit, "Salvar dump como")

    # -- log / progresso -----------------------------------------------------

    def _append_log(self, msg):
        self.log_edit.moveCursor(QTextCursor.End)
        self.log_edit.appendPlainText(msg)

    def _set_progress(self, done, total):
        if total <= 0:
            self.progress_bar.setRange(0, 0)  # indeterminado
            return
        self.progress_bar.setRange(0, 100)
        pct = int(done * 100 / total)
        self.progress_bar.setValue(min(pct, 100))

    def _set_progress_phase(self, phase_text):
        """Mostra a fase atual dentro da própria barra (%p%% - fase), já que a
        barra reinicia em cada fase (carregar FDL1, carregar FDL2, ler flash)
        - sem isso, parece que ela 'voltou para trás' sem motivo."""
        self.progress_bar.setFormat("%p%% - " + phase_text)

    # -- parâmetros comuns (conexão + FDL) -----------------------------------

    def _collect_common_params(self):
        fdl1_path = self.fdl1_path_edit.text().strip()
        if not fdl1_path or not os.path.isfile(fdl1_path):
            raise ValueError("Selecione um arquivo FDL1 válido (nor_fdl1.bin).")

        conn_mode = self.conn_mode_combo.currentData()
        params = {
            "conn_mode": conn_mode,
            "com_port": self._selected_com_port() if conn_mode == "serial" else "",
            "baudrate": parse_int(self.baudrate_combo.currentText(), "Baud rate") if conn_mode == "serial" else 115200,
            "wait_timeout": self.wait_spin.value(),
            "verbose": self.verbose_combo.currentIndex(),
            "fdl1_path": fdl1_path,
            "fdl1_addr": parse_int(self.fdl1_addr_edit.text(), "Endereço do FDL1"),
            "stage2_enabled": self.stage2_check.isChecked(),
            "stage2_path": self.stage2_path_edit.text().strip(),
            "stage2_addr": parse_int(self.stage2_addr_edit.text(), "Endereço do FDL2") if self.stage2_check.isChecked() else 0,
        }
        if conn_mode == "serial" and not params["com_port"]:
            raise ValueError("Selecione (ou digite) uma porta COM.")
        if params["stage2_enabled"] and (not params["stage2_path"] or not os.path.isfile(params["stage2_path"])):
            raise ValueError("Selecione um arquivo FDL2 válido ou desmarque a opção de segundo estágio.")
        return params

    # -- controle: dump -------------------------------------------------------

    def _collect_dump_params(self):
        params = self._collect_common_params()

        region_addr = self.region_combo.currentData()
        if region_addr is None:
            region_addr = parse_int(self.custom_region_edit.text(), "ID/endereço da região")

        out_path = self.out_path_edit.text().strip()
        if not out_path:
            raise ValueError("Informe onde salvar o arquivo de dump.")

        size_mode = self.size_mode_combo.currentData()
        params.update({
            "region_addr": region_addr,
            "start_offset": parse_int(self.start_offset_edit.text(), "Deslocamento inicial"),
            "size_mode": size_mode,
            "auto_size": size_mode == "dhtb",  # compatibilidade com dump_flash_auto (DHTB/VNTS)
            "size": parse_int(self.size_edit.text(), "Tamanho") if size_mode == "manual" else 0,
            "block_size": self.block_size_spin.value(),
            "out_path": out_path,
            "keep_charge": self.keep_charge_check.isChecked(),
            "power_off_after": self.power_off_check.isChecked(),
        })
        return params

    def _start_dump(self):
        try:
            params = self._collect_dump_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        if os.path.exists(params["out_path"]):
            resp = QMessageBox.question(
                self, "Sobrescrever arquivo?",
                "O arquivo de saída já existe:\n%s\n\nDeseja sobrescrever?" % params["out_path"],
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self._save_settings()
        self._begin_operation()

        self.worker = DumpWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.finished_ok.connect(lambda msg, p=params: self._offer_dump_as_write_source(p["out_path"]))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    def _offer_dump_as_write_source(self, out_path):
        """Depois de um dump bem-sucedido, já deixa esse arquivo pronto na
        aba de gravação - útil para restaurar o mesmo dump depois (ex.:
        num aparelho idêntico que precisou ser reflashado)."""
        self.write_file_edit.setText(out_path)
        self._append_log(
            "Arquivo pronto na aba 'Gravar firmware' para restaurar este "
            "dump depois, se precisar: %s" % out_path
        )

    # -- controle: gravação ----------------------------------------------------

    def _collect_write_params(self):
        params = self._collect_common_params()

        file_path = self.write_file_edit.text().strip()
        if not file_path or not os.path.isfile(file_path):
            raise ValueError("Selecione um arquivo válido para gravar.")

        params.update({
            "file_path": file_path,
            "file_offset": parse_int(self.write_file_offset_edit.text(), "Deslocamento no arquivo"),
            "file_size": parse_int_opt(self.write_file_size_edit.text(), "Tamanho a gravar"),
            "write_addr": parse_int_opt(self.write_addr_edit.text(), "Endereço de gravação"),
            "block_size": self.write_block_size_spin.value(),
            "erase_first": self.erase_first_check.isChecked(),
            "erase_size": parse_int_opt(self.erase_size_edit.text(), "Tamanho a apagar"),
        })
        return params

    def _start_write(self):
        try:
            params = self._collect_write_params()
        except ValueError as e:
            QMessageBox.warning(self, "Parâmetros inválidos", str(e))
            return

        resp = QMessageBox.warning(
            self, "Confirmar gravação",
            "Você está prestes a GRAVAR firmware no telefone.\n\n"
            "Arquivo: %s\n"
            "Endereço: %s\n\n"
            "Isso pode inutilizar o aparelho se algo estiver errado. "
            "Deseja continuar?" % (
                params["file_path"],
                ("0x%08x" % params["write_addr"]) if params["write_addr"] is not None else "(automático pelo chipset)",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self._save_settings()
        self._begin_operation()

        self.worker = WriteWorker(params)
        self._wire_worker(self.worker)
        self.worker.finished_ok.connect(lambda msg: self._end_operation(ok=True, msg=msg))
        self.worker.failed.connect(lambda msg: self._end_operation(ok=False, msg=msg))
        self.worker.start()

    # -- gerenciamento comum de operação em andamento ------------------------

    def _wire_worker(self, worker):
        worker.log.connect(self._append_log)
        worker.progress.connect(self._set_progress)
        worker.status.connect(lambda s: self.status_label.setText("Dispositivo: " + s))
        worker.status.connect(self._set_progress_phase)
        worker.chip_detected.connect(lambda s: self.chip_label.setText("Chipset: " + s))

    def _begin_operation(self):
        self.log_edit.clear()
        self.chip_label.setText("Chipset: -")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%%")
        self.start_btn.setEnabled(False)
        self.write_start_btn.setEnabled(False)
        self.diag_start_btn.setEnabled(False)
        self.reset_start_btn.setEnabled(False)
        self.hard_reset_start_btn.setEnabled(False)
        self.partition_list_btn.setEnabled(False)
        self.partition_read_btn.setEnabled(False)
        self.partition_erase_btn.setEnabled(False)
        self.pac_list_btn.setEnabled(False)
        self.pac_extract_btn.setEnabled(False)
        self.pac_use_fdl1_btn.setEnabled(False)
        self.pac_use_fdl2_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.write_cancel_btn.setEnabled(True)
        self.util_cancel_btn.setEnabled(True)
        self.partition_cancel_btn.setEnabled(True)
        self.pac_cancel_btn.setEnabled(True)

    def _end_operation(self, ok, msg):
        self._append_log(("" if ok else "ERRO: ") + msg)
        if ok:
            QMessageBox.information(self, "Concluído", msg)
        else:
            QMessageBox.critical(self, "Falha na operação", msg)
        self.start_btn.setEnabled(True)
        self.write_start_btn.setEnabled(self.confirm_write_check.isChecked())
        self.diag_start_btn.setEnabled(True)
        self.reset_start_btn.setEnabled(True)
        self.hard_reset_start_btn.setEnabled(self.confirm_hard_reset_check.isChecked())
        self.partition_list_btn.setEnabled(True)
        self.partition_read_btn.setEnabled(True)
        self.partition_erase_btn.setEnabled(self.confirm_partition_erase_check.isChecked())
        self.pac_list_btn.setEnabled(True)
        self.pac_extract_btn.setEnabled(True)
        self.pac_use_fdl1_btn.setEnabled(True)
        self.pac_use_fdl2_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.write_cancel_btn.setEnabled(False)
        self.util_cancel_btn.setEnabled(False)
        self.partition_cancel_btn.setEnabled(False)
        self.pac_cancel_btn.setEnabled(False)

    def _cancel_current(self):
        if self.worker is not None:
            self.worker.cancel()
            self._append_log("Cancelamento solicitado, aguardando a operação atual terminar...")
            self.cancel_btn.setEnabled(False)
            self.write_cancel_btn.setEnabled(False)
            self.util_cancel_btn.setEnabled(False)
            self.partition_cancel_btn.setEnabled(False)
            self.pac_cancel_btn.setEnabled(False)

    # -- persistência de configurações -----------------------------------

    def _load_settings(self):
        s = self.settings
        default_fdl1 = ""
        guess_path = os.path.join(os.getcwd(), "fdl_files", "nor_fdl1.bin")
        if os.path.isfile(guess_path):
            default_fdl1 = guess_path
        self.fdl1_path_edit.setText(s.value("fdl1_path", default_fdl1))
        self.fdl1_addr_edit.setText(s.value("fdl1_addr", "0x40004000"))
        self.out_path_edit.setText(s.value("out_path", self.out_path_edit.text()))
        mode = s.value("conn_mode", "usb")
        idx = self.conn_mode_combo.findData(mode)
        if idx >= 0:
            self.conn_mode_combo.setCurrentIndex(idx)

    def _save_settings(self):
        s = self.settings
        s.setValue("fdl1_path", self.fdl1_path_edit.text())
        s.setValue("fdl1_addr", self.fdl1_addr_edit.text())
        s.setValue("out_path", self.out_path_edit.text())
        s.setValue("conn_mode", self.conn_mode_combo.currentData())

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            resp = QMessageBox.question(
                self, "Operação em andamento",
                "Uma operação ainda está em andamento. Deseja cancelar e sair?",
            )
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(3000)
        self._save_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(_STYLE_SHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
