import customtkinter as ctk
import psutil
import socket
import subprocess
import threading
import queue
import ipaddress
import re
import sys
import ctypes
import json
import os
import time

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_IPS_FILE = os.path.join(SCRIPT_DIR, "saved_ips.json")
REFRESH_MS = 5000
IPV4_RE = re.compile(r"^\s*(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\s*$")

# Color Palette
BG_DARK = "#0f0f0f"
BG_SIDEBAR = "#161616"
BG_CARD = "#1c1c1c"
BG_INPUT = "#141414"
BORDER = "#2a2a2a"
BORDER_LIGHT = "#333333"
ACCENT = "#6C63FF"
ACCENT_HOVER = "#5A52D5"
SUCCESS = "#34D399"
SUCCESS_HOVER = "#2AB783"
DANGER = "#F87171"
DANGER_HOVER = "#DC2626"
WARNING = "#FBBF24"
TEXT_PRIMARY = "#F5F5F5"
TEXT_SECONDARY = "#888888"
TEXT_DIM = "#555555"


# ── Pure helpers (no UI, covered by tests/) ─────────────

def normalize_ipv4(text):
    """Return a canonical dotted IPv4 string, or None if text is not one."""
    match = IPV4_RE.match(text or "")
    if not match:
        return None
    parts = [int(p) for p in match.groups()]
    if any(p > 255 for p in parts):
        return None
    return ".".join(str(p) for p in parts)


def validate_static_config(ip, mask, gateway=None, dns=()):
    """Return an error message for an unusable static configuration, or None."""
    if not ip:
        return "IP address is required."
    if not mask:
        return "Subnet mask is required."
    try:
        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
    except ValueError:
        return f"{mask} is not a valid subnet mask."
    if net.prefixlen == 0:
        return "Subnet mask 0.0.0.0 is not usable."

    addr = ipaddress.IPv4Address(ip)
    if addr.is_loopback or addr.is_multicast or addr.is_unspecified or addr.is_reserved:
        return f"{ip} cannot be assigned to an adapter."
    if net.prefixlen < 31 and addr in (net.network_address, net.broadcast_address):
        return f"{ip} is the network or broadcast address of {net}."

    if gateway:
        gw = ipaddress.IPv4Address(gateway)
        if gw == addr:
            return "Gateway cannot be the same as the IP address."
        if gw not in net:
            return f"Gateway {gateway} is outside {net}."

    for server in dns:
        if server and ipaddress.IPv4Address(server).is_unspecified:
            return "DNS server 0.0.0.0 is not valid."
    return None


def build_static_commands(iface, ip, mask, gateway=None, dns1=None, dns2=None):
    """netsh commands that set a static address and DNS list on iface."""
    name = f"name={iface}"
    cmds = [["netsh", "interface", "ipv4", "set", "address", name, "source=static",
             f"address={ip}", f"mask={mask}", f"gateway={gateway or 'none'}"]]

    servers = [s for s in (dns1, dns2) if s]
    if servers:
        cmds.append(["netsh", "interface", "ipv4", "set", "dnsservers", name, "source=static",
                     f"address={servers[0]}", "register=primary", "validate=no"])
        for index, server in enumerate(servers[1:], start=2):
            cmds.append(["netsh", "interface", "ipv4", "add", "dnsservers", name,
                         f"address={server}", f"index={index}", "validate=no"])
    else:
        cmds.append(["netsh", "interface", "ipv4", "set", "dnsservers", name,
                     "source=static", "address=none", "validate=no"])
    return cmds


def build_dhcp_commands(iface):
    name = f"name={iface}"
    return [
        ["netsh", "interface", "ipv4", "set", "address", name, "source=dhcp"],
        ["netsh", "interface", "ipv4", "set", "dnsservers", name, "source=dhcp"],
    ]


