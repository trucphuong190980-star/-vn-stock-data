# VN Stock Pipeline · Thực hành Buổi 10 trong Claude Code

Cuối buổi bạn có một repo GitHub tự chạy mỗi tối ngày làm việc. 18:00 lấy giá 10 mã cổ phiếu, 19:00 Claude phân tích và
dựng report, 20:00 gửi email. Máy bạn tắt vẫn chạy.

Bạn làm trong **tab Code của Claude Desktop**. Việc nào cần đăng nhập tài khoản (GitHub, Gmail) thì làm trên trình duyệt.
Mỗi bước ghi rõ ai làm: **BẠN** (trình duyệt hoặc app), **AI** (Claude trong tab Code), **SCRIPT** (code tự chạy).

| Cần có | Ghi chú |
|---|---|
| Claude Desktop, gói Pro trở lên | tab Code và Scheduled tasks có từ gói Pro |
| Tài khoản GitHub | đã dùng ở Buổi 6 |
| Gmail đã bật xác minh 2 bước | để tạo App Password gửi email |
| Thư mục `github_actions/` | trong bộ thực hành Buổi 10 |

---

## Hệ gồm những gì

```text
18:00  GitHub Actions   daily_fetch.yml   SCRIPT   fetch_stock.py lấy phần dữ liệu còn thiếu   → data/stock_data.csv
19:00  Claude           lệnh /run         gọi lần lượt 3 skill, rồi push lên repo:
                         stock-check       SCRIPT   kiểm dữ liệu, tính chỉ số                 → runs/{ngày}/run.json, metrics.json
                         stock-picks       AI       viết lý do cho các mã top                 → runs/{ngày}/picks.json
                         stock-report      SCRIPT   dựng report 1 trang                       → reports/stock_report_{ngày}.html
20:00  GitHub Actions   daily_email.yml   SCRIPT   send_summary.py đọc run.json, gửi 1 email → Kết quả · Cần xem · Lỗi · Im lặng
```

Ba mốc giờ không gọi thẳng nhau. Chúng nối qua file trong repo, và `runs/{ngày}/run.json` cho biết lần chạy hôm nay đang ở
đâu. Số do script tính; Claude chỉ viết phần lý do.

```text
github_actions/
├── .github/workflows/        ← lịch của GitHub Actions: daily_fetch.yml (18:00), daily_email.yml (20:00)
├── .claude/commands/run.md   ← lệnh /run: 4 bước, theo thứ tự
├── .claude/skills/           ← 3 skill, mỗi bước một skill: stock-check · stock-picks · stock-report
├── CLAUDE.md                 ← luật engine cho Claude
├── workflow.yaml             ← bản đồ: bước nào, ai làm, skill nào, đọc gì, ghi gì, khi nào dừng
├── config.yaml               ← mã cổ phiếu, nguồn dữ liệu, số mã top, ngưỡng dừng, chế độ email
├── fetch_stock.py            ← script lấy dữ liệu (GitHub Actions chạy)
└── send_summary.py           ← script gửi email (GitHub Actions chạy)
```

---

## Bước 1 · Mở thư mục trong tab Code

**BẠN:** mở Claude Desktop → tab **Code** → **New**. Hàng dưới ô prompt: để **This computer** (Claude chạy trên máy bạn),
bấm **Choose…** chọn thư mục `github_actions`, chế độ **Accept edits**. Gõ:

```text
Đọc CLAUDE.md và workflow.yaml rồi tóm tắt cho tôi: hệ có mấy bước, bước nào do script làm, bước nào do AI, mỗi bước
dùng skill nào, đọc file gì và ghi file gì. Chưa chạy gì cả.
```

Claude kể đủ 6 bước (fetch, check, analyze, report, publish, email) và 3 skill. Đọc kỹ chỗ "khi nào dừng": đó là lý do
email "Cần xem" tồn tại.

## Bước 2 · Tạo repo trống trên GitHub

**BẠN, trình duyệt:** vào github.com → **New**.

- **Repository name:** `vn-stock-data`
- **Visibility:** Private
- Không tick "Add a README"

Bấm **Create repository**, copy đường dẫn repo (dạng `https://github.com/{tên-bạn}/vn-stock-data.git`).

## Bước 3 · Đẩy code lên repo

**AI, tab Code.** Gõ:

