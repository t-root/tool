# tool

Clone chỉ 1 tool (sparse checkout)

Ví dụ chỉ lấy `gamepad.py`:

```
git clone --filter=blob:none --no-checkout https://github.com/t-root/tool.git
cd tool
git sparse-checkout init --no-cone
git sparse-checkout set gamepad.py
git checkout main
```

Muốn lấy thêm tool khác thì chạy:

```
git sparse-checkout add keylogger.py
```

> Lưu ý: mặc định `git sparse-checkout` dùng "cone mode", chế độ này luôn giữ lại toàn bộ file nằm ở thư mục gốc (root) của repo, nên nếu không thêm `--no-cone` thì lệnh `set gamepad.py` vẫn kéo về tất cả file ở root. Thêm `git sparse-checkout init --no-cone` để sparse-checkout lọc đúng theo từng file.
