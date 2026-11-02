"""
send_summary.py — bước "email" của workflow.yaml (SCRIPT, GitHub Actions 20:00)
--------------------------------------------------------------------------------
Đọc runs/{hôm nay}/run.json rồi chọn đúng một loại email:

    succeeded             → Kết quả   : tóm tắt, top kèm lý do, bảng 10 mã, đính kèm report PDF
    needs_review          → Cần xem   : lý do dừng, việc cần làm
    failed / running      → Lỗi       : bước hỏng, việc cần làm
    chưa có run.json      → Im lặng   : Routine 19:00 chưa chạy hoặc chưa push
    skipped               → chỉ gửi khi config.yaml › email.mode = every

Không tự tính lại số: mọi con số lấy từ runs/{ngày}/metrics.json.
Template là HTML email (bảng lồng nhau, style inline, rộng tối đa 600px) để Gmail web và app điện thoại hiển thị giống nhau.
Mỗi email có kèm bản text thuần cho ứng dụng mail không đọc HTML.
Report PDF in từ reports/stock_report_{ngày}.html bằng Chrome headless (máy ubuntu-latest của GitHub Actions có sẵn
google-chrome). Không in được thì đính kèm bản HTML và ghi cảnh báo vào log.

    python send_summary.py                  # gửi qua Gmail (GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_TO trong GitHub Secrets)
    python send_summary.py --dry-run        # không gửi, ghi logs/email_preview.html + in đường dẫn file PDF để xem trước
    python send_summary.py --date 2026-10-29
"""

import argparse
import html
import json
import os
import shutil
import smtplib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")   # console Windows (cp1252) không in được tiếng Việt

VN = timezone(timedelta(hours=7))
CFG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
MODE = CFG.get("email", {}).get("mode", "important")
SOURCE = CFG.get("fetch", {}).get("source", "Yahoo Finance")
TREND = {"up": "Tăng", "down": "Giảm", "flat": "Đi ngang"}
e = html.escape

# ---- giao diện -----------------------------------------------------------------------------------------------
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
INK, SUB, MUTED, LINE = "#1A1A1A", "#5A5F66", "#8A9099", "#E6E8EC"
PAGE, SOFT, TINT = "#F2F4F7", "#F6F8FB", "#EEF4FD"
BRAND, DEEP = "#024AD8", "#013BAC"
UP, DOWN, AXIS = "#0E8A5A", "#C8321F", "#C9CED6"          # cặp tăng/giảm đã qua kiểm màu (dataviz validator)
AMBER = "#B7791F"
PILL = {"result": ("Kết quả", "#E3F4EC", "#0B6B46"), "review": ("Cần xem", "#FFF1D6", "#8A5300"),
        "error": ("Lỗi", "#FDE5E1", "#A12A19"), "quiet": ("Im lặng", "#ECEEF2", "#4A4F57"),
        "skipped": ("Bỏ qua", "#ECEEF2", "#4A4F57")}
STEP = {"check": "Kiểm dữ liệu", "analyze": "Viết lý do", "report": "Dựng report"}
STEP_STATE = {"ok": ("xong", UP), "stop": ("dừng", AMBER), "failed": ("hỏng", DOWN),
              "pending": ("chưa xong", MUTED), "not_run": ("không chạy", AXIS)}


def st(size, weight=400, color=INK, lh=1.5, extra=""):
    return (f"font-family:{FONT};font-size:{size}px;font-weight:{weight};line-height:{lh};color:{color};"
            f"mso-line-height-rule:exactly;{extra}")


def vn_date(iso: str, short=False) -> str:
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}" if short else f"{d}/{m}/{y}"


def grid(inner: str, extra="") -> str:
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="{extra}">{inner}</table>'


def gap(h: int) -> str:
    return f'<div style="height:{h}px;line-height:{h}px;font-size:0">&nbsp;</div>'


def heading(text: str) -> str:
    return f'<div style="{st(15, 700)}">{e(text)}</div>{gap(10)}'


def box(inner: str, bg=SOFT, border=SOFT) -> str:
    return grid(f'<tr><td style="background:{bg};border:1px solid {border};border-radius:10px;padding:14px 16px">{inner}</td></tr>')


