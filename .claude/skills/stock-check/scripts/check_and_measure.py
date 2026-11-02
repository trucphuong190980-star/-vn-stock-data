"""check_and_measure.py — bước "check" của workflow.yaml (SCRIPT).

Kiểm dữ liệu theo luật dừng trong config.yaml, tính chỉ số cho từng mã, ghi:
    runs/{ngày}/metrics.json   chỉ số + chuỗi giá chuẩn hoá cho biểu đồ
    runs/{ngày}/run.json       trạng thái lần chạy, các cờ
Dòng cuối in ra là JSON: {"status": ready | skipped | needs_review | failed, "run_dir": ..., ...}

    python .claude/skills/stock-check/scripts/check_and_measure.py [--accept] [--date YYYY-MM-DD] [--root .]

--accept  chạy tiếp dù có cờ nặng (sau khi người đã kiểm). Chỉ dùng thư viện chuẩn; có pyyaml thì dùng, không có thì
          tự đọc config.yaml (máy cloud của Claude Routine có thể chưa cài pyyaml).
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")   # console Windows (cp1252) không in được tiếng Việt

VN = timezone(timedelta(hours=7))          # Việt Nam không đổi giờ theo mùa



def load_config(path: Path) -> dict:
    """Đọc config.yaml. Có pyyaml thì dùng; không có thì đọc tập con YAML mà config.yaml dùng:
    khoá lồng theo thụt lề, danh sách "- giá trị", số, chuỗi, chú thích sau #."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass

    def scalar(v):
        v = v.strip().strip('"').strip("'")
        for cast in (int, float):
            try:
                return cast(v)
            except ValueError:
                pass
        return v

    root = {}
    stack = [(-1, root)]                       # (thụt lề, container)
    lines = [l.split(" #")[0].rstrip() for l in text.splitlines()]
    lines = [l for l in lines if l.strip() and not l.lstrip().startswith("#")]
    for i, line in enumerate(lines):
        ind = len(line) - len(line.lstrip())
        item = line.strip()
        while stack[-1][0] >= ind:
            stack.pop()
        parent = stack[-1][1]
        if item.startswith("- "):
            parent.append(scalar(item[2:]))
            continue
        key, _, val = item.partition(":")
        if val.strip():
            parent[key.strip()] = scalar(val)
        else:                                  # khoá mở khối: danh sách nếu dòng sau là "- ..."
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            child = [] if nxt.startswith("- ") else {}
            parent[key.strip()] = child
            stack.append((ind, child))
    return root

