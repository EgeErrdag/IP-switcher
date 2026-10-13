# IP Switcher Pro

A Windows desktop app to quickly switch between static IP configurations and DHCP mode on network adapters.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Adapter selection** — Dropdown lists all active network adapters with MAC identification
- **Static IP configuration** — Set IP, subnet mask, gateway, and DNS in one click
- **DHCP mode** — Revert any adapter to automatic configuration instantly
- **Saved profiles** — Store and load frequently used IP configurations
- **Auto-refresh** — Network status updates every 5 seconds
- **Admin auto-elevation** — Automatically requests administrator privileges via UAC
- **Dark UI** — Modern dark theme built with CustomTkinter

## Preview

```
╔══════════════════╦═══════════════════════════════════════════════════╗
║  IP Switcher     ║  Dashboard                          ● Ethernet  ║
║  Network Manager ║                                                  ║
║──────────────────║  ┌── Current IP ────┐  ┌── MAC Address ────────┐ ║
║  PROFILES     2  ║  │                  │  │                       │ ║
║                  ║  │  *.*.*.* 　　     │  │  **-**-**-**-**-**    │ ║
║  ┌────────────┐  ║  │                  │  │                       │ ║
║  │ Office     │  ║  └──────────────────┘  └───────────────────────┘ ║
║  │ *.*.*.*    │  ║                                                  ║
║  │  [Load] [x]│  ║  Configuration                                  ║
║  └────────────┘  ║  ─────────────────────────────────────────────── ║
║  ┌────────────┐  ║  Adapter     [ Ethernet 7  [**-**-**-**-**] ▼ ] ║
║  │ Home       │  ║  IP Address  [___].[___].[___].[___]             ║
║  │ *.*.*.*    │  ║  Subnet      [___].[___].[___].[___]            ║
║  │  [Load] [x]│  ║  Gateway     [___].[___].[___].[___]            ║
║  └────────────┘  ║  DNS Server  [___].[___].[___].[___]           ║
║                  ║                                                  ║
║                  ║  [ Apply Settings ]  [ DHCP Mode ]               ║
║ [+ Save Config]  ║                                                  ║
╚══════════════════╩═══════════════════════════════════════════════════╝
```

> *IP and MAC addresses are masked. Actual values are shown in the running application.*

## Requirements

- Windows 10/11
- Python 3.10+
- Administrator privileges (for `netsh` commands)

## Installation

```bash
git clone https://github.com/EgeErrdag/ip-switcher-pro.git
cd ip-switcher-pro
pip install -r requirements.txt
```

## Usage

**Option 1** — Double-click `run.bat`

**Option 2** — Run from terminal:
```bash
python main.py
```

The app will automatically request admin privileges if needed.

## How It Works

- Uses `psutil` to detect active network adapters and their addresses
- Applies network changes via Windows `netsh` commands
- Profiles are saved locally to `saved_ips.json` (excluded from git)

## Website

A Turkish, animated landing page that explains the app lives in `website/`. To open it on localhost:

```bash
python website/serve.py
```

or double-click `website/baslat.bat`. It opens http://localhost:8000 (or the next free port). No dependencies beyond Python.

## License

MIT
