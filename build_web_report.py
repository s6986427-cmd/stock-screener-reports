#!/usr/bin/env python3
"""整合『初期起漲偵測』+『剛離底階梯』兩套結果，產生手機看的網頁（index.html）"""
import os
import json
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PASSWORD = "19931026"

GRADE_LABEL = {"hot": "🔥 強力推薦", "watch": "👀 值得關注", "observe": "📌 持續觀察"}


def load_json(path):
    if not os.path.exists(path):
        return {"generated_at": None, "total_scanned": 0, "hits": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def early_card(r):
    reasons = "".join(f"<span class='tag'>{x}</span>" for x in r.get("reasons", []))
    return f"""
    <div class="card">
      <div class="card-head">
        <div><span class="code">{r['code']}</span><span class="name">{r.get('name','')}</span></div>
        <div class="price">{r['price']}</div>
      </div>
      <div class="meta">{r.get('market','')}｜{r.get('industry','')}</div>
      <div class="tags">{reasons}</div>
    </div>"""


def spike_card(r):
    reasons = "".join(f"<span class='tag'>{x}</span>" for x in r.get("reasons", []))
    return f"""
    <div class="card">
      <div class="card-head">
        <div><span class="code">{r['code']}</span><span class="name">{r.get('name','')}</span></div>
        <div class="price">{r['price']} <span class="gain">+{r.get('daily_gain_pct','')}%</span></div>
      </div>
      <div class="meta">{r.get('market','')}｜{r.get('industry','')}</div>
      <div class="tags">{reasons}</div>
    </div>"""


def sector_card(r):
    grade = r.get("grade", "observe")
    badge = GRADE_LABEL.get(grade, grade)
    one_liner = r.get("one_liner") or "—"
    return f"""
    <div class="card">
      <div class="card-head">
        <div><span class="code">{r['code']}</span><span class="name">{r.get('name','')}</span></div>
        <div class="price">{r.get('price','')}</div>
      </div>
      <div class="meta">{badge}｜{r.get('sector','')}｜{r.get('industry','')}</div>
      <div class="oneliner">{one_liner}</div>
    </div>"""


def main():
    early = load_json("early_rally_result.json")
    mid = load_json("mid_rally_result.json")
    spike = load_json("spike_result.json")
    sector = load_json("sector_result.json")

    early_hits = early.get("hits", [])
    mid_hits = mid.get("hits", [])
    spike_hits = spike.get("hits", [])
    sector_hits = sector.get("hits", [])
    sector_hot = [r for r in sector_hits if r.get("grade") == "hot"]
    sector_watch = [r for r in sector_hits if r.get("grade") == "watch"]
    sector_observe = [r for r in sector_hits if r.get("grade") == "observe"]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    early_html = "".join(early_card(r) for r in early_hits) or "<div class='empty'>目前沒有符合訊號的股票</div>"
    mid_html = "".join(early_card(r) for r in mid_hits) or "<div class='empty'>目前沒有符合訊號的股票</div>"
    spike_html = "".join(spike_card(r) for r in spike_hits) or "<div class='empty'>目前沒有符合訊號的股票</div>"
    hot_html = "".join(sector_card(r) for r in sector_hot)
    watch_html = "".join(sector_card(r) for r in sector_watch)
    observe_html = "".join(sector_card(r) for r in sector_observe)
    sector_html = (hot_html + watch_html + observe_html) or "<div class='empty'>目前沒有符合訊號的股票</div>"

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>選股報告</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "PingFang TC", sans-serif; background: #0f1117; color: #e5e7eb; padding-bottom: 40px; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px 20px; }}
  .header h1 {{ font-size: 20px; font-weight: 700; }}
  .header p {{ color: #94a3b8; margin-top: 6px; font-size: 13px; }}
  .section {{ padding: 20px 16px; }}
  .section h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #cbd5e1; border-left: 4px solid #e63946; padding-left: 10px; }}
  .card {{ background: #1a1d29; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .code {{ font-size: 16px; font-weight: 700; color: #f1f5f9; margin-right: 8px; }}
  .name {{ font-size: 13px; color: #94a3b8; }}
  .price {{ font-size: 17px; font-weight: 700; color: #ef4444; }}
  .gain {{ font-size: 13px; font-weight: 700; color: #f87171; margin-left: 4px; }}
  .meta {{ font-size: 12px; color: #64748b; margin-top: 6px; }}
  .oneliner {{ font-size: 13px; color: #cbd5e1; margin-top: 8px; line-height: 1.5; }}
  .tags {{ margin-top: 8px; }}
  .tag {{ display: inline-block; background: #172554; color: #93c5fd; padding: 3px 8px; border-radius: 4px; font-size: 11px; margin: 2px 4px 2px 0; }}
  .empty {{ text-align: center; padding: 24px; color: #64748b; font-size: 13px; }}
  .footer {{ text-align: center; color: #475569; font-size: 11px; padding: 20px; }}

  #gate {{ position: fixed; inset: 0; background: #0f1117; display: flex; align-items: center; justify-content: center; z-index: 100; }}
  #gate input {{ font-size: 18px; padding: 10px 14px; border-radius: 8px; border: 1px solid #334155; background: #1a1d29; color: #e5e7eb; width: 200px; text-align: center; }}
  #gate button {{ font-size: 16px; padding: 10px 18px; border-radius: 8px; border: none; background: #e63946; color: white; margin-left: 8px; }}
  #content {{ display: none; }}
</style>
</head>
<body>

<div id="gate">
  <div>
    <div style="color:#94a3b8; margin-bottom:10px; font-size:14px; text-align:center;">請輸入密碼</div>
    <input type="password" id="pw" maxlength="20" />
    <button onclick="checkPw()">進入</button>
  </div>
</div>

<div id="content">
  <div class="header">
    <h1>📊 選股報告</h1>
    <p>更新時間：{now_str}｜全市場掃描 {early.get('total_scanned',0)} 檔｜剛離底階梯掃描 {sector.get('total_scanned',0)} 檔</p>
  </div>

  <div class="section">
    <h2>💥 剛噴出（今日價漲量爆，{len(spike_hits)} 檔）</h2>
    {spike_html}
  </div>

  <div class="section">
    <h2>🚀 初期起漲偵測（全市場，{len(early_hits)} 檔）</h2>
    {early_html}
  </div>

  <div class="section">
    <h2>📈 續漲確認（已起漲一段，全市場，{len(mid_hits)} 檔）</h2>
    {mid_html}
  </div>

  <div class="section">
    <h2>🪜 剛離底階梯（七大產業，{len(sector_hits)} 檔）</h2>
    {sector_html}
  </div>

  <div class="footer">本報告為自動化篩選結果，僅供參考，不構成投資建議</div>
</div>

<script>
  const PW = "{PASSWORD}";
  function checkPw() {{
    const val = document.getElementById('pw').value;
    if (val === PW) {{
      document.getElementById('gate').style.display = 'none';
      document.getElementById('content').style.display = 'block';
      try {{ localStorage.setItem('stock_report_pw_ok', '1'); }} catch(e) {{}}
    }} else {{
      alert('密碼錯誤');
    }}
  }}
  document.getElementById('pw').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') checkPw();
  }});
  try {{
    if (localStorage.getItem('stock_report_pw_ok') === '1') {{
      document.getElementById('gate').style.display = 'none';
      document.getElementById('content').style.display = 'block';
    }}
  }} catch(e) {{}}
</script>

</body>
</html>
"""

    with open("web_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("已產生 web_report.html")


if __name__ == "__main__":
    main()
