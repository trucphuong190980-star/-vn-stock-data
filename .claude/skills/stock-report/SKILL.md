---
name: stock-report
description: Bước report của /run (SCRIPT). Script kiểm picks.json theo luật của stock-picks, dựng reports/stock_report_{ngày}.html một trang, ghi run.json là succeeded.
---

# stock-report

| Ai | Lệnh | Ra |
|---|---|---|
| SCRIPT | `python3 .claude/skills/stock-report/scripts/build_report.py --run runs/{ngày}` | `reports/stock_report_{ngày}.html`, `run.json` = `succeeded`, `logs/last_analyzed.txt` |

Script chỉ cần thư viện chuẩn của Python (Windows gọi `python` thay cho `python3`). Số trong report lấy từ
`metrics.json`; chữ lấy từ `picks.json`. Claude không sửa file HTML.

## Khi script báo lỗi

Script thoát với mã 2 khi `picks.json` sai luật (thiếu mã, sai thứ tự, có con số phần trăm, lý do quá ngắn hoặc quá dài).
Nó in từng lỗi và ghi `run.json` là `failed`.

1. Sửa đúng chỗ script chỉ trong `picks.json`, theo luật của skill `stock-picks`.
2. Chạy lại lệnh trên. Tối đa 2 lần sửa.
3. Vẫn lỗi thì dừng, để nguyên `run.json` là `failed`. Email 20:00 sẽ báo "Lỗi".