```text
Đẩy toàn bộ thư mục này lên repo {đường dẫn repo vừa copy}, nhánh main. Nhớ đẩy cả hai thư mục .github và .claude.
Xong thì liệt kê các thư mục đã lên repo.
```

Claude chạy `git init`, commit, push. Bấm **Allow** khi Claude xin chạy lệnh `git`. Lần đầu push, một cửa sổ đăng nhập GitHub
có thể bật lên: đăng nhập là xong.

**BẠN kiểm:** mở repo trên trình duyệt, tab **Code** phải thấy cả `.github/` và `.claude/`. Thiếu `.claude/` thì lịch 19:00
không có lệnh `/run` để chạy.

## Bước 4 · Cho GitHub Actions quyền ghi

**BẠN, trình duyệt:** repo → **Settings** → **Actions** → **General** → **Workflow permissions** → chọn **Read and write
permissions** → **Save**.

Không có quyền này, bước lấy dữ liệu chạy được nhưng không commit được file CSV.

## Bước 5 · Lấy dữ liệu lần đầu

**BẠN bấm, SCRIPT chạy:** repo → tab **Actions** → **VN Stock Daily Fetch** → **Run workflow** → **Run workflow**.

Chờ khoảng 2 phút tới khi có dấu tích xanh. Tab **Code** có thêm `data/stock_data.csv`: lần đầu lấy 90 ngày gần nhất,
khoảng 600 dòng cho 10 mã. Từ hôm sau chỉ lấy phần còn thiếu.

## Bước 6 · Cho Claude vào repo

Lịch 19:00 chạy trên máy cloud của Anthropic. Máy đó cần quyền đọc và push vào repo private của bạn.

**BẠN, trình duyệt:** mở `https://github.com/apps/claude` → **Install** (hoặc **Configure** nếu đã cài) → chọn tài khoản →
**Only select repositories** → chọn `vn-stock-data` → **Save**.

Push đi qua kết nối GitHub này, nên không cần tạo token (PAT) hay dán mật khẩu vào đâu cả.

## Bước 7 · Tạo lịch 19:00 cho Claude

Tính năng này tên mới là **Scheduled task**, tên cũ là **Routine**. Tuỳ tài khoản mà giao diện là một trong hai kiểu
dưới; các ô cần điền giống nhau.

**BẠN, tab Code:**

1. Bấm **Scheduled** ở thanh bên trái (không thấy thì tìm trong menu **More**) → **New task**. Hiện menu **Create with
   Claude** / **Set up manually** thì chọn **Set up manually**. Hộp **New scheduled task** mở ra.
2. Thanh bên ghi **Routines** thay vì Scheduled: bấm **Routines** → **New routine** → chọn **Cloud**. Một trang form mở ra;
   model, repo và environment chọn ngay dưới ô Instructions.
3. Điền:

| Ô | Điền |
|---|---|
| Name | `VN Stock 19:00` |
| Prompt (giao diện cũ: Instructions) | hai dòng ở dưới |
| Model, chọn trong ô prompt | Haiku (không có thì chọn Sonnet). Số do script tính, Claude chỉ viết vài câu lý do nên model nhỏ là đủ |
| Trigger | Schedule → Daily → 19:00 (giờ máy bạn) |
| Repository | `vn-stock-data`. Hộp New scheduled task: nằm trong **Advanced settings** → tab **General**. Không chọn repo thì task chỉ là task chat, không chạy được `/run` |
| Cloud environment | Default (hiện ra sau khi chọn repo). **Only on this computer** để tắt |
| Connectors | gỡ hết, task này không cần. Hộp New scheduled task: tab **Connectors** trong Advanced settings |

Prompt:

```text
Chạy lệnh /run của repo này, làm đúng các bước trong .claude/commands/run.md và không làm thêm việc gì khác.
Push kết quả thẳng lên nhánh main, không tạo nhánh mới.
```

Bấm **Create**. Trang chi tiết của task mở ra.

Prompt chỉ có hai dòng vì mọi luật nằm trong repo: `CLAUDE.md`, `workflow.yaml`, lệnh `/run`, 3 skill. Muốn đổi
cách chạy thì sửa file trong repo, không sửa task.

Lịch đặt đúng giờ chẵn có thể bắt đầu trễ vài phút. Không sao: email 20:00 còn gần một tiếng đệm.