def load_profiles(path):
    """Read saved profiles. Returns (profiles, warning).

    A file that cannot be read is moved aside instead of being treated as
    empty, so the next save does not wipe the user's profiles.
    """
    if not os.path.exists(path):
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("profile file is not a list")
        return [p for p in data if isinstance(p, dict) and p.get("ip")], None
    except (OSError, ValueError) as e:
        backup = f"{path}.broken-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(path, backup)
            return [], f"Profile file was unreadable, moved to {os.path.basename(backup)}"
        except OSError:
            return [], f"Profile file is unreadable: {e}"


def save_profiles(path, profiles):
    """Write profiles atomically so a crash mid-write cannot corrupt the file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def query_wmi_details():
    """Per-adapter DHCP/gateway/DNS details keyed by connection name.

    Uses WMI because netsh output is localized. Returns {} if WMI is missing
    or fails; the app then shows only what psutil knows.
    """
    try:
        import pythoncom
        import wmi
    except ImportError:
        return {}

    pythoncom.CoInitialize()
    try:
        conn = wmi.WMI()
        adapters = {}
        for a in conn.query("SELECT Index, NetConnectionID, PhysicalAdapter "
                            "FROM Win32_NetworkAdapter WHERE NetConnectionID IS NOT NULL"):
            adapters[a.Index] = {"name": a.NetConnectionID, "physical": bool(a.PhysicalAdapter)}

        details = {}
        for cfg in conn.query("SELECT Index, DHCPEnabled, DefaultIPGateway, DNSServerSearchOrder "
                              "FROM Win32_NetworkAdapterConfiguration"):
            adapter = adapters.get(cfg.Index)
            if not adapter:
                continue
            gateways = [g for g in (cfg.DefaultIPGateway or ()) if "." in g]
            dns = [d for d in (cfg.DNSServerSearchOrder or ()) if "." in d]
            details[adapter["name"]] = {
                "physical": adapter["physical"],
                "dhcp": bool(cfg.DHCPEnabled),
                "gateway": gateways[0] if gateways else None,
                "dns": dns,
            }
        return details
    except Exception:
        return {}
    finally:
        pythoncom.CoUninitialize()


def scan_adapters():
    """Snapshot of usable adapters. Runs on a worker thread (WMI is slow)."""
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    details = query_wmi_details()
    found = {}

    for iface, stat in stats.items():
        if "Loopback" in iface:
            continue
        extra = details.get(iface, {})
        ip = mask = mac = None
        for addr in addrs.get(iface, []):
            if addr.family == socket.AF_INET:
                ip, mask = addr.address, addr.netmask
            elif addr.family == psutil.AF_LINK:
                mac = addr.address

        if stat.isup and not ip:
            continue
        # Unplugged adapters are listed too, so a static IP can be set before
        # connecting the cable. Virtual ones stay hidden to keep the list short.
        if not stat.isup and (not extra.get("physical") or "Bluetooth" in iface):
            continue

        found[iface] = {
            "ip": ip,
            "mask": mask,
            "mac": mac or "??-??-??-??-??-??",
            "up": stat.isup,
            "dhcp": extra.get("dhcp"),
            "gateway": extra.get("gateway"),
            "dns": extra.get("dns", []),
        }
    return found


def run_commands(cmds):
    """Run netsh commands in order. Returns an error string, or None."""
    for args in cmds:
        result = subprocess.run(args, capture_output=True, text=True,
                                encoding="oem", errors="replace",
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            return result.stderr.strip() or result.stdout.strip() or "Unknown error"
    return None


class IPSwitcherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("IP Switcher Pro")
        self.geometry("1000x780")
        self.minsize(900, 760)
        self.configure(fg_color=BG_DARK)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_config = {}
        self.active_interface = None
        self.all_interfaces = {}
        self.display_to_name = {}
        self._results = queue.Queue()
        self._scanning = False
        self._busy = False
        self._msg_after = None
        self.saved_ips, load_warning = load_profiles(SAVED_IPS_FILE)

        self.setup_sidebar()
        self.setup_main_area()
        self.poll_results()
        self.refresh_timer()
        if load_warning:
            self.show_message(load_warning, True)

    # ── Sidebar ──────────────────────────────────────────

    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=260, fg_color=BG_SIDEBAR, corner_radius=0, border_width=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.sidebar_frame.grid_propagate(False)

        # Title
        title_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=24, pady=(32, 0), sticky="ew")

        ctk.CTkLabel(title_frame, text="IP Switcher",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Network Manager",
                     font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))

        # Separator
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=24, pady=(24, 16))

        # Section Header
        header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        header_frame.grid(row=2, column=0, padx=24, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(header_frame, text="PROFILES",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_DIM).pack(side="left")
        self.lbl_count = ctk.CTkLabel(header_frame, text="0",
                                       font=ctk.CTkFont(size=10), text_color=TEXT_DIM)
        self.lbl_count.pack(side="right")

        # Empty state label
        self.lbl_empty = ctk.CTkLabel(self.sidebar_frame, text="No saved profiles yet",
                                       font=ctk.CTkFont(size=11), text_color=TEXT_DIM)
        self.lbl_empty.grid(row=3, column=0, padx=24, pady=(20, 0), sticky="n")

        # Scrollable List
        self.scroll_saved = ctk.CTkScrollableFrame(
            self.sidebar_frame, fg_color="transparent",
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=BORDER_LIGHT)
        self.scroll_saved.grid(row=4, column=0, padx=8, pady=(4, 8), sticky="nsew")

        self.refresh_saved_list()

        # Save Button
        self.btn_save_current = ctk.CTkButton(
            self.sidebar_frame, text="+ Save Current Config", height=38,
            fg_color="transparent", border_width=1, border_color=BORDER_LIGHT,
            text_color=TEXT_SECONDARY, hover_color=BORDER,
            font=ctk.CTkFont(size=12),
            command=self.save_current_input_as_profile, corner_radius=8)
        self.btn_save_current.grid(row=5, column=0, padx=16, pady=(8, 24), sticky="ew")

    # ── Main Area ────────────────────────────────────────

    def setup_main_area(self):
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, padx=32, pady=24, sticky="nsew")
        self.main_content.grid_columnconfigure(0, weight=1)

        # ── Header Row ──
        header = ctk.CTkFrame(self.main_content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Dashboard",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color=TEXT_PRIMARY).pack(side="left")

        # Status Badge
        self.status_badge = ctk.CTkFrame(header, fg_color=BG_CARD, corner_radius=20,
                                          border_width=1, border_color=BORDER)
        self.status_badge.pack(side="right")

        self.status_dot = ctk.CTkLabel(self.status_badge, text="", width=8, height=8,
                                        font=ctk.CTkFont(size=10), text_color=TEXT_DIM)
        self.status_dot.pack(side="left", padx=(14, 6), pady=8)
        self.lbl_interface = ctk.CTkLabel(self.status_badge, text="Scanning...",
                                           font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY)
        self.lbl_interface.pack(side="left", padx=(0, 14), pady=8)

        # ── Info Cards Row ──
        cards_row = ctk.CTkFrame(self.main_content, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        cards_row.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        # IP Card
        self.ip_card = ctk.CTkFrame(cards_row, fg_color=BG_CARD, corner_radius=12,
                                     border_width=1, border_color=BORDER)
        self.ip_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(self.ip_card, text="Current IP",
                     font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(pady=(20, 4), padx=24, anchor="w")
        self.lbl_current_ip = ctk.CTkLabel(self.ip_card, text="---.---.---.---",
                                            font=ctk.CTkFont(size=28, weight="bold", family="Consolas"),
                                            text_color=ACCENT)
        self.lbl_current_ip.pack(pady=(0, 20), padx=24, anchor="w")

        # MAC Card
        self.mac_card = ctk.CTkFrame(cards_row, fg_color=BG_CARD, corner_radius=12,
                                      border_width=1, border_color=BORDER)
        self.mac_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(self.mac_card, text="MAC Address",
                     font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(pady=(20, 4), padx=24, anchor="w")
        self.lbl_current_mac = ctk.CTkLabel(self.mac_card, text="--:--:--:--:--:--",
                                             font=ctk.CTkFont(size=20, weight="bold", family="Consolas"),
                                             text_color=TEXT_SECONDARY)
        self.lbl_current_mac.pack(pady=(0, 20), padx=24, anchor="w")

        # ── Details Strip ──
        details = ctk.CTkFrame(self.main_content, fg_color=BG_CARD, corner_radius=12,
                               border_width=1, border_color=BORDER)
        details.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        self.lbl_details = ctk.CTkLabel(details, text="Mode: —   Mask: —   Gateway: —   DNS: —",
                                         font=ctk.CTkFont(size=12, family="Consolas"),
                                         text_color=TEXT_SECONDARY, anchor="w", justify="left")
        self.lbl_details.pack(side="left", padx=24, pady=14, fill="x", expand=True)

        self.btn_use_current = ctk.CTkButton(
            details, text="Use Current", width=110, height=30,
            font=ctk.CTkFont(size=11), fg_color=BORDER, hover_color=BORDER_LIGHT,
            text_color=TEXT_SECONDARY, corner_radius=6, command=self.use_current_config)
        self.btn_use_current.pack(side="right", padx=(8, 16), pady=10)

        # ── Config Card ──
        self.config_card = ctk.CTkFrame(self.main_content, fg_color=BG_CARD, corner_radius=12,
                                         border_width=1, border_color=BORDER)
        self.config_card.grid(row=3, column=0, sticky="nsew", pady=(0, 0))
        self.config_card.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(3, weight=1)

        # Config Header
        config_header = ctk.CTkFrame(self.config_card, fg_color="transparent")
        config_header.pack(fill="x", padx=28, pady=(24, 16))
        ctk.CTkLabel(config_header, text="Configuration",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT_PRIMARY).pack(side="left")

        # Message Label (in header, right side)
        self.lbl_msg = ctk.CTkLabel(config_header, text="", wraplength=380, justify="right",
                                     font=ctk.CTkFont(size=11, weight="bold"), text_color=SUCCESS)
        self.lbl_msg.pack(side="right")

        # Separator
        ctk.CTkFrame(self.config_card, height=1, fg_color=BORDER).pack(fill="x", padx=28)

        # Input Grid
        self.input_grid = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.input_grid.pack(fill="x", padx=28, pady=(20, 0))
        self.input_grid.grid_columnconfigure(1, weight=1)

        # Adapter Dropdown
        self._add_label("Adapter", 0)
        self.adapter_var = ctk.StringVar(value="Scanning...")
        self.adapter_dropdown = ctk.CTkComboBox(
            self.input_grid, variable=self.adapter_var,
            values=["Scanning..."], width=380, height=34,
            fg_color=BG_INPUT, border_color=BORDER, button_color=BORDER,
            button_hover_color=BORDER_LIGHT, dropdown_fg_color=BG_INPUT,
            dropdown_hover_color=BORDER,
            font=ctk.CTkFont(size=12, family="Consolas"), state="readonly",
            command=self.on_adapter_selected, corner_radius=6)
        self.adapter_dropdown.grid(row=0, column=1, sticky="w", pady=6)

        # IP inputs
        self.frame_ip = self._add_ip_row("IP Address", 1)
        self.entries_ip = self.frame_ip.entries

        self.frame_subnet = self._add_ip_row("Subnet Mask", 2)
        self.entries_subnet = self.frame_subnet.entries
        self.fill_entries(self.entries_subnet, "255.255.255.0")

        self.frame_gateway = self._add_ip_row("Gateway", 3)
        self.entries_gateway = self.frame_gateway.entries

        self.frame_dns = self._add_ip_row("DNS Server", 4)
        self.entries_dns = self.frame_dns.entries
        self.fill_entries(self.entries_dns, "8.8.8.8")

        self.frame_dns2 = self._add_ip_row("Alt. DNS", 5)
        self.entries_dns2 = self.frame_dns2.entries

        # ── Action Buttons ──
        btn_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=(20, 24))

        self.btn_apply = ctk.CTkButton(
            btn_frame, text="Apply Settings", command=self.apply_static_ip,
            height=42, width=160, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8)
        self.btn_apply.pack(side="left", padx=(0, 12))

        self.btn_dhcp = ctk.CTkButton(
            btn_frame, text="DHCP Mode", command=self.set_dhcp,
            height=42, width=140, font=ctk.CTkFont(size=13),
            fg_color="transparent", border_width=1, border_color=BORDER_LIGHT,
            text_color=TEXT_SECONDARY, hover_color=BORDER, corner_radius=8)
        self.btn_dhcp.pack(side="left")

    # ── UI Helpers ───────────────────────────────────────

    def _add_label(self, text, row):
        ctk.CTkLabel(self.input_grid, text=text, width=100, anchor="w",
                     font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY).grid(
            row=row, column=0, pady=6, sticky="w")

    def _add_ip_row(self, label_text, row):
        self._add_label(label_text, row)
        container = ctk.CTkFrame(self.input_grid, fg_color=BG_INPUT, corner_radius=6,
                                  border_width=1, border_color=BORDER)
        container.grid(row=row, column=1, sticky="w", pady=4)
        return self.create_4block_entry(container)

    def create_4block_entry(self, parent):
        parent.entries = []
        validation_cmd = (self.register(self.validate_entry), '%P')

        for i in range(4):
            entry = ctk.CTkEntry(parent, width=48, height=32, justify="center", border_width=0,
                                 fg_color="transparent", text_color=TEXT_PRIMARY,
                                 font=ctk.CTkFont(size=14, family="Consolas"),
                                 validate="key", validatecommand=validation_cmd)
            entry.pack(side="left", padx=1, pady=1)
            entry.bind("<KeyRelease>", lambda event, idx=i, entries=parent.entries: self.on_key_release(event, idx, entries))
            entry.bind("<KeyPress-period>", lambda event, idx=i, entries=parent.entries: self.jump_next(idx, entries))
            entry.bind("<KeyPress-KP_Decimal>", lambda event, idx=i, entries=parent.entries: self.jump_next(idx, entries))
            entry.bind("<KeyPress-BackSpace>", lambda event, idx=i, entries=parent.entries: self.on_backspace(idx, entries))
            entry.bind("<<Paste>>", lambda event, entries=parent.entries: self.on_paste(entries))
            parent.entries.append(entry)

            if i < 3:
                ctk.CTkLabel(parent, text=".", font=ctk.CTkFont(size=14, weight="bold"),
                             text_color=TEXT_DIM, width=4).pack(side="left")
        return parent

    # ── Data Logic ───────────────────────────────────────

    def save_saved_ips(self):
        try:
            save_profiles(SAVED_IPS_FILE, self.saved_ips)
        except OSError as e:
            self.show_message(f"Could not save profiles: {e}", True)
        self.refresh_saved_list()

    def refresh_saved_list(self):
        for widget in self.scroll_saved.winfo_children():
            widget.destroy()

        count = len(self.saved_ips)
        self.lbl_count.configure(text=str(count))

        if count == 0:
            self.lbl_empty.grid()
        else:
            self.lbl_empty.grid_remove()

        for idx, item in enumerate(self.saved_ips):
            row = ctk.CTkFrame(self.scroll_saved, fg_color=BG_CARD, corner_radius=8,
                               border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=3, padx=4)

            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=(12, 0), pady=10)

            subtitle = item.get('ip', '')
            try:
                prefix = ipaddress.IPv4Network(f"0.0.0.0/{item['subnet']}").prefixlen
                subtitle = f"{subtitle}/{prefix}"
            except (KeyError, ValueError):
                pass

            ctk.CTkLabel(info_frame, text=item.get('name', 'Profile'),
                         font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_PRIMARY,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=subtitle,
                         font=ctk.CTkFont(size=10, family="Consolas"), text_color=TEXT_DIM,
                         anchor="w").pack(anchor="w")

            # Load button
            load_btn = ctk.CTkButton(row, text="Load", width=44, height=28,
                                      font=ctk.CTkFont(size=10),
                                      fg_color=BORDER, hover_color=BORDER_LIGHT,
                                      text_color=TEXT_SECONDARY, corner_radius=6,
                                      command=lambda i=item: self.load_profile_to_entries(i))
            load_btn.pack(side="right", padx=(4, 4), pady=8)

            del_btn = ctk.CTkButton(row, text="x", width=28, height=28,
                                     font=ctk.CTkFont(size=11),
                                     fg_color="transparent", hover_color=DANGER_HOVER,
                                     text_color=TEXT_DIM, corner_radius=6,
                                     command=lambda i=idx: self.delete_saved_ip(i))
            del_btn.pack(side="right", pady=8)

    def delete_saved_ip(self, index):
        name = self.saved_ips[index].get("name", "Profile")
        del self.saved_ips[index]
        self.save_saved_ips()
        self.show_message(f"Deleted '{name}'", False)

    def save_current_input_as_profile(self):
        ip = self.get_ip_from_entries(self.entries_ip)
        if not ip:
            self.show_message("Enter an IP address first.", True)
            return

        dialog = ctk.CTkInputDialog(text="Profile name:", title="Save Profile")
        name = (dialog.get_input() or "").strip()
        if not name:
            return

        profile = {"name": name, "ip": ip}
        for key, entries in (("subnet", self.entries_subnet), ("gateway", self.entries_gateway),
                             ("dns", self.entries_dns), ("dns2", self.entries_dns2)):
            value = self.get_ip_from_entries(entries)
            if value:
                profile[key] = value

        # Saving under an existing name updates that profile instead of duplicating it
        for i, existing in enumerate(self.saved_ips):
            if existing.get("name", "").lower() == name.lower():
                self.saved_ips[i] = profile
                self.save_saved_ips()
                self.show_message(f"Updated '{name}'", False)
                return

        self.saved_ips.append(profile)
        self.save_saved_ips()
        self.show_message(f"Saved '{name}'", False)

    def load_profile_to_entries(self, item):
        self.fill_entries(self.entries_ip, item.get('ip', ''))
        self.fill_entries(self.entries_subnet, item.get('subnet', '255.255.255.0'))
        self.fill_entries(self.entries_dns, item.get('dns', ''))
        self.fill_entries(self.entries_dns2, item.get('dns2', ''))

        if 'gateway' in item:
            self.fill_entries(self.entries_gateway, item['gateway'])
        elif 'subnet' in item:
            # Saved with every field: no gateway means it was left empty on purpose
            self.fill_entries(self.entries_gateway, "")
        else:
            # Profiles from older versions stored only the IP; guess x.y.z.1
            parts = item.get('ip', '').split('.')
            self.fill_entries(self.entries_gateway,
                              f"{parts[0]}.{parts[1]}.{parts[2]}.1" if len(parts) == 4 else "")

        self.show_message(f"Loaded '{item.get('name')}'", False)

    def use_current_config(self):
        info = self.all_interfaces.get(self.active_interface)
        if not info or not info["ip"]:
            self.show_message("Selected adapter has no IPv4 address.", True)
            return
        dns = info["dns"] + ["", ""]
        self.fill_entries(self.entries_ip, info["ip"])
        self.fill_entries(self.entries_subnet, info["mask"] or "255.255.255.0")
        self.fill_entries(self.entries_gateway, info["gateway"] or "")
        self.fill_entries(self.entries_dns, dns[0])
        self.fill_entries(self.entries_dns2, dns[1])
        self.show_message("Copied current settings", False)

    def fill_entries(self, entries, ip_str):
        for e in entries:
            e.delete(0, 'end')
        if not ip_str:
            return
        parts = ip_str.split('.')
        if len(parts) == 4:
            for i, part in enumerate(parts):
                entries[i].insert(0, part)

    def get_ip_from_entries(self, entries):
        return normalize_ipv4(".".join(e.get() for e in entries))

    def validate_entry(self, value):
        if value == "":
            return True
        if not value.isdigit():
            return False
        if len(value) > 3:
            return False
        return True

    def on_key_release(self, event, idx, entries):
        val = entries[idx].get()
        if len(val) == 3 and idx < 3:
            if not (event.keysym == "BackSpace" or event.keysym.startswith("Left")
                    or event.keysym in ("Tab", "ISO_Left_Tab")):
                entries[idx + 1].focus_set()
        if val.isdigit() and int(val) > 255:
            entries[idx].delete(0, 'end')
            entries[idx].insert(0, "255")

    def jump_next(self, idx, entries):
        if idx < 3 and entries[idx].get():
            entries[idx + 1].focus_set()
            entries[idx + 1].select_range(0, 'end')
        return "break"

    def on_backspace(self, idx, entries):
        if idx > 0 and entries[idx].get() == "":
            entries[idx - 1].focus_set()
            entries[idx - 1].icursor('end')
            return "break"
        return None

    def on_paste(self, entries):
        try:
            text = self.clipboard_get()
        except Exception:
            return "break"
        ip = normalize_ipv4(text)
        if ip:
            self.fill_entries(entries, ip)
            entries[3].focus_set()
        return "break"

    def show_message(self, text, is_error=False):
        if self._msg_after:
            self.after_cancel(self._msg_after)
        self.lbl_msg.configure(text=text, text_color=DANGER if is_error else SUCCESS)
        self._msg_after = self.after(6000 if is_error else 4000, self._clear_message)

    def _clear_message(self):
        self._msg_after = None
        self.lbl_msg.configure(text="")

    # ── Background Work ──────────────────────────────────

    def run_in_background(self, work, on_done):
        """Run work() off the UI thread; on_done(result) runs on the UI thread."""
        def target():
            try:
                result = work()
            except Exception as e:
                result = e
            self._results.put((on_done, result))
        threading.Thread(target=target, daemon=True).start()

    def poll_results(self):
        while True:
            try:
                on_done, result = self._results.get_nowait()
            except queue.Empty:
                break
            on_done(result)
        self.after(100, self.poll_results)

    def set_busy(self, busy, text=""):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in (self.btn_apply, self.btn_dhcp, self.btn_use_current):
            btn.configure(state=state)
        if busy:
            if self._msg_after:
                self.after_cancel(self._msg_after)
                self._msg_after = None
            self.lbl_msg.configure(text=text, text_color=WARNING)

    # ── Network Logic ────────────────────────────────────

    def refresh_timer(self):
        self.request_scan()
        self.after(REFRESH_MS, self.refresh_timer)

    def request_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.run_in_background(scan_adapters, self.on_scan_done)

    def on_scan_done(self, found):
        self._scanning = False
        if isinstance(found, Exception):
            return
        self.update_adapter_list(found)

    def on_adapter_selected(self, choice):
        iface_name = self.display_to_name.get(choice)
        if iface_name and iface_name in self.all_interfaces:
            self.active_interface = iface_name
            self.update_status_display()

    @staticmethod
    def display_name(name, info):
        state = "" if info["up"] else "  (not connected)"
        return f"{name}  [{info['mac']}]{state}"

    def update_adapter_list(self, found):
        old_names = {n: self.display_name(n, i) for n, i in self.all_interfaces.items()}
        new_names = {n: self.display_name(n, i) for n, i in found.items()}
        self.all_interfaces = found

        if new_names != old_names:
            self.display_to_name = {d: n for n, d in new_names.items()}
            # Connected adapters first
            ordered = sorted(found, key=lambda n: (not found[n]["up"], n.lower()))
            display_names = [new_names[n] for n in ordered] or ["No adapters found"]
            self.adapter_dropdown.configure(values=display_names)

            if self.active_interface not in found:
                self.active_interface = ordered[0] if ordered else None
            self.adapter_var.set(new_names[self.active_interface] if self.active_interface
                                 else "No adapters found")

        self.update_status_display()

    def update_status_display(self):
        info = self.all_interfaces.get(self.active_interface)
        if not info:
            self.lbl_interface.configure(text="No adapter", text_color=DANGER)
            self.status_dot.configure(text_color=DANGER)
            self.lbl_current_ip.configure(text="---.---.---.---")
            self.lbl_current_mac.configure(text="--:--:--:--:--:--")
            self.lbl_details.configure(text="Mode: —   Mask: —   Gateway: —   DNS: —")
            return

        color = SUCCESS if info["up"] else WARNING
        label = self.active_interface if info["up"] else f"{self.active_interface} · not connected"
        self.lbl_interface.configure(text=label, text_color=color)
        self.status_dot.configure(text_color=color)
        self.lbl_current_ip.configure(text=info["ip"] or "---.---.---.---")
        self.lbl_current_mac.configure(text=info["mac"])

        mode = {True: "DHCP", False: "Static", None: "—"}[info["dhcp"]]
        dns = ", ".join(info["dns"]) or "—"
        self.lbl_details.configure(
            text=f"Mode: {mode}   Mask: {info['mask'] or '—'}   "
                 f"Gateway: {info['gateway'] or '—'}   DNS: {dns}")

    def apply_static_ip(self):
        if self._busy:
            return
        if not self.active_interface:
            self.show_message("No active interface!", True)
            return

        new_ip = self.get_ip_from_entries(self.entries_ip)
        subnet = self.get_ip_from_entries(self.entries_subnet)
        gateway = self.get_ip_from_entries(self.entries_gateway)
        dns1 = self.get_ip_from_entries(self.entries_dns)
        dns2 = self.get_ip_from_entries(self.entries_dns2)

        for label, entries, value in (("Gateway", self.entries_gateway, gateway),
                                      ("DNS", self.entries_dns, dns1),
                                      ("Alt. DNS", self.entries_dns2, dns2)):
            if not value and any(e.get() for e in entries):
                self.show_message(f"{label} is incomplete.", True)
                return

        error = validate_static_config(new_ip, subnet, gateway, (dns1, dns2))
        if error:
            self.show_message(error, True)
            return

        iface = self.active_interface
        cmds = build_static_commands(iface, new_ip, subnet, gateway, dns1, dns2)
        self.set_busy(True, "Applying...")
        self.run_in_background(lambda: run_commands(cmds),
                               lambda err: self.on_command_done(err, f"Applied to {iface}"))

    def set_dhcp(self):
        if self._busy:
            return
        if not self.active_interface:
            self.show_message("No active interface!", True)
            return

        iface = self.active_interface
        self.set_busy(True, "Switching to DHCP...")
        self.run_in_background(lambda: run_commands(build_dhcp_commands(iface)),
                               lambda err: self.on_command_done(err, f"{iface} switched to DHCP"))

    def on_command_done(self, error, success_text):
        self.set_busy(False)
        if isinstance(error, Exception):
            self.show_message(f"Error: {error}", True)
        elif error:
            self.show_message(f"Failed: {error[:160]}", True)
        else:
            self.show_message(success_text, False)
        self.after(2000, self.request_scan)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def hide_console():
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)


def get_pythonw():
    """Return pythonw.exe path to avoid console window on re-launch."""
    exe = sys.executable
    folder = os.path.dirname(exe)
    pythonw = os.path.join(folder, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return exe


if __name__ == "__main__":
    hide_console()
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", get_pythonw(), f'"{script}"', None, 1)
    else:
        app = IPSwitcherApp()
        app.mainloop()
