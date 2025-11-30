#!/usr/bin/env python3
"""
Export WiFi profiles with passwords from Windows
Equivalent of passwifi.cmd
"""

import os
import subprocess
import sys
from pathlib import Path

def main():
    # Get current script directory
    script_dir = Path(__file__).parent.absolute()
    
    # Create Wifi directory if it doesn't exist
    wifi_dir = script_dir / "Wifi"
    wifi_dir.mkdir(exist_ok=True)
    
    print(f"Exporting WiFi profiles to: {wifi_dir}")
    
    # Export WiFi profiles with clear keys (passwords)
    try:
        command = f'netsh wlan export profile key=clear folder="{wifi_dir}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n")
            print("Installed successfully. Press any key to exit.")
            print("\n")
            input()
        else:
            print("Error:", result.stderr)
            input("Press any key to exit...")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error exporting WiFi profiles: {e}")
        input("Press any key to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