**Chỉ chạy thứ 2 đến thứ 6:** lịch Daily chạy cả thứ 7, chủ nhật. Hai ngày đó không có phiên mới nên lần chạy tự bỏ qua,
nhưng vẫn tốn một chút hạn mức. Muốn bỏ hẳn: trang task → menu cạnh tên → **Edit** → **Trigger** → **Custom** → nhập
`0 12 * * 1-5` → **Save changes**. Giờ trong ô này tính theo UTC: 12:00 UTC là 19:00 giờ Việt Nam. Ô có sẵn chữ
`CRON_TZ=…` ở đầu thì xoá cả cụm đó rồi nhập như trên.

## Bước 8 · Chạy thử ngay

**BẠN bấm, AI và SCRIPT chạy:** trên trang task, bấm **Run now**. Lần chạy hiện ở mục **History**: bấm vào để xem Claude làm
từng bước: chạy `stock-check`, viết `picks.json`, chạy `stock-report`, rồi push.

**BẠN kiểm** trên repo:

- `runs/{hôm nay}/run.json` có `"status": "succeeded"`.
- `reports/stock_report_{hôm nay}.html` đã có. Bấm vào file → **Download raw file** → mở bằng trình duyệt.

History không ghi **Error** chỉ có nghĩa là phiên chạy kết thúc bình thường. Kết quả thật nằm trong `run.json`.

Đã bấm **Run now** hôm nay thì lần chạy 19:00 tối nay sẽ tự bỏ qua, vì mỗi ngày chỉ có một report. Lịch chạy đều từ ngày
mai.

## Bước 9 · Nối email

**9a · BẠN tạo Gmail App Password:** vào `https://myaccount.google.com/apppasswords` → tạo password tên `vn-stock-github`
→ copy 16 ký tự. Không thấy trang này: tài khoản chưa bật xác minh 2 bước, hoặc là tài khoản Google Workspace bị quản trị
viên chặn.

**9b · BẠN thêm 3 Secrets:** repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Secret |
|---|---|
| `GMAIL_USER` | địa chỉ Gmail dùng để gửi |
| `GMAIL_APP_PASSWORD` | 16 ký tự vừa tạo |
| `EMAIL_TO` | email nhận. Nhiều người thì cách nhau bằng dấu phẩy |

**9c · BẠN bấm, SCRIPT gửi:** tab **Actions** → **VN Stock Daily Email** → **Run workflow**. Bước 8 đã chạy xong nên bạn
nhận email **Kết quả**, có report PDF đính kèm. Nhận email **Im lặng** nghĩa là email đã nối đúng, nhưng repo chưa có lần chạy
nào hôm nay: xem lại Bước 8.

Xong. Từ giờ hệ tự chạy:

| Giờ | Ai chạy | Việc |
|---|---|---|
| 18:00 thứ 2–6 | GitHub Actions | lấy phần dữ liệu còn thiếu |
| 19:00 thứ 2–6 | Claude, trên cloud | kiểm, tính số, viết lý do, dựng report, push |
| 20:00 thứ 2–6 | GitHub Actions | gửi đúng một email |

---

## Khi nhận email

| Email | Nghĩa | Làm gì |
|---|---|---|
| **Kết quả** | chạy trọn | đọc. Report đầy đủ nằm trong file PDF đính kèm |
| **Cần xem** | script thấy cờ nặng, dừng trước khi phân tích | xem mục dưới |
| **Lỗi** | một bước hỏng | email ghi bước nào và việc cần làm |
| **Im lặng** | tới 20:00 repo chưa có lần chạy hôm nay | mở task, xem History: task chưa chạy, hay chạy mà không push được |

**Khi nhận "Cần xem":**

1. Mở `data/stock_data.csv` trên GitHub, xem các mã email nêu.
2. Dữ liệu sai (nguồn lỗi): chạy lại **VN Stock Daily Fetch**, hoặc chờ hôm sau.
3. Dữ liệu đúng (ví dụ cổ phiếu chia tách): cho chạy tiếp. Tab **Code** → **New** → ô môi trường chọn môi trường cloud
   **Default** → chọn repo `vn-stock-data` → gõ:

```text
/run --accept
Push kết quả thẳng lên nhánh main, không tạo nhánh mới.
```

Report sẽ ghi rõ là đã chấp nhận cờ nặng. Muốn có email ngay thì chạy tay **VN Stock Daily Email**.