def now_vn() -> datetime:
    return datetime.now(VN).replace(microsecond=0)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_rows(path: Path) -> dict:
    """{ticker: [(date, close, volume), ...]} — bỏ dòng trùng ngày (giữ dòng sau), sắp theo ngày."""
    by = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                d = r["Date"][:10]
                close = float(r["Close"])
                vol = float(r["Volume"]) if r.get("Volume") not in (None, "") else 0.0
            except (KeyError, ValueError):
                continue
            by.setdefault(r["Ticker"].strip(), {})[d] = (close, vol)
    return {t: sorted((d, c, v) for d, (c, v) in rows.items()) for t, rows in by.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--date", help="ngày chạy YYYY-MM-DD, mặc định hôm nay giờ Việt Nam")
    ap.add_argument("--accept", action="store_true", help="chạy tiếp dù có cờ nặng")
    a = ap.parse_args()

    root = Path(a.root)
    cfg = load_config(root / "config.yaml")
    tickers = cfg["tickers"]
    rep, chk = cfg.get("report", {}), cfg.get("checks", {})
    top_n = int(rep.get("top_picks", 3))
    window = int(rep.get("window_days", 30))
    run_day = date.fromisoformat(a.date) if a.date else now_vn().date()
    run_id = run_day.isoformat()
    run_dir = root / "runs" / run_id
    run_path = run_dir / "run.json"
    started = now_vn().isoformat()

    def finish(status, check_status, note, flags=(), data_date=None, extra=None):
        run = {
            "run_id": run_id, "workflow": "vn-stock-daily-brief", "status": "running" if status == "ready" else status,
            "data_date": data_date, "started_at": started, "updated_at": now_vn().isoformat(), "accepted": a.accept,
            "steps": [
                {"step": "check", "who": "SCRIPT", "status": check_status, "note": note},
                {"step": "analyze", "who": "AI", "status": "pending" if status == "ready" else "not_run"},
                {"step": "report", "who": "SCRIPT", "status": "pending" if status == "ready" else "not_run"},
            ],
            "flags": list(flags), "outputs": [],
        }
        write_json(run_path, run)
        out = {"status": status, "run_dir": run_dir.as_posix(), "data_date": data_date, "note": note,
               "flags": [f["level"] + ": " + f["detail"] for f in flags]}
        out.update(extra or {})
        print(json.dumps(out, ensure_ascii=False))
        return 0

    # Lần chạy hôm nay đã xong → không ghi đè (chạy tay lần hai trong ngày không làm mất kết quả cho email 20:00)
    if run_path.exists():
        prev = json.loads(run_path.read_text(encoding="utf-8"))
        if prev.get("status") == "succeeded" and not a.accept:
            print(json.dumps({"status": "skipped", "run_dir": run_dir.as_posix(), "data_date": prev.get("data_date"),
                              "note": "Hôm nay đã có báo cáo; giữ nguyên run.json."}, ensure_ascii=False))
            return 0

    data_file = root / "data" / "stock_data.csv"
    if not data_file.exists():
        return finish("failed", "failed", "Không có data/stock_data.csv: bước lấy dữ liệu trên GitHub Actions chưa chạy hoặc lỗi.")

    rows = read_rows(data_file)
    all_dates = sorted({d for r in rows.values() for d, _, _ in r})
    if not all_dates:
        return finish("failed", "failed", "data/stock_data.csv không có dòng hợp lệ.")
    data_date = all_dates[-1]
    age = (run_day - date.fromisoformat(data_date)).days
    if age > int(chk.get("max_data_age_days", 3)):
        return finish("skipped", "stop", f"Dữ liệu cũ: ngày mới nhất {data_date}, cách hôm nay {age} ngày. Kiểm bước lấy dữ liệu.",
                      data_date=data_date)

    last_file = root / "logs" / "last_analyzed.txt"
    last = last_file.read_text(encoding="utf-8").strip() if last_file.exists() else ""
    if last == data_date and not a.accept:
        return finish("skipped", "stop", f"Ngày dữ liệu {data_date} đã phân tích rồi (ngày nghỉ hoặc chưa có phiên mới).",
                      data_date=data_date)

    # ── chỉ số từng mã ──────────────────────────────────────────────────────────────────────────────
    start = (date.fromisoformat(data_date) - timedelta(days=window)).isoformat()
    flags, metrics = [], []
    missing = [t for t in tickers if not rows.get(t) or rows[t][-1][0] != data_date]
    limit = float(chk.get("max_daily_move_pct", 15))
    for t in tickers:
        win = [r for r in rows.get(t, []) if r[0] >= start]
        if len(win) < 2:
            flags.append({"level": "soft", "code": "short_history", "detail": f"{t}: chưa đủ dữ liệu trong cửa sổ, không xếp hạng"})
            continue
        closes = [c for _, c, _ in win]
        rets = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(1, len(closes))]
        ret = (closes[-1] / closes[0] - 1) * 100
        vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
        vols = [v for _, _, v in win]
        recent = vols[-7:]
        vratio = (sum(recent) / len(recent)) / (sum(vols) / len(vols)) if sum(vols) else 0.0
        # phiên mới kể từ lần phân tích trước (hoặc phiên cuối) mà đổi giá quá ngưỡng → cờ nặng
        for i in range(1, len(win)):
            if win[i][0] > (last or win[-2][0]) and abs(rets[i - 1]) > limit:
                flags.append({"level": "hard", "code": "big_move",
                              "detail": f"{t}: đổi giá {rets[i - 1]:+.1f}% phiên {win[i][0]}, vượt ngưỡng {limit:g}% (lỗi nguồn hoặc chia tách?)"})
        if win[-1][0] == data_date and win[-1][2] == 0:
            flags.append({"level": "soft", "code": "zero_volume", "detail": f"{t}: khối lượng phiên {data_date} bằng 0"})
        metrics.append({
            "ticker": t, "close": closes[-1], "last_date": win[-1][0], "sessions": len(win),
            "return_pct": round(ret, 2), "volatility_pct": round(vol, 2),
            "trend": "up" if ret > 3 else ("down" if ret < -3 else "flat"),
            "volume_ratio": round(vratio, 2), "score": round(ret / vol, 3) if vol > 0 else 0.0,
        })

    max_missing = int(chk.get("max_missing_tickers", 2))
    if len(missing) > max_missing:
        flags.append({"level": "hard", "code": "missing_tickers",
                      "detail": f"Thiếu {len(missing)} mã ở phiên {data_date}: {', '.join(missing)} (ngưỡng {max_missing})"})
    else:
        for t in missing:
            flags.append({"level": "soft", "code": "missing_ticker", "detail": f"{t}: không có dữ liệu phiên {data_date}"})

    metrics.sort(key=lambda m: m["score"], reverse=True)
    n = len(metrics)
    for i, m in enumerate(metrics, 1):
        m["rank"] = i
        m["group"] = "top" if i <= top_n else ("avoid" if n >= 2 * top_n + 1 and i > n - top_n else "watch")

    dates = [d for d in all_dates if d >= start]
    series = {}
    for t in [m["ticker"] for m in metrics]:
        closes = {d: c for d, c, _ in rows[t] if d >= start}
        base = closes[min(closes)]
        series[t] = [round(closes[d] / base * 100, 2) if d in closes else None for d in dates]

    up = sum(m["trend"] == "up" for m in metrics)
    down = sum(m["trend"] == "down" for m in metrics)
    write_json(run_dir / "metrics.json", {
        "run_id": run_id, "data_date": data_date, "window_days": window, "window_start": start,
        "language": rep.get("language", "vi"), "top_picks": top_n,
        "top": [m["ticker"] for m in metrics if m["group"] == "top"],
        "avoid": [m["ticker"] for m in metrics if m["group"] == "avoid"],
        "market": {"tickers": n, "up": up, "down": down, "flat": n - up - down,
                   "avg_return_pct": round(sum(m["return_pct"] for m in metrics) / n, 2) if n else 0.0},
        "tickers": metrics, "series": {"dates": dates, "values": series},
    })

    hard = [f for f in flags if f["level"] == "hard"]
    if n == 0:
        return finish("failed", "failed", "Không mã nào đủ dữ liệu để tính chỉ số.", flags, data_date)
    if hard and not a.accept:
        return finish("needs_review", "stop", "Có cờ nặng: dừng trước khi phân tích, chờ người kiểm.", flags, data_date)
    note = f"{n}/{len(tickers)} mã đủ dữ liệu, phiên {data_date}" + (" · đã chấp nhận cờ nặng" if hard else "")
    return finish("ready", "ok", note, flags, data_date,
                  {"top": [m["ticker"] for m in metrics if m["group"] == "top"]})


if __name__ == "__main__":
    sys.exit(main())
