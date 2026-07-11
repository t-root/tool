import os
import sys
import subprocess
import re


def get_versions():
    out = subprocess.run(["py", "-0"], capture_output=True, text=True).stdout

    # parse từ -V:3.11 hoặc -V:3.13 *
    versions = re.findall(r"-V:(\d+\.\d+)", out)

    return sorted(set(versions), key=lambda v: tuple(map(int, v.split("."))))


def set_default(version):
    path = os.path.join(os.environ["LOCALAPPDATA"], "py.ini")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"[defaults]\npython={version}\n")

    print("Set default Python =", version)


def main():
    versions = get_versions()

    print("Installed:", ", ".join(versions))

    if len(sys.argv) < 2:
        print("No version → nothing changed")
        return

    ver = sys.argv[1].lstrip("-")

    if ver not in versions:
        print("Not installed:", ver)
        return

    set_default(ver)


if __name__ == "__main__":
    main()