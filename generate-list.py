import os
import sys
from datetime import datetime, timedelta


def progress(current, total, bar_length=40):
    """Hiển thị thanh tiến trình."""
    percent = current / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "-" * (bar_length - filled)

    sys.stdout.write(f"\r[{bar}] {percent * 100:6.2f}%")
    sys.stdout.flush()

    if current == total:
        print()


def generate_number_list(script_dir):
    print("Select the type of file to generate:")
    for i in range(1, 11):
        start = f"{0:0{i}d}"
        end = f"{10 ** i - 1:0{i}d}"
        print(f"{i}. {start}-{end}")

    print("11. DDMMYYYY")

    option = input("Enter your choice (1-11): ").strip()

    if not option.isdigit():
        print("Invalid choice!")
        return

    option = int(option)

    if option == 11:
        generate_date_list(script_dir)
        return

    if option < 1 or option > 10:
        print("Invalid choice!")
        return

    n = option

    filename = os.path.join(script_dir, f"list{n}.txt")

    max_num = 10 ** n
    fmt = f"{{:0{n}d}}\n"

    print("\nPress Enter for full range, or type anything for custom range:")
    custom = input().strip()

    if custom == "":
        start_num = 0
        end_num = max_num - 1
    else:
        while True:
            start_str = input(f"Enter start ({0:0{n}d}): ").strip()
            end_str = input(f"Enter end ({10**n-1:0{n}d}): ").strip()

            if not (start_str.isdigit() and end_str.isdigit()):
                print("Numbers only!")
                continue

            if len(start_str) != n or len(end_str) != n:
                print(f"Both numbers must have exactly {n} digits!")
                continue

            start_num = int(start_str)
            end_num = int(end_str)

            if start_num > end_num:
                print("Start must be <= End.")
                continue

            break

    total = end_num - start_num + 1

    print("\nGenerating...\n")

    with open(filename, "w", encoding="utf-8") as f:
        for index, number in enumerate(range(start_num, end_num + 1), 1):
            f.write(fmt.format(number))
            progress(index, total)

    print(f"\nDone!")
    print(f"Saved to:\n{filename}")


def generate_date_list(script_dir):
    while True:
        try:
            start_year = int(input("Enter start year: "))
            end_year = int(input("Enter end year: "))

            if start_year > end_year:
                print("Start year must be <= End year.")
                continue

            break

        except ValueError:
            print("Invalid year!")

    filename = os.path.join(
        script_dir,
        f"list_{start_year}_{end_year}.txt"
    )

    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    total = (end_date - start_date).days + 1

    current = start_date

    print("\nGenerating dates...\n")

    with open(filename, "w", encoding="utf-8") as f:
        for i in range(1, total + 1):
            f.write(current.strftime("%d%m%Y") + "\n")
            current += timedelta(days=1)
            progress(i, total)

    print(f"\nDone!")
    print(f"Saved to:\n{filename}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    generate_number_list(script_dir)


if __name__ == "__main__":
    main()