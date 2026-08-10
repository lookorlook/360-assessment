#!/usr/bin/env python3
"""
Step 3 - 飞书 Base 数据处理器
从飞书 Base 读取评价数据，处理为看板所需的数据格式

输入: question_bank.json + Base 数据 (通过 lark-cli 或本地JSON)
输出: dashboard_data.json (供看板 HTML 使用)

数据处理规则:
1. 解析评分: 从 select 字段提取 1-5 分数, None=无法判断
2. 按评价人关系分组: 上级/平级/下级
3. 计算维度均分
4. 计算每题均分、标准差
5. 提取开放性回答

Usage:
  python process_base_data.py {
    --base-token <token> --table-id <id> --question-bank <path> [--as user|bot]
  } | {
    --input-json <raw_data.json> --question-bank <path>
  }
"""

import json, sys, os, subprocess, re, platform
from statistics import mean, stdev
from collections import defaultdict

def _find_lark_cli():
    is_win = platform.system() == 'Windows'
    home = os.path.expanduser('~')
    base = os.path.join(home, '.workbuddy', 'binaries', 'node', 'versions')
    for ver in ['22.12.0', '22.22.2']:
        node_dir = os.path.join(base, ver)
        node_exe = os.path.join(node_dir, 'node.exe' if is_win else 'bin', 'node')
        script = os.path.join(node_dir, 'node_modules', '@larksuite', 'cli', 'scripts', 'run.js')
        if os.path.exists(node_exe) and os.path.exists(script):
            return {'node': node_exe, 'script': script}
    return {'node': 'node', 'script': None}

LARK_CLI = _find_lark_cli()


def run_lark(*args, timeout=120):
    node = LARK_CLI['node']; script = LARK_CLI.get('script')
    cmd = [node, script] + list(args) if script else [node] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        try:
            err = json.loads(result.stderr or '{}')
        except:
            err = {}
        return {'ok': False, 'error': err.get('message', result.stderr or result.stdout)}
    try:
        return json.loads(result.stdout)
    except:
        return {'ok': False, 'error': result.stdout}


def fetch_base_records(base_token: str, table_id: str, identity: str = 'user') -> list:
    """从 Base 获取全部记录"""
    all_records = []
    offset = 0
    limit = 200

    while True:
        result = run_lark(
            'base', '+record-list',
            '--base-token', base_token,
            '--table-id', table_id,
            '--limit', str(limit),
            '--offset', str(offset),
            f'--as', identity
        )
        if not result.get('ok'):
            print(f"❌ 读取记录失败: {result.get('error')}")
            break

        data = result.get('data', {})
        records = data.get('records', [])
        all_records.extend(records)

        if not data.get('has_more'):
            break
        offset += limit

    return all_records


def parse_score_from_cell(cell_value) -> int | None:
    """从 cell 值提取分数"""
    if cell_value is None:
        return None
    if isinstance(cell_value, (int, float)):
        return int(cell_value)
    if isinstance(cell_value, str):
        m = re.match(r'(\d+)分', cell_value)
        if m:
            return int(m.group(1))
        if '无法判断' in cell_value or 'N/A' in cell_value:
            return None
    if isinstance(cell_value, list) and cell_value:
        # select 字段返回的是选项数组
        opt = cell_value[0] if isinstance(cell_value[0], str) else cell_value[0].get('text', '')
        return parse_score_from_cell(opt)
    return None


def parse_relationship(cell_value) -> str:
    """解析评价人关系"""
    if not cell_value:
        return '未指定'
    if isinstance(cell_value, list) and cell_value:
        opt = cell_value[0] if isinstance(cell_value[0], str) else cell_value[0].get('text', '')
        if '上级' in opt:
            return '上级'
        if '平级' in opt:
            return '平级'
        if '下级' in opt:
            return '下级'
    return str(cell_value)