---

## Sửa hệ bằng Claude Code

Mọi thay đổi làm trong repo. Lần chạy sau tự dùng bản mới, không phải sửa task.

Mở lại thư mục `github_actions` trong tab Code (**This computer**). Mỗi ngày GitHub Actions và Claude đều commit lên repo,
nên luôn mở đầu bằng câu "kéo bản mới nhất về". Ví dụ:

```text
Kéo bản mới nhất từ GitHub về. Thêm mã ACB và CTG vào danh sách theo dõi trong config.yaml, rồi commit và push lên main.
```

```text
Kéo bản mới nhất từ GitHub về. Trong skill stock-picks, đổi luật để mỗi lý do tối đa 2 câu. Commit và push lên main.
```

```text
Kéo bản mới nhất từ GitHub về. Đổi giờ gửi email sang 20:30 giờ Việt Nam. Nhớ cron của GitHub tính theo giờ UTC.
Commit và push lên main.
```

| Muốn đổi | Sửa ở đâu |
|---|---|
| Thêm, bớt mã cổ phiếu | `config.yaml` → `tickers` |
| Số ngày lấy lần đầu | `config.yaml` → `fetch.lookback_days` |
| Tên nguồn in ở chân email | `config.yaml` → `fetch.source` (dữ liệu luôn lấy từ Yahoo Finance qua yfinance) |
| Số mã top | `config.yaml` → `report.top_picks` |
| Độ dài cửa sổ tính Return | `config.yaml` → `report.window_days` |
| Ngưỡng dừng | `config.yaml` → `checks` |
| Gửi cả khi lần chạy bị bỏ qua | `config.yaml` → `email.mode: every` |
| Giờ lấy dữ liệu, giờ gửi email | `cron` trong `daily_fetch.yml`, `daily_email.yml` (giờ UTC = giờ Việt Nam − 7) |
| Giờ Claude phân tích | trigger của task: Scheduled → mở task → menu cạnh tên → Edit |
| Cách viết lý do | `.claude/skills/stock-picks/SKILL.md` |

---

## Script tự dừng khi nào

Không cần Claude phán. `stock-check` dừng theo ngưỡng trong `config.yaml`:

| Gặp chuyện gì | `run.json` | Email 20:00 |
|---|---|---|
| Chưa có `data/stock_data.csv` | `failed` | Lỗi |
| Dữ liệu cũ hơn 3 ngày | `skipped` | không gửi |
| Ngày dữ liệu này đã phân tích (cuối tuần, ngày lễ) | `skipped` | không gửi |
| Thiếu hơn 2 mã, hoặc một mã đổi giá quá 15% trong 1 phiên | `needs_review` | Cần xem |
| Thiếu 1–2 mã, khối lượng phiên cuối bằng 0 | chạy tiếp, ghi chú | Kết quả kèm ghi chú |

---

## Khi gặp lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| Bước 3: Claude báo máy chưa có Git | Gõ "Cài Git cho máy này", bấm Allow, rồi gõ lại câu ở Bước 3 |
| Bước 5: Actions báo lỗi ở bước push | Chưa làm Bước 4 |
| Actions báo đỏ ở bước **Fetch stock data** | Cả 10 mã đều lỗi: Yahoo tạm chặn lượt gọi hoặc mất mạng. Chờ vài phút rồi bấm **Run workflow** lại |
| Bước 8: lần chạy báo không clone hoặc không push được repo | Claude GitHub App chưa được cấp quyền vào `vn-stock-data`: làm lại Bước 6 |
| History có warning "The last run…" | Làm theo đúng dòng warning. Thường chỉ cần bấm **Run now** lại |
| `run.json` là `skipped` | Bình thường vào cuối tuần, ngày lễ, hoặc hôm đó đã có report. Lý do ghi trong `steps[0].note` |
| Email **Lỗi** ở bước viết lý do | Claude viết `picks.json` sai luật quá 2 lần. Chi tiết trong `run.json`. Bấm **Run now** chạy lại |
| Không nhận email nào | Xem lần chạy **VN Stock Daily Email** trong tab Actions; kiểm tên 3 Secrets |
| Lịch GitHub Actions chạy trễ | Lúc GitHub đông, lịch có thể trễ vài phút tới vài chục phút. Các mốc cách nhau một tiếng là để đệm |
