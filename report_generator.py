"""輸出 HTML 報告"""
from jinja2 import Template
from datetime import datetime
import os

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>選股報告 {{ date }}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "PingFang TC", sans-serif; background: #f0f2f5; color: #1a1a2e; }
  .header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 32px; }
  .header h1 { font-size: 24px; font-weight: 700; }
  .header p { color: #94a3b8; margin-top: 6px; font-size: 14px; }
  .stats { display: flex; gap: 16px; padding: 24px 32px; flex-wrap: wrap; }
  .stat-card { background: white; border-radius: 12px; padding: 20px 28px; flex: 1; min-width: 150px;
               box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .stat-card .num { font-size: 32px; font-weight: 700; color: #e63946; }
  .stat-card .label { font-size: 13px; color: #64748b; margin-top: 4px; }
  .section { padding: 0 32px 32px; }
  .section h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #374151;
                border-left: 4px solid #e63946; padding-left: 12px; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px;
          overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  th { background: #1a1a2e; color: white; padding: 12px 16px; text-align: left; font-size: 13px; font-weight: 500; }
  td { padding: 12px 16px; font-size: 13px; border-bottom: 1px solid #f1f5f9; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #f8fafc; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .badge-hot { background: #fee2e2; color: #dc2626; }
  .badge-watch { background: #fef9c3; color: #854d0e; }
  .badge-ok { background: #dcfce7; color: #166534; }
  .score-bar { display: flex; align-items: center; gap: 8px; }
  .bar { height: 6px; border-radius: 3px; background: #e63946; }
  .reasons { font-size: 12px; color: #64748b; margin-top: 3px; }
  .tag { display: inline-block; background: #eff6ff; color: #1d4ed8; padding: 2px 8px;
         border-radius: 4px; font-size: 11px; margin: 2px 2px 0 0; }
  .empty { text-align: center; padding: 40px; color: #94a3b8; }
  .card { background: white; border-radius: 12px; margin-bottom: 16px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: hidden; }
  .card-header { padding: 14px 20px; display: flex; align-items: center; gap: 12px;
                 border-bottom: 1px solid #f1f5f9; }
  .card-code { font-size: 18px; font-weight: 700; }
  .card-name { font-size: 14px; color: #64748b; }
  .card-price { margin-left: auto; font-size: 20px; font-weight: 700; color: #e63946; }
  .card-body { padding: 16px 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .qa-block { padding: 10px 14px; background: #f8fafc; border-radius: 8px; }
  .qa-q { font-size: 11px; color: #64748b; font-weight: 600; margin-bottom: 4px; }
  .qa-a { font-size: 13px; color: #1e293b; line-height: 1.5; }
  .one-liner { grid-column: 1 / -1; background: #fffbeb; border-left: 3px solid #f59e0b;
               padding: 10px 14px; border-radius: 0 8px 8px 0; }
  .inst-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .inst-tag { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
  .inst-buy { background: #fee2e2; color: #dc2626; }
  .inst-sell { background: #f0fdf4; color: #166534; }
  .inst-neutral { background: #f1f5f9; color: #64748b; }
</style>
</head>
<body>
<div class="header">
  <h1>📊 選股雷達報告</h1>
  <p>產生時間：{{ date }} ．共分析 {{ total }} 支上市股票</p>
</div>

<div class="stats">
  <div class="stat-card"><div class="num">{{ hot_count }}</div><div class="label">🔥 強力推薦（3 模組）</div></div>
  <div class="stat-card"><div class="num">{{ watch_count }}</div><div class="label">👀 值得關注（2 模組）</div></div>
  <div class="stat-card"><div class="num">{{ observe_count }}</div><div class="label">📌 持續觀察（1 模組）</div></div>
  <div class="stat-card"><div class="num">{{ total }}</div><div class="label">本次分析總數</div></div>
</div>

{% macro stock_card(s, badge_class, badge_label) %}
<div class="card">
  <div class="card-header">
    <div>
      <div class="card-code">{{ s.code }} <span class="tag" style="background:#f0fdf4;color:#166534;font-size:11px">{{ s.sector or '—' }}</span></div>
      <div class="card-name">{{ s.name }}</div>
    </div>
    <span class="badge {{ badge_class }}" style="margin-left:8px">{{ badge_label }}</span>
    <div class="card-price">{{ s.price }} 元</div>
  </div>
  <div class="card-body">

    <div class="qa-block">
      <div class="qa-q">受益哪個大趨勢？</div>
      <div class="qa-a">{{ s.trend_tags or '—' }}</div>
    </div>

    <div class="qa-block">
      <div class="qa-q">供應鏈位置</div>
      <div class="qa-a">{{ s.position or '—' }} 游</div>
    </div>

    <div class="qa-block">
      <div class="qa-q">最近 EPS 表現</div>
      <div class="qa-a">
        {% if s.eps %}EPS {{ s.eps }} 元，{% endif %}
        {{ s.eps_trend or '資料不足' }}
        {% if s.eps_growth_yoy %}（YoY {{ s.eps_growth_yoy }}%）{% endif %}
      </div>
    </div>

    <div class="qa-block">
      <div class="qa-q">本益比合理嗎？</div>
      <div class="qa-a">
        {% if s.pe %}PE {{ s.pe }}，同業均 {{ s.sector_avg_pe or '—' }}，{{ s.pe_vs_sector }}
        {% else %}資料不足{% endif %}
      </div>
    </div>

    <div class="qa-block">
      <div class="qa-q">三大法人動向（近 10 日）</div>
      <div class="qa-a">
        <div class="inst-row">
          <span class="inst-tag {% if s.foreign_net > 0 %}inst-buy{% elif s.foreign_net < 0 %}inst-sell{% else %}inst-neutral{% endif %}">外資 {{ s.foreign_str or '—' }}</span>
          <span class="inst-tag {% if s.trust_net > 0 %}inst-buy{% elif s.trust_net < 0 %}inst-sell{% else %}inst-neutral{% endif %}">投信 {{ s.trust_str or '—' }}</span>
          <span class="inst-tag {% if s.dealer_net > 0 %}inst-buy{% elif s.dealer_net < 0 %}inst-sell{% else %}inst-neutral{% endif %}">自營 {{ s.dealer_str or '—' }}</span>
        </div>
      </div>
    </div>

    <div class="qa-block">
      <div class="qa-q">技術面訊號</div>
      <div class="qa-a">RSI {{ s.rsi }}，量比 {{ s.vol_ratio }}x，距低 +{{ s.from_low_pct }}%</div>
    </div>

    <div class="qa-block">
      <div class="qa-q">護城河</div>
      <div class="qa-a">{{ s.moat or '—' }}</div>
    </div>

    <div class="qa-block">
      <div class="qa-q">最大風險</div>
      <div class="qa-a">{{ s.risk_note or '—' }}</div>
    </div>

    <div class="qa-block one-liner">
      <div class="qa-q">一句話投資理由</div>
      <div class="qa-a"><strong>{{ s.one_liner or '—' }}</strong></div>
    </div>

  </div>
</div>
{% endmacro %}

{% if hot_stocks %}
<div class="section">
  <h2>🔥 強力推薦（三項訊號同時符合）</h2>
  {% for s in hot_stocks %}{{ stock_card(s, 'badge-hot', '強力推薦') }}{% endfor %}
</div>
{% endif %}

{% if watch_stocks %}
<div class="section">
  <h2>👀 值得關注（符合 2 個訊號）</h2>
  {% for s in watch_stocks %}{{ stock_card(s, 'badge-watch', '值得關注') }}{% endfor %}
</div>
{% endif %}

{% if observe_stocks %}
<div class="section">
  <h2>📌 持續觀察（符合 1 個模組）</h2>
  <table>
    <tr>
      <th>股票</th><th>現價</th><th>RSI</th><th>量比</th><th>距低點</th><th>判斷</th>
    </tr>
    {% for s in observe_stocks[:20] %}
    <tr>
      <td><strong>{{ s.code }}</strong><br><span style="color:#64748b;font-size:12px">{{ s.name }}</span></td>
      <td>{{ s.price }}</td>
      <td>{{ s.rsi }}</td>
      <td>{{ s.vol_ratio }}x</td>
      <td>+{{ s.from_low_pct }}%</td>
      <td><span class="badge badge-ok">觀察</span></td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}

{% if not hot_stocks and not watch_stocks %}
<div class="section">
  <div class="empty">本週市場條件偏緊，暫無強力推薦標的。請繼續觀察。</div>
</div>
{% endif %}

<div style="text-align:center;padding:24px;color:#94a3b8;font-size:12px">
  ⚠️ 本報告為自動化篩選結果，僅供參考，不構成投資建議。請自行評估風險。
</div>
</body>
</html>
"""

def generate_report(final_df, total_analyzed, output_dir=".", mode="general"):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_date = datetime.now().strftime("%Y%m%d")

    hot = final_df[final_df["grade"] == "hot"].to_dict("records")
    watch = final_df[final_df["grade"] == "watch"].to_dict("records")
    observe = final_df[final_df["grade"] == "observe"].to_dict("records")

    def prep(rows):
        for r in rows:
            r["themes_list"] = r.get("themes", "—").split("、") if r.get("themes") else ["—"]
            r["tech_reasons_str"] = " ／ ".join(r.get("tech_reasons", []))
        return rows

    tmpl = Template(HTML_TEMPLATE)
    html = tmpl.render(
        date=date_str,
        total=total_analyzed,
        hot_count=len(hot),
        watch_count=len(watch),
        observe_count=len(observe),
        hot_stocks=prep(hot),
        watch_stocks=prep(watch),
        observe_stocks=prep(observe),
    )

    output_path = os.path.join(output_dir, f"report_{file_date}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
