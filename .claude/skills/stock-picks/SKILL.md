---
name: stock-picks
description: Bước analyze của /run (AI). Claude đọc runs/{ngày}/metrics.json và viết picks.json, gồm một câu tổng quan và lý do cho các mã top. Không gõ con số mới.
---

# stock-picks

| Ai | Việc | Ra |
|---|---|---|
| AI | đọc `runs/{ngày}/metrics.json`, viết lý do | `runs/{ngày}/picks.json` |

Chỉ làm bước này khi `stock-check` trả `status` là `ready`.

## Đọc `metrics.json`

- `top`: danh sách mã cần viết lý do, đúng thứ tự.
- `tickers[]`: mỗi mã có `return_pct` (Return trong cửa sổ), `volatility_pct` (độ lệch chuẩn lợi suất ngày),
  `trend` (`up` · `flat` · `down`), `volume_ratio` (khối lượng 7 phiên cuối so với trung bình cửa sổ), `rank`, `group`.
- `market`: số mã tăng, giảm, đi ngang và Return bình quân.
- `window_days`: độ dài cửa sổ tính bằng ngày lịch, không phải số phiên. Viết "trong 30 ngày qua", không viết "30 phiên".
- `language`: `vi` thì viết tiếng Việt, `en` thì viết tiếng Anh.

## Khuôn `picks.json`

```json
{
  "summary": "Một câu về toàn nhóm 10 mã trong cửa sổ, dựa trên market.",
  "picks": [
    {"ticker": "FPT", "reason": "2–3 câu: vì sao mã này đứng đầu theo Return so với biến động, xu hướng, khối lượng."},
    {"ticker": "VCB", "reason": "..."},
    {"ticker": "MBB", "reason": "..."}
  ]
}
```

## Luật viết

- Đủ mọi mã trong `top`, đúng thứ tự, không thêm mã khác.
- Mỗi lý do 2–3 câu, 20–400 ký tự. `summary` tối đa 300 ký tự.
- Không gõ con số phần trăm. Bảng trong report đã có số do script tính; lý do chỉ diễn giải ("Return cao nhất nhóm, biến
  động thấp hơn mặt bằng").
- Chỉ dựa vào các trường trên. `metrics.json` không có diễn biến từng phiên, nên không viết "tăng mạnh trong các phiên cuối"
  hay nhận định nào không suy ra được từ Return, biến động, xu hướng, khối lượng và thứ hạng.
- Không viết "nên mua", "chắc chắn tăng". Report là tín hiệu để xem xét, không phải khuyến nghị đầu tư.
- `volume_ratio` trên 1 là khối lượng gần đây cao hơn bình thường; dưới 1 là thấp hơn.

Skill `stock-report` kiểm các luật trên trước khi dựng report. Nó báo lỗi thì sửa đúng chỗ nó chỉ trong `picks.json`.
