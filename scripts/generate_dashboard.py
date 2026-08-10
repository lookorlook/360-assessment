#!/usr/bin/env python3
"""
Step 4 - 360 环评看板生成器
从题库和 Base 数据生成交互式 HTML 看板

Usage:
  python generate_dashboard.py <excel_path> <data_json> [--output <html_path>]

支持两种数据模式:
1. Excel题库 + 已有看板内联数据 → 重新生成看板
2. Excel题库 + 飞书Base数据 → 首次生成看板
"""

import json, sys, os
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_excel import parse_excel
from process_base_data import process_records, compute_dashboard_data


def generate_dashboard_html(dashboard_data: dict, output_path: str):
    """生成看板 HTML"""

    html = __build_html(dashboard_data)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def __build_html(data: dict) -> str:
    """构建完整 HTML"""
    # 嵌入数据为 JSON
    data_json = json.dumps(data, ensure_ascii=False, default=str)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>360° 环评诊断看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#161A1E; --card:#21262D; --ink:#E6EDF3; --ink2:#8B949E; --line:#30363D;
  --brand:#58A6FF; --brand-soft:#1F2937;
  --good:#3FB950; --mid:#D29922; --bad:#F85149;
  --peer:#58A6FF; --sub:#F0883E;
  --shadow:0 1px 3px rgba(0,0,0,.3),0 6px 24px rgba(0,0,0,.2);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.6;padding-bottom:60px}}
