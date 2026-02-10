import customtkinter as ctk
import psutil
import socket
import subprocess
import sys
import ctypes
import json
import os

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_IPS_FILE = os.path.join(SCRIPT_DIR, "saved_ips.json")

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


class IPSwitcherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("IP Switcher Pro")
        self.geometry("1000x680")
        self.minsize(900, 620)
        self.configure(fg_color=BG_DARK)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_config = {}
        self.active_interface = None
        self.all_interfaces = {}
        self.display_to_name = {}
        self.saved_ips = self.load_saved_ips()

        self.setup_sidebar()
        self.setup_main_area()
        self.refresh_timer()

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
        self.main_content.grid(row=0, column=1, padx=32, pady=32, sticky="nsew")
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

        # ── Config Card ──
        self.config_card = ctk.CTkFrame(self.main_content, fg_color=BG_CARD, corner_radius=12,
                                         border_width=1, border_color=BORDER)
        self.config_card.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        self.config_card.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(2, weight=1)

        # Config Header
        config_header = ctk.CTkFrame(self.config_card, fg_color="transparent")
        config_header.pack(fill="x", padx=28, pady=(24, 16))
        ctk.CTkLabel(config_header, text="Configuration",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT_PRIMARY).pack(side="left")

        # Message Label (in header, right side)
        self.lbl_msg = ctk.CTkLabel(config_header, text="",
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

        # ── Action Buttons ──
        btn_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=(24, 28))

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
            parent.entries.append(entry)

            if i < 3:
                ctk.CTkLabel(parent, text=".", font=ctk.CTkFont(size=14, weight="bold"),
                             text_color=TEXT_DIM, width=4).pack(side="left")
        return parent

    # ── Data Logic ───────────────────────────────────────

    def load_saved_ips(self):
        if os.path.exists(SAVED_IPS_FILE):
            try:
                with open(SAVED_IPS_FILE, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_saved_ips(self):
        with open(SAVED_IPS_FILE, "w") as f:
            json.dump(self.saved_ips, f)
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

            ctk.CTkLabel(info_frame, text=item.get('name', 'Profile'),
                         font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_PRIMARY,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=item.get('ip', ''),
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
        del self.saved_ips[index]
        self.save_saved_ips()

    def save_current_input_as_profile(self):
        ip = self.get_ip_from_entries(self.entries_ip)
        gateway = self.get_ip_from_entries(self.entries_gateway)
        if not ip:
            self.show_message("Enter an IP address first.", True)
            return

        dialog = ctk.CTkInputDialog(text="Profile name:", title="Save Profile")
        name = dialog.get_input()
        if name:
            profile = {"name": name, "ip": ip}
            if gateway:
                profile["gateway"] = gateway
            self.saved_ips.append(profile)
            self.save_saved_ips()
            self.show_message(f"Saved '{name}'", False)

    def load_profile_to_entries(self, item):
        self.fill_entries(self.entries_ip, "")
        self.fill_entries(self.entries_gateway, "")

        self.fill_entries(self.entries_ip, item.get('ip', ''))
        if 'gateway' in item:
            self.fill_entries(self.entries_gateway, item['gateway'])
        elif 'ip' in item:
            parts = item['ip'].split('.')
            if len(parts) == 4:
                self.fill_entries(self.entries_gateway, f"{parts[0]}.{parts[1]}.{parts[2]}.1")

        self.show_message(f"Loaded '{item.get('name')}'", False)

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
        parts = [e.get() for e in entries]
        if any(p == "" or not p.isdigit() for p in parts):
            return None
        return ".".join(parts)

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
            if not (event.keysym == "BackSpace" or event.keysym.startswith("Left")):
                entries[idx + 1].focus_set()
        if val.isdigit() and int(val) > 255:
            entries[idx].delete(0, 'end')
            entries[idx].insert(0, "255")

    def show_message(self, text, is_error=False):
        self.lbl_msg.configure(text=text, text_color=DANGER if is_error else SUCCESS)
        self.after(4000, lambda: self.lbl_msg.configure(text=""))

    # ── Network Logic ────────────────────────────────────

    def refresh_timer(self):
        self.get_network_info()
        self.after(5000, self.refresh_timer)

    def on_adapter_selected(self, choice):
        iface_name = self.display_to_name.get(choice)
        if iface_name and iface_name in self.all_interfaces:
            self.active_interface = iface_name
            info = self.all_interfaces[iface_name]
            self.lbl_current_ip.configure(text=info["ip"])
            self.lbl_current_mac.configure(text=info["mac"])
            self.lbl_interface.configure(text=iface_name, text_color=SUCCESS)
            self.status_dot.configure(text_color=SUCCESS)

    def get_network_info(self):
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            found = {}

            for iface, stat in stats.items():
                if not stat.isup or iface not in addrs:
                    continue
                if "Loopback" in iface:
                    continue
                ip = None
                mac = None
                for addr in addrs[iface]:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                    elif addr.family == -1:
                        mac = addr.address
                if ip:
                    found[iface] = {"ip": ip, "mac": mac or "??-??-??-??-??-??"}

            prev_interfaces = set(self.all_interfaces.keys())
            self.all_interfaces = found

            if set(found.keys()) != prev_interfaces:
                self.display_to_name = {}
                display_names = []
                for name, info in found.items():
                    display = f"{name}  [{info['mac']}]"
                    display_names.append(display)
                    self.display_to_name[display] = name

                if not display_names:
                    display_names = ["No adapters found"]

                self.adapter_dropdown.configure(values=display_names)

                if self.active_interface not in found and found:
                    first_name = list(found.keys())[0]
                    self.active_interface = first_name
                    for d, n in self.display_to_name.items():
                        if n == first_name:
                            self.adapter_var.set(d)
                            break
                elif not found:
                    self.active_interface = None
                    self.adapter_var.set("No adapters found")

            if self.active_interface and self.active_interface in found:
                info = found[self.active_interface]
                self.lbl_interface.configure(text=self.active_interface, text_color=SUCCESS)
                self.status_dot.configure(text_color=SUCCESS)
                self.lbl_current_ip.configure(text=info["ip"])
                self.lbl_current_mac.configure(text=info["mac"])
            else:
                self.lbl_interface.configure(text="Disconnected", text_color=DANGER)
                self.status_dot.configure(text_color=DANGER)
                self.lbl_current_ip.configure(text="---.---.---.---")
                self.lbl_current_mac.configure(text="--:--:--:--:--:--")

        except Exception:
            pass

    def apply_static_ip(self):
        if not self.active_interface:
            self.show_message("No active interface!", True)
            return

        new_ip = self.get_ip_from_entries(self.entries_ip)
        subnet = self.get_ip_from_entries(self.entries_subnet)
        gateway = self.get_ip_from_entries(self.entries_gateway)
        dns = self.get_ip_from_entries(self.entries_dns)

        if not new_ip or not subnet or not gateway:
            self.show_message("IP, Subnet, and Gateway are required!", True)
            return

        self.lbl_msg.configure(text="Applying...", text_color=WARNING)
        self.update_idletasks()

        cmds = [
            f'netsh interface ip set address "{self.active_interface}" static {new_ip} {subnet} {gateway}',
        ]
        if dns:
            cmds.append(f'netsh interface ip set dns "{self.active_interface}" static {dns}')
        else:
            cmds.append(f'netsh interface ip set dns "{self.active_interface}" static 8.8.8.8')

        try:
            for c in cmds:
                result = subprocess.run(c, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    self.show_message(f"Failed: {err[:80]}", True)
                    return
            self.show_message("Applied successfully", False)
            self.after(2000, self.get_network_info)
        except Exception as e:
            self.show_message(f"Error: {str(e)}", True)

    def set_dhcp(self):
        if not self.active_interface:
            return

        self.lbl_msg.configure(text="Switching to DHCP...", text_color=WARNING)
        self.update_idletasks()

        try:
            for c in [
                f'netsh interface ip set address "{self.active_interface}" source=dhcp',
                f'netsh interface ip set dns "{self.active_interface}" source=dhcp',
            ]:
                result = subprocess.run(c, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    self.show_message(f"Failed: {err[:80]}", True)
                    return
            self.show_message("Switched to DHCP", False)
            self.after(2000, self.get_network_info)
        except Exception as e:
            self.show_message(f"Error: {str(e)}", True)


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
