import os

def main():
    print("Select the type of file to generate (number of digits from 1 to 10):")
    for i in range(1, 11):
        start = f"{0:0{i}d}"
        end = f"{10**i - 1:0{i}d}"
        print(f"{i}. {start}-{end}")
    option = input("Enter your choice (1-10): ").strip()

    if not option.isdigit() or not (1 <= int(option) <= 10):
        print("Invalid choice!")
        return

    n = int(option)

    # 🔥 Đảm bảo file luôn nằm cùng thư mục với script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, f'list{n}.txt')

    max_num = 10 ** n
    fmt = f'{{:0{n}d}}\n'

    print("Press Enter for full range, or type any key for custom range:")
    range_option = input().strip()

    if range_option == "":
        start_num = 0
        end_num = max_num - 1
    else:
        while True:
            start_str = input(f"Enter the start number (from {0:0{n}d}): ").strip()
            end_str = input(f"Enter the end number (up to {10**n - 1:0{n}d}): ").strip()
            if not (start_str.isdigit() and end_str.isdigit()):
                print("Invalid input! Numbers only. Please try again.")
                continue
            if not (len(start_str) == n and len(end_str) == n):
                print(f"Input must be exactly {n} digits! Please try again.")
                continue
            start_num = int(start_str)
            end_num = int(end_str)
            if not (0 <= start_num <= end_num < max_num):
                print("Invalid range! Please try again.")
                continue
            break

    with open(filename, 'w', encoding='utf-8') as f:
        for i in range(start_num, end_num + 1):
            f.write(fmt.format(i))
    print(f"File {filename} has been generated successfully.")

if __name__ == "__main__":
    main()
