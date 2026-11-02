"""
fetch_stock.py — bước "fetch" của workflow.yaml (SCRIPT, GitHub Actions 18:00)
--------------------------------------------------------------------------------
Kéo data OHLCV của các mã trong config.yaml từ Yahoo Finance (thư viện yfinance), lưu vào CSV.
Gói vnstock trên PyPI đã bị cách ly, nên nguồn đổi sang Yahoo: không cần key, cài thẳng từ PyPI.

Logic:
- Lần đầu: fetch config.yaml › fetch.lookback_days ngày gần nhất
- Lần sau: chỉ fetch ngày còn thiếu, append vào file (chạy lại không tạo dòng trùng)
- Giá Yahoo tính bằng đồng → chia 1000 về nghìn đồng như trước, để check và report đọc đúng
- Bỏ dòng khối lượng 0: Yahoo điền cả ngày nghỉ lễ bằng giá cũ
- Cả 10 mã đều lỗi → thoát mã lỗi để Actions báo đỏ. Không có phiên (cuối tuần, nghỉ lễ) không tính là lỗi.

Output: data/stock_data.csv
Cột: Date, Ticker, Open, High, Low, Close, Volume
"""

import csv
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")   # console Windows (cp1252) không in được tiếng Việt

# ─── ĐỌC CONFIG ──────────────────────────────────────────────────────────────

_config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
TICKERS = _config["tickers"]
LOOKBACK_DAYS = _config["fetch"]["lookback_days"]
OUTPUT_FILE = Path("data/stock_data.csv")
LOG_FILE = Path("logs/fetch.log")
HEADER = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]

# ─── LOGGING ─────────────────────────────────────────────────────────────────

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),                              # GitHub Actions log
        logging.FileHandler(LOG_FILE, encoding="utf-8"),                # file log trong repo
    ],
)
log = logging.getLogger(__name__)

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_latest_date_in_csv() -> str | None:
    if not OUTPUT_FILE.exists():
        return None
    latest = None
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get("Date", "")[:10]
            if val and (latest is None or val > latest):
                latest = val
    return latest


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def fetch_and_append():
    try:
        import yfinance as yf
        from yfinance.exceptions import YFPricesMissingError
    except Exception as e:
        log.error(f"Lỗi import yfinance: {type(e).__name__}: {e}")
        sys.exit(1)

    today = date.today()
    yesterday = today - timedelta(days=1)

    # ── Xác định khoảng ngày cần fetch ───────────────────────────────────────
    latest_str = get_latest_date_in_csv()

    if latest_str is None:
        fetch_start = today - timedelta(days=LOOKBACK_DAYS)
        log.info(f"Chưa có data → fetch {LOOKBACK_DAYS} ngày: {fetch_start} → {yesterday}")
    else:
        fetch_start = date.fromisoformat(latest_str) + timedelta(days=1)
        if fetch_start > yesterday:
            log.info(f"Data đã up-to-date (latest: {latest_str}). Không có gì để fetch.")
            sys.exit(0)
        log.info(f"Fetch từ {fetch_start} → {yesterday}")

    start_str = fetch_start.strftime("%Y-%m-%d")
    end_str = yesterday.strftime("%Y-%m-%d")
    end_excl = (yesterday + timedelta(days=1)).strftime("%Y-%m-%d")   # yfinance không tính ngày end

    # ── Tạo thư mục data nếu chưa có ─────────────────────────────────────────
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_exists = OUTPUT_FILE.exists()

    # ── Fetch và append ───────────────────────────────────────────────────────
    success_count = 0
    error_count = 0
    total_rows = 0

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(HEADER)

        for i, ticker in enumerate(TICKERS):
            if i:
                time.sleep(1)   # nghỉ giữa các mã để Yahoo không chặn vì gọi dồn
            try:
                # Mã HOSE trên Yahoo có đuôi .VN. raise_errors=True: mất mạng, bị chặn thì ném lỗi thật,
                # thay vì để yfinance gộp chung với "không có phiên" rồi trả bảng rỗng
                try:
                    df = yf.Ticker(f"{ticker}.VN").history(start=start_str, end=end_excl, interval="1d",
                                                           raise_errors=True)
                except YFPricesMissingError:
                    df = None   # khoảng ngày không có phiên (cuối tuần, nghỉ lễ): không tính là lỗi

                if df is None or df.empty:
                    log.warning(f"{ticker}: Không có data ({start_str} → {end_str})")
                    continue

                df.index = df.index.strftime("%Y-%m-%d")
                df_filtered = df[(df.index >= start_str) & (df.index <= end_str)]

                # Yahoo điền ngày nghỉ lễ bằng giá cũ, khối lượng 0 → bỏ, nếu không chỉ số tính ra sẽ sai
                zero_days = df_filtered.index[df_filtered["Volume"] == 0].tolist()
                if zero_days:
                    log.warning(f"{ticker}: bỏ {len(zero_days)} ngày khối lượng 0: {', '.join(zero_days)}")
                    df_filtered = df_filtered[df_filtered["Volume"] > 0]

                if df_filtered.empty:
                    log.warning(f"{ticker}: Không có data trong khoảng này")
                    continue

                for day, row in df_filtered.iterrows():
                    writer.writerow([
                        day,
                        ticker,
                        round(row["Open"] / 1000, 2),    # đồng → nghìn đồng
                        round(row["High"] / 1000, 2),
                        round(row["Low"] / 1000, 2),
                        round(row["Close"] / 1000, 2),
                        int(row["Volume"]),
                    ])
                    total_rows += 1

                log.info(f"{ticker}: ✓ {len(df_filtered)} dòng")
                success_count += 1

            except Exception as e:
                log.error(f"{ticker}: Lỗi — {type(e).__name__}: {e}")
                error_count += 1

    log.info(f"=== Xong: {success_count}/{len(TICKERS)} tickers | {total_rows} dòng mới ===")

    if error_count == len(TICKERS):
        log.error(f"Cả {len(TICKERS)} mã đều lỗi (Yahoo chặn hoặc mất mạng) → báo đỏ trên Actions")
        sys.exit(1)


if __name__ == "__main__":
    fetch_and_append()