def bullets(items, color=INK) -> str:
    return "".join(f'<div style="{st(14, color=color, lh=1.55)}padding:3px 0">&bull;&nbsp; {e(x)}</div>' for x in items)


def circle(text, bg=BRAND, fg="#FFFFFF") -> str:
    return (f'<td width="26" valign="top" style="padding-top:1px"><div style="width:26px;height:26px;border-radius:13px;'
            f'background:{bg};text-align:center;{st(13, 700, fg, "26px")}">{e(str(text))}</div></td>')


def steps_strip(run) -> str:
    cells = []
    for s in run.get("steps", []):
        word, color = STEP_STATE.get(s["status"], (s["status"], MUTED))
        cells.append(f'<td valign="top" style="padding:0 8px 0 0">'
                     f'<span style="display:inline-block;width:8px;height:8px;border-radius:4px;background:{color}"></span>'
                     f'<span style="{st(12.5, 600)}">&nbsp; {STEP.get(s["step"], s["step"])}</span><br>'
                     f'<span style="{st(12, color=MUTED)}">{e(s["who"])} · {word}</span></td>')
    head = f'<div style="{st(12, 600, MUTED)}letter-spacing:.6px;text-transform:uppercase">Lần chạy {vn_date(run["run_id"])}</div>{gap(8)}'
    return head + grid(f"<tr>{''.join(cells)}</tr>")


def page(kind: str, title: str, sub: str, body: str, preheader: str) -> str:
    label, pbg, pfg = PILL[kind]
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only"><title>{e(title)}</title>
<style>@media only screen and (max-width:480px){{.px{{padding-left:18px!important;padding-right:18px!important}}.outer{{padding:12px 6px!important}}.hm{{display:none!important}}.kv{{font-size:17px!important}}.ttl{{font-size:21px!important}}}}</style></head>
<body style="margin:0;padding:0;background:{PAGE}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE}" style="background:{PAGE}"><tr><td align="center" class="outer" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#FFFFFF;border:1px solid {LINE};border-radius:14px;border-collapse:separate;overflow:hidden">
<tr><td bgcolor="{DEEP}" class="px" style="background:{DEEP};padding:22px 28px 24px;border-radius:14px 14px 0 0">
{grid(f'<tr><td style="{st(11, 700, "#BFD3FF", 1.2)}letter-spacing:1.4px">VN STOCK DAILY BRIEF</td>'
      f'<td align="right"><span style="display:inline-block;padding:4px 11px;border-radius:999px;background:{pbg};{st(12, 700, pfg, 1.3)}">{label}</span></td></tr>')}