.wrap{{max-width:1200px;margin:0 auto;padding:0 22px}}
header.hero{{background:linear-gradient(120deg,#131C2E,#1A3370 55%,#1F4388);color:#fff;padding:28px 0 34px}}
header.hero .wrap{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:16px}}
.hero h1{{font-size:22px;font-weight:700}}
.hero .sub{{opacity:.9;font-size:13px;margin-top:6px}}
.pill{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);border-radius:10px;padding:10px 14px;font-size:13px;text-align:center;min-width:110px}}
.pill b{{display:block;font-size:20px;font-weight:800;margin-top:2px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin:-22px 0 26px}}
.kpi{{background:var(--card);border-radius:14px;padding:16px;box-shadow:var(--shadow);border:1px solid var(--line)}}
.kpi .l{{font-size:12px;color:var(--ink2);display:flex;align-items:center;gap:6px}}
.kpi .v{{font-size:22px;font-weight:800;margin-top:8px}}
.kpi .d{{font-size:11px;color:var(--ink2);margin-top:3px}}
.dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.dot.bad{{background:var(--bad)}} .dot.good{{background:var(--good)}} .dot.brand{{background:var(--brand)}}
section{{background:var(--card);border-radius:16px;padding:24px;margin-bottom:20px;box-shadow:var(--shadow);border:1px solid var(--line)}}
.sec-h{{display:flex;align-items:center;gap:10px;margin-bottom:16px}}
.sec-h .ic{{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;font-size:16px;background:var(--brand-soft);color:var(--brand)}}
.sec-h h2{{font-size:17px;font-weight:700}}
.note{{font-size:12px;color:var(--ink2);margin-bottom:14px}}
.bar-line{{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}}
.bar-line .name{{width:140px;flex:none;color:var(--ink2);text-align:right;font-size:12px}}
.bar-track{{flex:1;background:#161A1E;border-radius:7px;height:20px;position:relative;overflow:hidden}}
.bar-fill{{height:100%;border-radius:7px;display:flex;align-items:center;justify-content:flex-end;padding-right:7px;color:#fff;font-size:11px;font-weight:700;transition:width 1s cubic-bezier(.2,.8,.2,1)}}
.bar-fill.peer{{background:linear-gradient(90deg,#388BFD,#58A6FF)}}
.bar-fill.sub{{background:linear-gradient(90deg,#D4622E,#F0883E)}}
.legend{{display:flex;gap:18px;font-size:12px;color:var(--ink2);margin:4px 0 14px}}
.legend i{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:-1px}}
.chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}}
@media(max-width:860px){{.chart-row{{grid-template-columns:1fr}} .kpis{{grid-template-columns:repeat(2,1fr)}}}}
.chart-box{{position:relative;height:380px}}
.tl{{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:8px}}
.tl .h{{font-size:13px;font-weight:700;display:flex;justify-content:space-between;align-items:center}}
.tl .q{{font-size:12px;color:var(--ink2);margin-top:4px}}
.tl .score{{font-weight:800;font-size:16px}}
.tl .stdev{{font-size:10px;color:var(--ink2);margin-left:4px}}
.risk{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.rc{{border:1px solid var(--line);border-radius:13px;padding:15px;background:var(--card);border-left:4px solid var(--bad)}}
.rc.amber{{border-left-color:var(--mid)}}
.rc .t{{font-size:14px;font-weight:700;margin-bottom:5px}}
.rc p{{font-size:12px;color:var(--ink2);margin-top:4px}}
.quote{{border-left:3px solid var(--line);padding:5px 0 5px 11px;margin:9px 0 4px;font-size:11px;color:var(--ink2);font-style:italic}}
.tags{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}}
.atag{{background:rgba(248,81,73,.15);color:var(--bad);border:1px solid rgba(248,81,73,.3);border-radius:999px;padding:5px 12px;font-size:12px;font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}}
th{{color:var(--ink2);font-weight:600;font-size:11px;background:#161A1E}}
td .bar-sm{{display:inline-block;height:14px;border-radius:3px;background:var(--brand);vertical-align:middle;margin-right:6px}}
tr:hover td{{background:rgba(88,166,255,.05)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700}}
.badge.peer{{background:rgba(88,166,255,.15);color:var(--peer)}}
.badge.sub{{background:rgba(240,136,62,.15);color:var(--sub)}}
</style>
</head>
<body>
<div id="app">加载中...</div>

<script>
const DATA = {data_json};

// ====== 核心计算 ======
function avg(arr) {{ return arr.filter(v => v !== null && !isNaN(v)).reduce((a,b)=>a+b,0) / arr.filter(v => v !== null && !isNaN(v)).length || 0; }}
function stdevCalc(arr) {{ const a = arr.filter(v => v !== null && !isNaN(v)); if(a.length<2) return null; const m = a.reduce((s,v)=>s+v,0)/a.length; return Math.sqrt(a.reduce((s,v)=>s+Math.pow(v-m,2),0)/a.length); }}

const QIDS = DATA.questions.map(q=>q.id);
const DIMS = DATA.dim_list;
const SCORES = DATA.scores;

// 按关系分组
const evaluators = DATA.evaluators || [];
const peerIdx = evaluators.map((e,i)=>(e.relation||'').includes('平级')?i:-1).filter(i=>i>=0);
const subIdx = evaluators.map((e,i)=>(e.relation||'').includes('下级')?i:-1).filter(i=>i>=0);

// 维度均分
const dimAvgs = {{}};
DATA.question_bank.dimensions.forEach(dim => {{
  let all=[]; dim.questions.forEach(q => {{ all = all.concat((SCORES[q.id]||[]).filter(v=>v!==null)); }});
  dimAvgs[dim.name] = avg(all);
}});

// 每题均分
const qAvgs = {{}};
QIDS.forEach(q => {{ const s=SCORES[q]||[]; qAvgs[q] = avg(s); }});

// 全局数据
const allScores = QIDS.flatMap(q => (SCORES[q]||[]).filter(v=>v!==null));
const allAvg = avg(allScores);
const peerAvg = avg(peerIdx.flatMap(i => QIDS.map(q => (SCORES[q]||[])[i]).filter(v=>v!==null)));
const subAvg = avg(subIdx.flatMap(i => QIDS.map(q => (SCORES[q]||[])[i]).filter(v=>v!==null)));

// 排序
const sortedCats = Object.entries(dimAvgs).sort((a,b) => (b[1]||0) - (a[1]||0));
const sortedQ = QIDS.map(q => ({{q,v:qAvgs[q]}})).filter(x=>x.v>0).sort((a,b)=>(a.v||0)-(b.v||0));

// ====== 渲染 ======
function render() {{
    let h = '';
    
    // 标题
    h += `<header class="hero">
        <div class="wrap">
            <div>
                <h1>${{DATA.question_bank.meta.table_title}} · ${{DATA.question_bank.meta.subject}}</h1>
                <div class="sub">${{DATA.dim_list.length}} 维度 · ${{QIDS.length}} 项指标 · ${{evaluators.length}} 位评价者 (${{peerIdx.length}} 平级 + ${{subIdx.length}} 下级)</div>
            </div>
            <div style="display:flex;gap:10px">
                <div class="pill"><b>${{peerIdx.length}}</b>有效平级</div>
                <div class="pill"><b>${{subIdx.length}}</b>有效下级</div>
            </div>
        </div>
    </header>`;

    // KPI 卡片
    h += `<div class="wrap"><div class="kpis">
        <div class="kpi"><div class="l">📊 综合平均分</div><div class="v">${{allAvg.toFixed(2)}}</div><div class="d">满分 5.0 · ${{allScores.length}} 条评分</div></div>
        <div class="kpi"><div class="l"><span class="dot good"></span>最高维度</div><div class="v">${{sortedCats[0][1].toFixed(2)}}</div><div class="d">${{sortedCats[0][0]}}</div></div>
        <div class="kpi"><div class="l"><span class="dot bad"></span>最低维度</div><div class="v">${{sortedCats[sortedCats.length-1][1].toFixed(2)}}</div><div class="d">${{sortedCats[sortedCats.length-1][0]}}</div></div>
        <div class="kpi"><div class="l">⚖️ 下级 vs 平级</div><div class="v">${{subAvg.toFixed(2)}} / ${{peerAvg.toFixed(2)}}</div><div class="d">差 ${{Math.abs(subAvg-peerAvg).toFixed(2)}} 分</div></div>
        <div class="kpi"><div class="l">🔍 最大分歧项</div><div class="v" id="kpi-max-stdev">--</div><div class="d" id="kpi-max-stdev-q"></div></div>
    </div>`;

    // 维度对比
    h += `<section><div class="sec-h"><div class="ic">📊</div><h2>维度对比分析（平级 vs 下级）</h2></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">`;

    // 柱状图
    h += `<div>`;
    DIMS.forEach(dim => {{
        const d = DATA.dimensions[dim] || {{peer:0,sub:0}};
        h += `<div class="bar-line"><div class="name">${{dim}}</div><div class="bar-track"><div class="bar-fill peer" style="width:${{(d.peer/5*100).toFixed(0)}}%">${{(d.peer||0).toFixed(2)}}</div></div></div>`;
        h += `<div class="bar-line"><div class="name" style="color:var(--ink2);font-size:10px">　　下级</div><div class="bar-track"><div class="bar-fill sub" style="width:${{(d.sub/5*100).toFixed(0)}}%">${{(d.sub||0).toFixed(2)}}</div></div></div>`;
    }});
    h += `</div>`;

    // 雷达图
    h += `<div class="chart-box"><canvas id="radarChart"></canvas></div></div>
        <div class="legend"><i style="background:var(--peer)"></i>平级 <i style="background:var(--sub)"></i>下级</div>
    </section>`;

    // 每题得分
    h += `<section><div class="sec-h"><div class="ic">📋</div><h2>各项指标得分</h2></div>
        <div style="max-height:600px;overflow-y:auto">`;
    QIDS.forEach(q => {{
        const v = qAvgs[q] || 0;
        const sd = stdevCalc((SCORES[q]||[]).filter(x=>x!==null));
        const qInfo = DATA.questions.find(x=>x.id===q);
        const tag = qInfo ? qInfo.tag : '';
        const dim = qInfo ? qInfo.dimension : '';
        const color = v < 3.0 ? 'var(--bad)' : v < 3.5 ? 'var(--mid)' : 'var(--good)';
        h += `<div class="tl">
            <div class="h"><span>${{q}} ${{tag}}</span><span class="score" style="color:${{color}}">${{v.toFixed(2)}}</span></div>
            <div style="flex:1;margin:6px 16px 0 0"><div class="bar-track"><div class="bar-fill peer" style="width:${{(v/5*100).toFixed(0)}}%;background:${{color}}"></div></div></div>
            <div class="q" style="display:flex;justify-content:space-between"><span>${{dim}}</span>${{sd !== null ? '<span>SD='+sd.toFixed(2)+'</span>' : ''}}</div>
        </div>`;
    }});
    h += `</div></section>`;

    // 评分热力图
    h += `<section><div class="sec-h"><div class="ic">🔢</div><h2>评价明细（热力图）</h2></div>
        <div style="overflow-x:auto"><table>
        <tr><th>评价人</th><th>关系</th>${{QIDS.map(q=>'<th>'+q+'</th>').join('')}}<th>均分</th></tr>`;
    evaluators.forEach((ev, ei) => {{
        h += `<tr><td>${{ev.name||('评价人'+(ei+1))}}</td>
            <td><span class="badge ${{(ev.relation||'').includes('平级')?'peer':'sub'}}">${{ev.relation||'未知'}}</span></td>`;
        const rowScores = QIDS.map(q => (SCORES[q]||[])[ei]);
        rowScores.forEach(s => {{
            const bg = s===null?'transparent': s>=4?'rgba(63,185,80,.2)': s>=3?'rgba(210,153,34,.2)':'rgba(248,81,73,.2)';
            h += `<td style="background:${{bg}};text-align:center">${{s!==null?s:'-'}}</td>`;
        }});
        h += `<td style="font-weight:700">${{avg(rowScores).toFixed(2)}}</td></tr>`;
    }});
    h += `</table></div></section>`;

    // 脚注
    h += `<div style="text-align:center;padding:20px;color:var(--ink2);font-size:12px">
        360° 环评诊断看板 | 数据来源: ${{DATA.question_bank.source_file || '飞书Base'}} | 生成时间: ${{new Date().toLocaleString('zh-CN')}}
    </div></div>`;

    document.getElementById('app').innerHTML = h;

    // 渲染雷达图
    new Chart(document.getElementById('radarChart'), {{
        type: 'radar',
        data: {{
            labels: DIMS,
            datasets: [{{
                label: '维度均分', data: DIMS.map(c => dimAvgs[c]),
                backgroundColor: 'rgba(88,166,255,0.12)', borderColor: '#58A6FF', borderWidth: 2,
                pointBackgroundColor: '#58A6FF', pointBorderColor: '#fff', pointRadius: 4
            }}]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            scales: {{ r: {{ min: 1, max: 5, ticks: {{ stepSize: 1, color: '#8B949E' }}, pointLabels: {{ color: '#E6EDF3', font: {{size:11}} }}, grid: {{ color: '#30363D' }}, angleLines: {{ color: '#30363D' }} }} }},
            plugins: {{ legend: {{ display: false }} }}
        }}
    }});

    // 找最大分歧项
    let maxSD = 0, maxSDQ = '';
    QIDS.forEach(q => {{
        const sd = stdevCalc((SCORES[q]||[]).filter(x=>x!==null));
        if (sd && sd > maxSD) {{ maxSD = sd; maxSDQ = q; }}
    }});
    document.getElementById('kpi-max-stdev').textContent = maxSD > 0 ? maxSD.toFixed(2) : '--';
    document.getElementById('kpi-max-stdev-q').textContent = maxSDQ;
}}

render();
</script>
</body>
</html>'''


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_dashboard.py <excel_path> <data_json> [--output <html_path>]")
        print("  data_json: 飞书Base导出的原始记录 JSON，或已有看板的 DATA 内联 JSON")
        sys.exit(1)

    excel_path = sys.argv[1]
    data_path = sys.argv[2]
    output_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        output_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    if not output_path:
        output_path = Path(__file__).parent.parent / 'outputs' / '360-dashboard.html'

    # Step 1: 解析题库
    print("📋 Step 1: 解析题库...")
    bank = parse_excel(excel_path)

    # Step 2: 加载数据
    print("📊 Step 2: 加载数据...")
    with open(data_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # 检测数据格式: 原始 Base records 还是看板内联数据?
    records = None
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        if 'questions' in raw and 'q25' in raw:
            # 这是看板内联 DATA 格式，需要转换
            print("   检测到看板内联数据格式，转换中...")
            records = __convert_dashboard_inline(raw)
        elif 'records' in raw:
            records = raw['records']
        elif 'data' in raw:
            records = raw['data']
        else:
            records = [raw]

    # Step 3: 处理数据
    print("🔢 Step 3: 计算指标...")
    processed = process_records(records, bank)
    dashboard_data = compute_dashboard_data(processed, bank)

    # Step 4: 生成看板
    print("🎨 Step 4: 生成看板 HTML...")
    path = generate_dashboard_html(dashboard_data, output_path)
    print(f"\n✅ 看板已生成: {path}")


def __convert_dashboard_inline(inline: dict) -> list:
    """将看板内联 DATA 格式转为 Base record 格式"""
    records = []
    evs = inline.get('evaluators', [])
    questions_data = inline.get('questions', [])
    data_matrix = inline.get('data', [])

    for ei, ev in enumerate(evs):
        fields = {}
        fields['评价人关系'] = [ev.get('relation', '')]

        for qi in range(len(questions_data)):
            if qi < len(data_matrix) and ei < len(data_matrix[qi]):
                score = data_matrix[qi][ei].get('score') if isinstance(data_matrix[qi][ei], dict) else data_matrix[qi][ei]
                qid = f'Q{qi+1}'
                tag = questions_data[qi].get('id', qid) if qi < len(questions_data) else qid
                fields[f'{qid}-{tag}'] = score

        records.append({'fields': fields})

    return records


if __name__ == '__main__':
    main()