def process_records(records: list, question_bank: dict) -> dict:
    """处理记录数据，生成看板数据结构"""

    questions = []
    for dim in question_bank['dimensions']:
        for q in dim['questions']:
            questions.append(q)

    # 数据结构: scores[q_idx][evaluator_idx] = score
    evaluators = []  # [{name, relation}]
    scores = {q['id']: [] for q in questions}
    open_texts = {}

    for record in records:
        fields = record.get('fields', {})

        # 提取评价人关系
        rel = None
        for k, v in fields.items():
            if '评价人关系' in k or 'Relationship' in k:
                rel = parse_relationship(v)
                break

        # 提取各题评分
        ev_idx = len(evaluators)
        eval_name = f"评价人{ev_idx + 1}"
        evaluators.append({
            'name': eval_name,
            'id': record.get('record_id', f'rec_{ev_idx}'),
            'relation': rel or '未指定'
        })

        # 匹配字段到题目
        for q in questions:
            qid = q['id']
            tag = q['tag']
            score = None
            for field_key, field_val in fields.items():
                if qid in field_key and tag in field_key:
                    if '原因' not in field_key and '补充' not in field_key:
                        score = parse_score_from_cell(field_val)
                        break
            scores[qid].append(score)

        # 提取开放性回答
        for field_key, field_val in fields.items():
            if '提升和改进' in field_key:
                open_texts.setdefault('improvement', []).append({
                    'author': eval_name,
                    'text': str(field_val) if field_val else ''
                })

    return {
        'evaluators': evaluators,
        'questions': scores,
        'open_texts': open_texts,
        'total_records': len(records)
    }


def compute_dashboard_data(processed: dict, question_bank: dict) -> dict:
    """计算看板所需的聚合数据"""

    dims = question_bank['dimensions']
    evs = processed['evaluators']
    scores = processed['questions']

    # 问题列表
    all_qs = []
    for d in dims:
        for q in d['questions']:
            all_qs.append({
                'id': q['id'],
                'text': q['description'],
                'dimension': d['name'],
                'tag': q['tag']
            })

    # 按评价人关系分组
    peer_indices = [i for i, e in enumerate(evs) if '平级' in e.get('relation', '')]
    sub_indices = [i for i, e in enumerate(evs) if '下级' in e.get('relation', '')]
    sup_indices = [i for i, e in enumerate(evs) if '上级' in e.get('relation', '')]

    # 维度均分
    dim_avgs = {}
    for d in dims:
        peer_all, sub_all = [], []
        for q in d['questions']:
            qs = scores.get(q['id'], [])
            if qs:
                peer_all += [qs[i] for i in peer_indices if i < len(qs) and qs[i] is not None]
                sub_all += [qs[i] for i in sub_indices if i < len(qs) and qs[i] is not None]

        dim_avgs[d['name']] = {
            'peer': round(mean(peer_all), 2) if peer_all else None,
            'sub': round(mean(sub_all), 2) if sub_all else None
        }

    # 每题均分
    q_avgs = {}
    for q in all_qs:
        qs = scores.get(q['id'], [])
        valid = [s for s in qs if s is not None]
        q_avgs[q['id']] = {
            'avg': round(mean(valid), 2) if valid else None,
            'stdev': round(stdev(valid), 2) if len(valid) >= 2 else None,
            'n': len(valid)
        }

    return {
        'dimensions': dim_avgs,
        'question_avgs': q_avgs,
        'questions': all_qs,
        'dim_list': [d['name'] for d in dims],
        'evaluators': evs,
        'peer_count': len(peer_indices),
        'sub_count': len(sub_indices),
        'sup_count': len(sup_indices),
        'scores': scores,
        'question_bank': question_bank
    }


def main():
    if '--input-json' in sys.argv:
        idx = sys.argv.index('--input-json')
        input_json = sys.argv[idx + 1]

        idx_bank = sys.argv.index('--question-bank')
        bank_path = sys.argv[idx_bank + 1]

        with open(input_json, 'r', encoding='utf-8') as f:
            records = json.load(f)
        if isinstance(records, dict):
            records = records.get('records', records.get('data', []))

        with open(bank_path, 'r', encoding='utf-8') as f:
            bank = json.load(f)

    else:
        print("Usage: python process_base_data.py --input-json <raw_data.json> --question-bank <path>")
        print("   or: python process_base_data.py --base-token <token> --table-id <id> --question-bank <path>")
        sys.exit(1)

    processed = process_records(records, bank)
    dashboard_data = compute_dashboard_data(processed, bank)

    # 输出
    print(json.dumps(dashboard_data, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
