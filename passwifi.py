#!/usr/bin/env python3
"""
Export WiFi profiles from Windows and save them into a clean TXT file (SSID and Password only)
Automatically exits when finished.
"""

import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    # Lấy đường dẫn tuyệt đối của thư mục chứa script
    script_dir = Path(__file__).parent.absolute()
    
    # Tạo một thư mục tạm để chứa các file XML do netsh xuất ra
    temp_wifi_dir = script_dir / "temp_wifi_xml"
    temp_wifi_dir.mkdir(exist_ok=True)
    
    # File kết quả cuối cùng
    output_file = script_dir / "wifi_passwords.txt"
    
    print("Scanning info WiFi...")
    
    try:
        # Sử dụng đường dẫn tuyệt đối tới netsh.exe để xuất các profile ra file XML tạm thời
        command = f'C:\\Windows\\System32\\netsh.exe wlan export profile key=clear folder="{temp_wifi_dir}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            sys.exit(1)
            
        # Đọc tất cả các file XML được sinh ra để lọc Tên và Mật khẩu
        wifi_list = []
        xml_files = list(temp_wifi_dir.glob("*.xml"))
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Định nghĩa namespace của tệp XML từ Microsoft WLAN profile
                ns = {'wp': 'http://www.microsoft.com/networking/WLAN/profile/v1'}
                
                # Tìm tên WiFi (SSID)
                name_node = root.find('.//wp:name', ns)
                ssid = name_node.text if name_node is not None else "Không rõ"
                
                # Tìm mật khẩu (KeyMaterial)
                key_node = root.find('.//wp:keyMaterial', ns)
                password = key_node.text if key_node is not None else "[Không có mật khẩu hoặc Mạng mở]"
                
                wifi_list.append((ssid, password))
            except Exception:
                # Bỏ qua nếu có file XML nào bị lỗi cấu trúc định dạng
                continue
        
        # Ghi danh sách sạch vào file TXT duy nhất
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=== DANH SÁCH MẠNG WIFI ĐÃ LƯU ===\n\n")
            for ssid, password in wifi_list:
                f.write(f"Tên WiFi: {ssid}\n")
                f.write(f"Mật khẩu: {password}\n")
                f.write("-" * 30 + "\n")
                
        print(f"Done! Save as: {output_file.name}")
        
        # Dọn dẹp: Xóa thư mục tạm và các file XML bên trong
        for xml_file in xml_files:
            try: os.remove(xml_file)
            except: pass
        try: os.rmdir(temp_wifi_dir)
        except: pass
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()