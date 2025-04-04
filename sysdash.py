from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
import psutil
import subprocess
import time
import os
import re

console = Console()

def ascii_bar(usage, width=25):
    blocks = "█▓▒░ "
    full = int((usage / 100) * width)
    return f"[{'█' * full}{' ' * (width - full)}] {usage:.1f}%"

def signal_bar(rssi, width=10):
    try:
        bars = int((100 + int(float(rssi))) / 10)
        return "[" + "█" * bars + " " * (width - bars) + f"] {rssi} dBm"
    except:
        return "[No Signal]"

def get_cpu_section():
    cpu = psutil.cpu_percent(percpu=True)
    lines = []
    for i, usage in enumerate(cpu):
        lines.append(f"Core {i:02d}: {ascii_bar(usage)}")
    return Panel("\n".join(lines), title="🧠 CPU USAGE", border_style="cyan", padding=(1, 2))

def get_top_processes():
    table = Table(title="🔥 TOP SERVICES (CPU)", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="bold")
    table.add_column("CPU %", justify="right")
    table.add_column("PID", justify="right")
    procs = sorted(psutil.process_iter(['name', 'cpu_percent', 'pid']), key=lambda p: p.info['cpu_percent'], reverse=True)
    for p in procs[:5]:
        name = p.info['name'] or "?"
        cpu = p.info['cpu_percent'] or 0
        pid = p.info['pid']
        table.add_row(str(name), f"{cpu:0.1f}", str(pid))
    return Panel(table, border_style="magenta")

def get_network_interfaces():
    table = Table(title="🌐 NETWORK INTERFACES", show_header=True, header_style="bold green")
    table.add_column("Iface")
    table.add_column("IP")
    table.add_column("Speed")
    table.add_column("Duplex")
    output = subprocess.getoutput("ip -o addr show")
    lines = output.strip().split('\n')
    added = set()
    for line in lines:
        parts = line.split()
        iface = parts[1]
        if iface in added:
            continue
        added.add(iface)
        ip = parts[3] if len(parts) > 3 else "—"
        try:
            ethtool = subprocess.getoutput(f"ethtool {iface}")
            speed = re.search(r"Speed: (.+)", ethtool)
            duplex = re.search(r"Duplex: (.+)", ethtool)
            speed = speed.group(1) if speed else "?"
            duplex = duplex.group(1) if duplex else "?"
        except:
            speed, duplex = "?", "?"
        table.add_row(iface, ip, speed, duplex)
    return Panel(table, border_style="green")

def get_multicast_routes():
    table = Table(title="📡 MULTICAST ROUTES", show_header=True, header_style="bold yellow")
    table.add_column("Iface")
    table.add_column("Group")
    ss_out = subprocess.getoutput("ss -unap")
    found = False
    for line in ss_out.splitlines():
        if "239." in line or "224." in line:
            found = True
            parts = line.split()
            try:
                dest = parts[4]
                ip = dest.rsplit(":", 1)[0]
                iface = parts[-1].split(":")[-1]
                table.add_row(iface, ip)
            except:
                continue

    if not found:
        # Fallback using ip maddr
        ip_maddr = subprocess.getoutput("ip maddr")
        for line in ip_maddr.splitlines():
            if "inet" in line and ("224." in line or "239." in line):
                ip = line.strip().split()[1]
                iface_match = re.search(r'dev\s+(\w+)', line)
                iface = iface_match.group(1) if iface_match else "?"
                table.add_row(iface, ip)
    return Panel(table, border_style="yellow")

def get_wifi_info():
    iface = "wlan0"
    try:
        info = subprocess.getoutput(f"iw dev {iface} link")
        ssid = re.search(r'SSID: (.+)', info).group(1)
        freq = re.search(r'freq: (\d+)', info).group(1)
        tx = re.search(r'tx bitrate: ([\d.]+ .bit/s)', info)
        rssi = subprocess.getoutput(f"grep {iface} /proc/net/wireless").split()[2]
        snr = subprocess.getoutput(f"grep {iface} /proc/net/wireless").split()[3]
        return Panel(
            f"SSID: [bold green]{ssid}\n[/]Freq: {freq} MHz\nTX: {tx.group(1) if tx else '?'}\nSignal: {signal_bar(rssi)} SNR: {snr}",
            title="📶 WIFI (wlan0)",
            border_style="blue"
        )
    except:
        return Panel("🚫 WiFi Info Not Found", title="WiFi", border_style="red")

def get_zerotier_info():
    try:
        out = subprocess.getoutput("zerotier-cli info")
        networks = subprocess.getoutput("zerotier-cli listnetworks")
        return Panel(f"{out}\n\n{networks}", title="🌐 ZEROTIER VPN", border_style="green")
    except:
        return Panel("🚫 ZeroTier not available", border_style="red")

def get_tetrapack_info():
    try:
        out = subprocess.getoutput("systemctl status tetrapack.service")
        summary = "\n".join(out.splitlines()[:6])
        return Panel(summary, title="🧪 TETRAPACK SERVICE", border_style="magenta")
    except:
        return Panel("🚫 Tetrapack service not found", border_style="red")

def render():
    layout = Table.grid(expand=True)
    layout.add_row(
        get_cpu_section(),
        get_top_processes()
    )
    layout.add_row(
        get_network_interfaces(),
        get_multicast_routes()
    )
    layout.add_row(
        get_wifi_info(),
        get_zerotier_info()
    )
    layout.add_row(
        get_tetrapack_info()
    )
    return layout

if __name__ == "__main__":
    with Live(render(), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                live.update(render())
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nExiting...")
