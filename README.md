# IP Switcher Pro

A Windows desktop app to quickly switch between static IP configurations and DHCP mode on network adapters.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Adapter selection** — Dropdown lists network adapters with MAC identification, including unplugged physical adapters so you can configure them before connecting
- **Live details** — Shows whether the adapter is on DHCP or static, plus its mask, gateway and DNS servers
- **Static IP configuration** — Set IP, subnet mask, optional gateway, and primary/alternate DNS in one click
- **Input checks** — Rejects invalid masks, network/broadcast addresses, and gateways outside the subnet before anything is changed
- **DHCP mode** — Revert any adapter to automatic configuration instantly
- **Saved profiles** — Store and load complete configurations (IP, mask, gateway, both DNS servers); saving under an existing name updates it
- **Use Current** — Copy the adapter's live settings into the form, e.g. to save them as a profile
- **Fast entry** — Paste a full address into any box; `.` jumps to the next block
- **Responsive UI** — Network changes and scans run in the background, so the window never freezes
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
git clone https://github.com/EgeErrdag/IP-switcher.git
cd IP-switcher
py -m pip install -r requirements.txt
```

## Usage

**Option 1** — Double-click `run.bat`

**Option 2** — Run from terminal:
```bash
python main.py
```

The app will automatically request admin privileges if needed.

## How It Works

- Uses `psutil` to detect network adapters and their addresses, and WMI (`wmi` + `pywin32`) for DHCP state, gateway and DNS, since `netsh` output depends on the Windows language
- Applies network changes via Windows `netsh interface ipv4` commands on a background thread
- Profiles are saved locally to `saved_ips.json` (excluded from git). The file is written atomically, and if it ever becomes unreadable it is moved aside as `saved_ips.json.broken-<time>` instead of being overwritten

## Tests

```bash
py -m unittest discover -s tests
```

## License

MIT