<div class="ttl" style="{st(24, 700, "#FFFFFF", 1.25)}padding-top:12px">{e(title)}</div>
<div style="{st(13, 400, "#D6E2FF")}padding-top:4px">{e(sub)}</div>
</td></tr>
<tr><td class="px" style="padding:24px 28px 26px">{body}</td></tr>
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px"><tr>
<td align="center" style="padding:14px 28px 0;{st(12, color=MUTED)}">Gửi tự động lúc 20:00 bởi GitHub Actions · dữ liệu {e(SOURCE)} qua yfinance<br>
Báo cáo phục vụ học tập, không phải khuyến nghị đầu tư.</td></tr></table>
</td></tr></table>
</body></html>"""


# ---- bảng 10 mã có thanh Return hai chiều ---------------------------------------------------------------------
def return_bar(value: float, scale: float) -> str:
    pct = 0 if not scale else max(3, round(abs(value) / scale * 100)) if value else 0
    bar = (lambda color, radius, align: f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="{pct}%" align="{align}">'
           f'<tr><td height="8" bgcolor="{color}" style="background:{color};height:8px;border-radius:{radius};font-size:0;line-height:0">&nbsp;</td></tr></table>')
    left = bar(DOWN, "4px 0 0 4px", "right") if value < 0 and pct else "&nbsp;"
    right = bar(UP, "0 4px 4px 0", "left") if value > 0 and pct else "&nbsp;"
    return grid(f'<tr><td width="50%" align="right" style="font-size:0;line-height:0">{left}</td>'
                f'<td width="50%" align="left" style="border-left:1px solid {AXIS};font-size:0;line-height:0">{right}</td></tr>')


def ticker_table(m) -> str:
    rows = sorted(m["tickers"], key=lambda r: r.get("rank") or 999)
    scale = max((abs(r["return_pct"]) for r in rows), default=0)
    th = f"padding:0 6px 8px;border-bottom:1px solid {LINE};{st(11.5, 600, MUTED, 1.3)}"
    out = [f'<tr><th align="left" width="6%" style="{th}">#</th><th align="left" width="12%" style="{th}">Mã</th>'
           f'<th align="center" colspan="2" style="{th}">Return</th>'
           f'<th align="right" width="15%" style="{th}">Biến động</th><th align="left" width="17%" class="hm" style="{th}">Xu hướng</th></tr>']
    for r in rows:
        bg = TINT if r["group"] == "top" else "#FFFFFF"
        td = f"padding:9px 6px;border-bottom:1px solid {LINE};background:{bg};"
        out.append(f'<tr><td style="{td}{st(12.5, color=MUTED)}">{r.get("rank") or "–"}</td>'
                   f'<td style="{td}{st(13.5, 700)}">{e(r["ticker"])}</td>'
                   f'<td width="38%" style="{td}">{return_bar(r["return_pct"], scale)}</td>'
                   f'<td align="right" width="12%" style="{td}{st(13.5, 600)}white-space:nowrap">{r["return_pct"]:+.1f}%</td>'
                   f'<td align="right" style="{td}{st(13.5)}">{r["volatility_pct"]:.1f}%</td>'
                   f'<td class="hm" style="{td}{st(13.5, color=SUB)}white-space:nowrap">{TREND[r["trend"]]}</td></tr>')
    return grid("".join(out), "border-collapse:collapse")


# ---- 4 loại email ---------------------------------------------------------------------------------------------
def result_email(day, run, m, picks, attach):
    by = {r["ticker"]: r for r in m["tickers"]}
    mk = m["market"]
    tiles = [(mk["up"], "mã tăng"), (mk["down"], "mã giảm"), (mk["flat"], "mã đi ngang"),
             (f'{mk["avg_return_pct"]:+.1f}%', "Return bình quân")]
    kpi = "".join(f'<td width="25%" style="padding:{"0 4px 0 0" if i == 0 else "0 0 0 4px" if i == 3 else "0 4px"}">'
                  f'<div style="background:{SOFT};border-radius:10px;padding:12px 12px 11px">'
                  f'<div class="kv" style="{st(20, 700, lh=1.2)}">{v}</div><div style="{st(12, color=SUB, lh=1.4)}">{lab}</div></div></td>'
                  for i, (v, lab) in enumerate(tiles))

    cards = []
    for i, p in enumerate(picks["picks"], 1):
        r = by[p["ticker"]]
        stats = (f'Return <b style="color:{INK}">{r["return_pct"]:+.1f}%</b> &nbsp;·&nbsp; Biến động <b style="color:{INK}">'
                 f'{r["volatility_pct"]:.1f}%</b> &nbsp;·&nbsp; KL 7 phiên/TB <b style="color:{INK}">{r["volume_ratio"]:.2f}</b>')
        cards.append(grid(
            f'<tr><td style="border:1px solid {LINE};border-radius:12px;padding:14px 16px">'
            + grid(f'<tr>{circle(i)}<td style="padding-left:10px"><div style="{st(17, 700, lh=1.3)}">{e(p["ticker"])}</div>'
                   f'<div style="{st(12.5, color=SUB, lh=1.5)}">{stats}</div></td></tr>')
            + f'<div style="{st(14, lh=1.6)}padding-top:10px">{e(p["reason"])}</div></td></tr>') + gap(10))

    notes = [f["detail"] for f in run.get("flags", [])]
    body = (f'<div style="{st(15.5, lh=1.6)}">{e(picks["summary"])}</div>{gap(16)}'
            + grid(f"<tr>{kpi}</tr>") + gap(24)
            + heading(f'Top {len(picks["picks"])} hôm nay') + "".join(cards) + gap(14)
            + heading("10 mã theo dõi") + ticker_table(m)
            + f'<div style="{st(12, color=MUTED, lh=1.5)}padding-top:8px">Xếp hạng theo Return chia Biến động. Return tính trong '
              f'{m["window_days"]} ngày qua; Biến động là độ lệch chuẩn lợi suất ngày.</div>{gap(20)}'
            + (box(f'<div style="{st(13, 700)}">Ghi chú dữ liệu</div>{gap(4)}{bullets(notes, SUB)}') + gap(12) if notes else "")
            + (box(f'<div style="{st(13.5, lh=1.55)}">Report đầy đủ, có biểu đồ diễn biến giá: '
                   f'<b>{e(attach.name)}</b> trong file đính kèm.'
                   + ('' if attach.suffix == ".pdf" else ' Tải về rồi mở bằng trình duyệt.') + '</div>') + gap(20) if attach else "")
            + f'<div style="border-top:1px solid {LINE};padding-top:16px">{steps_strip(run)}</div>')
    top = ", ".join(m["top"])
    text = [f"Phiên {vn_date(m['data_date'])} · cửa sổ {m['window_days']} ngày · {mk['tickers']} mã", "", picks["summary"],
            f"{mk['up']} tăng · {mk['down']} giảm · {mk['flat']} đi ngang · Return bình quân {mk['avg_return_pct']:+.1f}%", "",
            f"TOP {len(picks['picks'])} HÔM NAY"]
    for i, p in enumerate(picks["picks"], 1):
        r = by[p["ticker"]]
        text += [f"{i}. {p['ticker']} · Return {r['return_pct']:+.1f}% · Biến động {r['volatility_pct']:.1f}% · "
                 f"KL 7 phiên/TB {r['volume_ratio']:.2f}", f"   {p['reason']}"]
    text += ["", "10 MÃ THEO DÕI (xếp theo Return chia Biến động)"]
    text += [f"{r.get('rank') or '-':>2}  {r['ticker']:<4} {r['return_pct']:+6.1f}%  {r['volatility_pct']:4.1f}%  {TREND[r['trend']]}"
             for r in sorted(m["tickers"], key=lambda r: r.get("rank") or 999)]
    text += [f"Ghi chú: {x}" for x in notes]
    text += ["", f"Report đầy đủ: file đính kèm {attach.name}" if attach else "", "Không phải khuyến nghị đầu tư."]
    subject = f"[VN Stock] {vn_date(m['data_date'], True)} · Kết quả · Top {top}"
    return subject, page("result", f"Phiên {vn_date(m['data_date'])}",
                         f"Cửa sổ {m['window_days']} ngày · {vn_date(m['window_start'], True)} → {vn_date(m['data_date'], True)} · "
                         f"{mk['tickers']} mã", body, picks["summary"]), "\n".join(text)


def todo(items) -> str:
    rows = "".join(f'<tr>{circle(i, "#E3E7EE", INK)}<td style="padding:2px 0 12px 10px;{st(14, lh=1.55)}">{x}</td></tr>'
                   for i, x in enumerate(items, 1))
    return heading("Việc cần làm") + grid(rows)


def review_email(day, run):
    hard = [f["detail"] for f in run["flags"] if f["level"] == "hard"]
    soft = [f["detail"] for f in run["flags"] if f["level"] == "soft"]
    body = (f'<div style="{st(15.5, lh=1.6)}">Lần chạy 19:00 dừng ở bước kiểm dữ liệu, chưa phân tích và chưa có report. '
            f'Script thấy:</div>{gap(12)}'
            + box(bullets(hard), "#FFF8EB", "#F5DFB0") + gap(22)
            + todo(["Mở <code>data/stock_data.csv</code> trên repo, xem các mã ở trên.",
                    "Dữ liệu sai: vào tab <b>Actions</b>, chạy lại <b>VN Stock Daily Fetch</b>.",
                    "Dữ liệu đúng: tab <b>Code</b> → phiên mới, môi trường cloud <b>Default</b>, repo này → gõ "
                    "<code>/run --accept</code>."])
            + (gap(8) + box(f'<div style="{st(13, 700)}">Ghi chú thêm</div>{gap(4)}{bullets(soft, SUB)}') if soft else "")
            + gap(20) + f'<div style="border-top:1px solid {LINE};padding-top:16px">{steps_strip(run)}</div>')
    sub = f"Dữ liệu phiên {vn_date(run['data_date'])}" if run.get("data_date") else "Chưa phân tích"
    first = next(f for f in run["flags"] if f["level"] == "hard")
    why = first["detail"].split(":")[0] + (" đổi giá bất thường" if first["code"] == "big_move" else "")
    why += f" (+{len(hard) - 1} cờ)" if len(hard) > 1 else ""
    return (f"[VN Stock] {vn_date(day, True)} · Cần xem: {why}",
            page("review", f"Lần chạy {vn_date(day, True)} đang chờ bạn kiểm", sub + " · dừng trước khi phân tích", body, hard[0]))


def error_email(day, run):
    bad = next((s for s in run["steps"] if s["status"] in ("failed", "pending")), run["steps"][0])
    why = bad.get("note") or "lần chạy dừng giữa chừng, chưa ghi kết quả"
    fix = {"check": ["Vào tab <b>Actions</b>, xem lần chạy 18:00 của <b>VN Stock Daily Fetch</b>.",
                     "Sửa xong, chạy lại workflow đó, rồi mở Routine bấm <b>Run now</b>."],
           "analyze": ["Mở <code>runs/{d}/run.json</code> xem luật nào bị vi phạm.".format(d=e(day)),
                       "Mở Routine, bấm <b>Run now</b>."],
           "report": ["Mở Routine, xem lần chạy trong <b>History</b> để thấy lỗi của <code>build_report.py</code>.",
                      "Sửa xong, bấm <b>Run now</b>."]}
    steps = fix.get(bad["step"], fix["report"]) if bad["status"] == "failed" else \
        ["Routine dừng giữa chừng: mở lần chạy trong <b>History</b> xem dừng ở đâu.", "Mở Routine, bấm <b>Run now</b>."]
    body = (f'<div style="{st(15.5, lh=1.6)}">Bước <b>{STEP.get(bad["step"], bad["step"])}</b> ({e(bad["who"])}) không xong:</div>{gap(12)}'
            + box(f'<div style="{st(14, lh=1.55)}">{e(why)}</div>', "#FDF1EF", "#F3C9C2") + gap(22)
            + todo(steps) + gap(8)
            + f'<div style="border-top:1px solid {LINE};padding-top:16px">{steps_strip(run)}</div>')
    return (f"[VN Stock] {vn_date(day, True)} · Lỗi ở bước {STEP.get(bad['step'], bad['step']).lower()}",
            page("error", f"Lần chạy {vn_date(day, True)} bị lỗi", f"Hỏng ở bước {STEP.get(bad['step'], bad['step']).lower()}", body, why))


def silence_email(day):
    body = (f'<div style="{st(15.5, lh=1.6)}">Tới 20:00 trên repo vẫn chưa có <code>runs/{e(day)}/run.json</code>.</div>{gap(18)}'
            + todo(["Mở Routine, xem <b>History</b> lúc 19:00: Routine chưa chạy, hay chạy xong mà không push được.",
                    "Không push được thường do Claude GitHub App chưa có quyền vào repo: mở github.com/apps/claude → "
                    "<b>Configure</b>, chọn lại repo này.",
                    "Sửa xong, bấm <b>Run now</b>. Email không tự gửi lại; xem kết quả trong <code>reports/</code>."]))
    return (f"[VN Stock] {vn_date(day, True)} · Im lặng: chưa có lần chạy nào hôm nay",
            page("quiet", "Không thấy lần chạy hôm nay", f"Ngày {vn_date(day)} · Routine 19:00 chưa để lại kết quả", body,
                 "Routine 19:00 chưa chạy hoặc chưa push"))


def skipped_email(day, run):
    note = run["steps"][0].get("note", "")
    body = (f'<div style="{st(15.5, lh=1.6)}">{e(note)}</div>{gap(20)}'
            + f'<div style="border-top:1px solid {LINE};padding-top:16px">{steps_strip(run)}</div>')
    return f"[VN Stock] {vn_date(day, True)} · Bỏ qua", page("skipped", "Hôm nay không có report mới", f"Ngày {vn_date(day)}", body, note)


def plain_text(subject: str, body_html: str) -> str:
    """Bản text thuần đi kèm, cho ứng dụng mail không hiển thị HTML."""
    import re
    t = re.sub(r"<(style|title)[^>]*>.*?</\1>", "", body_html, flags=re.S)
    t = re.sub(r"<div style=\"display:none[^\"]*\">.*?</div>", "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>|</(div|tr|p|h\d)>", "\n", t)
    t = re.sub(r"</t[dh]>", "  ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    lines = [" ".join(x.split()) for x in t.splitlines()]
    return subject + "\n\n" + "\n".join(x for x in lines if x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    day = a.date or datetime.now(VN).date().isoformat()
    run_dir = Path("runs") / day
    run = load(run_dir / "run.json")
    attach, text = None, None

    if run is None:
        subject, body = silence_email(day)
    elif run["status"] == "succeeded":
        m, picks = load(run_dir / "metrics.json"), load(run_dir / "picks.json")
        report = Path(run["outputs"][0]) if run.get("outputs") else None
        attach = (report_pdf(report) or report) if report and report.exists() else None
        if attach is not None and attach.suffix != ".pdf":
            print(f"CẢNH BÁO: không in được PDF (không thấy Chrome) → đính kèm bản HTML {attach.name}")
        subject, body, text = result_email(day, run, m, picks, attach)
    elif run["status"] == "needs_review":
        subject, body = review_email(day, run)
    elif run["status"] in ("failed", "running"):
        subject, body = error_email(day, run)
    elif run["status"] == "skipped" and MODE == "every":
        subject, body = skipped_email(day, run)
    else:
        print(f"Lần chạy {day}: {run['status']} · chế độ email '{MODE}' → không gửi.")
        return 0

    if a.dry_run:
        out = Path("logs") / "email_preview.html"
        out.parent.mkdir(exist_ok=True)
        meta = (f'<div style="background:#1A1A1A;color:#FFFFFF;{st(12.5, color="#FFFFFF")}padding:10px 16px">'
                f'<b>Subject:</b> {e(subject)} &nbsp;·&nbsp; <b>Đính kèm:</b> {e(attach.name if attach else "—")}</div>')
        out.write_text(body.replace(f'<body style="margin:0;padding:0;background:{PAGE}">',
                                    f'<body style="margin:0;padding:0;background:{PAGE}">{meta}', 1), encoding="utf-8")
        print(f"[dry-run] {subject} → {out}" + (f"\n[dry-run] đính kèm: {attach}" if attach else ""))
        return 0

    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("EMAIL_TO") or user
    msg = MIMEMultipart("mixed")
    msg["Subject"], msg["From"], msg["To"] = subject, f"VN Stock Daily Brief <{user}>", to
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text or plain_text(subject, body), "plain", "utf-8"))
    alt.attach(MIMEText(body, "html", "utf-8"))
    msg.attach(alt)
    if attach and attach.exists():
        part = MIMEApplication(attach.read_bytes(), "pdf" if attach.suffix == ".pdf" else "octet-stream", Name=attach.name)
        part["Content-Disposition"] = f'attachment; filename="{attach.name}"'
        msg.attach(part)
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
    print(f"Đã gửi: {subject} → {to}")
    return 0


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def report_pdf(src: Path):
    """In report HTML ra PDF A4 bằng Chrome headless, ghi vào thư mục tạm (không lẫn vào repo). Không in được → None."""
    names = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")
    win = (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    exe = next((p for p in map(shutil.which, names) if p), None) or next((p for p in win if Path(p).exists()), None)
    if not exe:
        return None
    out = Path(tempfile.gettempdir()) / src.with_suffix(".pdf").name
    out.unlink(missing_ok=True)
    try:
        subprocess.run([exe, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", src.resolve().as_uri()], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out if out.exists() and out.stat().st_size > 0 else None


if __name__ == "__main__":
    sys.exit(main())
