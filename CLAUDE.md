# VN Stock Daily Brief · AI system

Repo này là một AI system tối giản chạy theo lịch trên GitHub:

```text
18:00  GitHub Actions   fetch_stock.py        → data/stock_data.csv
19:00  Claude Routine   /run                  → runs/{ngày}/run.json + reports/stock_report_{ngày}.html
20:00  GitHub Actions   send_summary.py       → email (kết quả · cần xem · lỗi · im lặng)
```

Bản đồ đầy đủ ở `workflow.yaml`. Khi được gọi, bạn chỉ chạy lệnh `/run`.

## Luật engine

1. Chỉ làm các bước trong `workflow.yaml` có `runs_on: Claude Routine`, đúng thứ tự. Không thêm bước, không mở file ngoài
   danh sách `reads` của bước đó.
2. Số do script tính. Bạn không gõ con số mới vào report; bạn chỉ viết lý do cho các mã top trong `picks.json`, theo
   `.claude/skills/stock-picks/SKILL.md`.
3. Script nói dừng là dừng. `check_and_measure.py` trả `skipped`, `needs_review` hoặc `failed` thì không phân tích, chỉ
   commit `run.json` rồi push.
4. Mỗi lần chạy có đúng một `runs/{YYYY-MM-DD}/run.json`. Email đọc file này để biết gửi loại nào.
5. Không sửa `config.yaml`, `workflow.yaml`, `.github/workflows/` hay các script. Muốn đổi cách chạy là việc của người.
6. Trả lời ngắn: một dòng trạng thái và đường dẫn report. Không giải thích từng bước.

## Thư mục

```text
github_actions/                       ← gốc repo
├── .github/workflows/                ← lịch chạy: daily_fetch.yml, daily_email.yml
├── .claude/commands/run.md           ← lệnh /run
├── .claude/skills/                   ← 3 skill, mỗi bước một skill:
│   ├── stock-check/                  ←   check · SCRIPT kiểm dữ liệu, tính chỉ số
│   ├── stock-picks/                  ←   analyze · AI viết lý do
│   └── stock-report/                 ←   report · SCRIPT dựng report HTML
├── CLAUDE.md                         ← file này: luật engine
├── workflow.yaml                     ← các bước, ai làm, đọc gì, ghi gì, khi nào dừng
├── config.yaml                       ← mã, nguồn, top picks, ngưỡng dừng, chế độ email
├── fetch_stock.py · send_summary.py  ← script của GitHub Actions
├── data/stock_data.csv               ← do Actions ghi
├── runs/{ngày}/                      ← run.json · metrics.json · picks.json của từng lần chạy
├── reports/                          ← stock_report_{ngày}.html
└── logs/                             ← fetch.log · last_analyzed.txt
```
