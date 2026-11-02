---
description: Chạy AI system VN Stock Daily Brief một lần, theo workflow.yaml (stock-check → stock-picks → stock-report → push)
argument-hint: "[--accept] [--date YYYY-MM-DD]"
allowed-tools: Bash(python:*), Bash(python3:*), Bash(git:*), Read, Write
---

Chạy đúng 4 bước dưới đây, theo thứ tự. Mỗi bước 1–3 có một skill; đọc `SKILL.md` của skill đó trước khi làm. Không làm
thêm việc gì khác.

Lệnh Python: dùng `python3`; máy không có `python3` (Windows) thì dùng `python`. Script chỉ cần thư viện chuẩn.

1. **Kiểm dữ liệu và tính chỉ số · skill `stock-check` (SCRIPT).** Chạy:

   ```bash
   python3 .claude/skills/stock-check/scripts/check_and_measure.py $ARGUMENTS
   ```

   Dòng cuối là JSON có `status` và `run_dir`.
   - `status` là `ready`: sang bước 2.
   - `status` là `skipped`, `needs_review` hoặc `failed`: nhảy thẳng tới bước 4. Không phân tích, không dựng report.

2. **Viết lý do · skill `stock-picks` (AI).** Đọc `{run_dir}/metrics.json`. Viết `{run_dir}/picks.json` đúng khuôn và
   luật trong `.claude/skills/stock-picks/SKILL.md`: một câu tổng quan và lý do cho từng mã trong `top`. Không gõ con số mới.

3. **Dựng report · skill `stock-report` (SCRIPT).** Chạy:

   ```bash
   python3 .claude/skills/stock-report/scripts/build_report.py --run {run_dir}
   ```

   Script báo lỗi ở `picks.json` thì sửa đúng chỗ đó rồi chạy lại, tối đa 2 lần. Vẫn lỗi thì để nguyên và sang bước 4:
   `run.json` đã ghi `failed`.

4. **Đẩy lên repo (SCRIPT).** Đẩy thẳng lên nhánh `main`, không tạo nhánh mới. Chạy:

   ```bash
   git add runs reports logs
   git commit -m "run: {ngày trong run_dir} · {status}"
   git push origin HEAD:main
   ```

   Push bị từ chối vì `main` trên GitHub có commit mới hơn thì chạy `git pull --rebase origin main` rồi push lại.

Trả lời đúng một dòng: `status` cuối cùng trong `{run_dir}/run.json` và đường dẫn report nếu có.
