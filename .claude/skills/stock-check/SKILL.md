---
name: stock-check
description: Bước check của /run (SCRIPT). Script kiểm data/stock_data.csv theo luật dừng, tính chỉ số từng mã, ghi runs/{ngày}/run.json và metrics.json. Claude chỉ chạy script và đọc status.
---

# stock-check

| Ai | Lệnh | Ra |
|---|---|---|
| SCRIPT | `python3 .claude/skills/stock-check/scripts/check_and_measure.py [--accept] [--date YYYY-MM-DD]` | `runs/{ngày}/run.json`, `runs/{ngày}/metrics.json` |

Script chỉ cần thư viện chuẩn của Python (Windows gọi `python` thay cho `python3`). Dòng cuối in ra là JSON có `status`
và `run_dir`. Claude không tự tính hay sửa số trong `metrics.json`.

## Đọc `status`

| `status` | Nghĩa | Làm gì tiếp |
|---|---|---|
| `ready` | dữ liệu đạt, đã tính chỉ số | sang skill `stock-picks` |
| `skipped` | dữ liệu cũ, hoặc ngày dữ liệu này đã phân tích | không phân tích; push `run.json` |
| `needs_review` | cờ nặng: thiếu nhiều mã, hoặc một mã đổi giá bất thường | không phân tích; push `run.json`. Email 20:00 báo "Cần xem" |
| `failed` | không có `data/stock_data.csv`, hoặc không mã nào đủ dữ liệu | không phân tích; push `run.json` |

Ngưỡng dừng nằm trong `config.yaml › checks`. Claude không tự nới ngưỡng hay bỏ qua cờ nặng. Chỉ khi người đã kiểm dữ
liệu và gọi `/run --accept` thì script mới cho chạy tiếp.

Cờ nhẹ (thiếu 1–2 mã, khối lượng phiên cuối bằng 0) không làm dừng: script ghi vào `run.json › flags`, report và email
hiện thành ghi chú.
