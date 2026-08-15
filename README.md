# MabuiETool

**Professional Mobile Device Service Tool**

MabuiETool is a professional PySide6 desktop application that wraps and preserves the existing MediaTek and Spreadtrum/Unisoc functionality in this repository while introducing a new product identity, modular architecture, dashboard, device detection layer, backend adapters, diagnostics, backup manifests, and a modern service-tool interface.

> The legacy `mtkclient` Python package remains in the source tree for compatibility with existing MTK functionality and imports. MabuiETool provides the new user-facing identity and adapters around that code instead of deleting working functionality.

## Features

- Professional MabuiETool GUI with fixed sidebar, top device bar, dynamic workspace, bottom log console, and status bar.
- Dashboard for device status, USB/COM status, platform, chipset, boot mode, security, battery, Android version, and protocol.
- Modular `DeviceManager` independent from GUI widgets.
- Backend adapters for MediaTek, Unisoc/SPD, Qualcomm EDL detection, and Android ADB/Fastboot diagnostics.
- Capability model used by backends to describe supported operations.
- Central branding in `mabuietool/core/branding.py`.
- Central dark/light theme support through `ThemeManager`.
- Professional categorized logger: INFO, SUCCESS, WARNING, ERROR, DEBUG, USB, PROTOCOL, DEVICE.
- FRP diagnostics module for authorized diagnostics only; unauthorized bypass/removal is not implemented.
- Backup manager with SHA256 and JSON manifest support.
- PyInstaller-oriented Windows build script.

## Architecture

```text
mabuietool/
├── core/          # branding, config, logging, errors, capabilities
├── device/        # DeviceInfo model and DeviceManager
├── backends/      # MediaTek, Unisoc/SPD, Qualcomm and Android adapters
├── frp/           # FRP diagnostics manager
├── backup/        # backup manifest and hash manager
├── gui/           # PySide6 main window, sidebar, dashboard, console, themes and pages
└── resources/     # MabuiETool vector icon/resources
```

The GUI talks to `DeviceManager`; `DeviceManager` talks to backend adapters; adapters use USB, serial, ADB/Fastboot, or preserved legacy modules. This avoids putting USB/serial logic directly inside widgets.

## Installation

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Python 3.11, 3.12 and 3.13 are supported targets. PySide6 is used for the GUI.

## Running

Development mode:

```bash
python -m mabuietool
python -m mabuietool --help
```

Installed entry points:

```bash
mabuietool
mabuietool-gui
```

The Unisoc/SPD interface is unified inside the MabuiETool **Unisoc / SPD** page, including a **Full SPD Tool** tab that embeds the existing SPD workflow without launching a separate application. The legacy MTK interface remains available for compatibility:

```bash
python mtk_gui.py
```

## Supported Platforms and Protocols

- MediaTek: BootROM / Preloader detection and preserved legacy MTK workflows.
- Unisoc / Spreadtrum: BSL / FDL / PAC workflow via the bundled SPD modules embedded in the MabuiETool workspace.
- Qualcomm: EDL detection and diagnostics foundation.
- Android: ADB and Fastboot tool detection for diagnostics.
- USB and COM monitoring through PyUSB and pyserial.

## Building on Windows

Use the provided script:

```bat
build_windows.bat
```

The script first creates a `--onedir` build named `MabuiETool`. After validating resources and runtime behavior, it can be extended to produce a `--onefile` executable.

## Troubleshooting

- If USB detection is unavailable, install the correct USB driver and ensure the process has permission to access USB devices.
- If COM detection is unavailable, verify the pyserial installation and device driver.
- If ADB/Fastboot status is unavailable, install Android platform tools and add them to `PATH`.
- The application opens safely without a connected phone and shows `Device: Disconnected`.

## Development

Run the test suite:

```bash
python -m pytest
```

Run import/launch checks:

```bash
python -m py_compile mabuietool/app.py mabuietool/gui/main_window.py
python -m mabuietool --help
```

## License and Credits

MabuiETool preserves and adapts legacy components from the existing GPLv3 codebase. See `LICENSE` for license details. Legacy references to `mtkclient` may remain in package names, imports, code compatibility paths, license notices, and technical documentation where required to preserve working functionality.
