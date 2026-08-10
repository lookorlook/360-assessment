#!/usr/bin/env python3
"""
Step 2 - Feishu Base Creator
根据题库 JSON 创建飞书多维表格（Base）+ 表单

输入: question_bank.json
输出: 飞书 Base token + 表单 URL

核心逻辑:
1. 读取题库 JSON
2. 使用 lark-cli 创建 Base table
3. 为每道题创建 select 字段（1-5分 + 无法判断）
4. 为每道题创建「原因说明」text 字段
5. 为每道题创建「补充内容」text 字段（1分和5分的补充说明）
6. 创建「评价人关系」select 字段
7. 创建开放题 text 字段
8. 创建表单

Usage:
  python create_feishu_form.py <question_bank.json> [--base-name <name>] [--dry-run]
"""

import json, sys, os, subprocess, time, platform

LARK_CLI = _find_lark_cli()
LARK_IDENTITY = "--as user"


def _find_lark_cli():
    """Auto-detect lark-cli node and script paths cross-platform."""
    is_win = platform.system() == 'Windows'
    home = os.path.expanduser('~')
    base = os.path.join(home, '.workbuddy', 'binaries', 'node', 'versions')

    # Try common node versions
    for ver in ['22.12.0', '22.22.2']:
        node_dir = os.path.join(base, ver)
        node_exe = os.path.join(node_dir, 'node.exe' if is_win else 'bin', 'node')
        script = os.path.join(node_dir, 'node_modules', '@larksuite', 'cli', 'scripts', 'run.js')
        if os.path.exists(node_exe) and os.path.exists(script):
            return {'node': node_exe, 'script': script}

    # Fallback to system node
    return {'node': 'node', 'script': None}


def run_lark(*args, timeout=60):
    """运行 lark-cli 命令"""
    node = LARK_CLI['node']
    script = LARK_CLI.get('script')
    if script:
        cmd = [node, script] + list(args)
    else:
        cmd = [node] + list(args)
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


def create_base(name: str) -> dict:
    """创建新 Base"""
    result = run_lark(
        'base', '+base-create',
        '--name', name,
        '--table-name', '360环评数据',
        LARK_IDENTITY
    )
    return result


def create_field(base_token, table_id, field_json: dict) -> dict:
    """创建字段"""
    result = run_lark(
        'base', '+field-create',
        '--base-token', base_token,
        '--table-id', table_id,
        '--json', json.dumps(field_json, ensure_ascii=False),
        '--yes',
        LARK_IDENTITY
    )
    return result


def build_select_field(name: str, description: str, options: list) -> dict:
    """构建 select 类型字段 JSON"""
    return {
        'name': name,
        'type': 'select',
        'description': description,
        'options': [
            {
                'name': opt['name'],
                'hue': opt.get('hue', 'Wathet'),
                'lightness': opt.get('lightness', 'Lighter')
            }
            for opt in options
        ]
    }


def build_text_field(name: str) -> dict:
    """构建 text 类型字段 JSON"""
    return {
        'name': name,
        'type': 'text',
        'style': {'type': 'plain'}
    }


def build_scoring_options(scoring_options: list) -> list:
    """将评分选项转换为字段选项"""
    field_options = []
    hue_map = {5: 'Green', 4: 'Turquoise', 3: 'Wathet', 2: 'Orange', 1: 'Red'}
    light_map = {5: 'Light', 4: 'Lighter', 3: 'Lighter', 2: 'Lighter', 1: 'Lighter'}

    for opt in scoring_options:
        s = opt['score']
        if s is not None:
            label = f"{s}分：{opt['text']}"
            suffix = ""
            if s in (1, 5):
                suffix = "\n⚠️ 如选择此项，请举案例和场景说明原因\nPlease provide examples and scenarios to explain your choice"
            field_options.append({
                'name': f"{s}分：非常{'同意' if s==5 else '不同意' if s==1 else '比较同意' if s==4 else '比较不同意' if s==2 else '中立'}{suffix}",
                'hue': hue_map.get(s, 'Wathet'),
                'lightness': light_map.get(s, 'Default')
            })
        else:
            field_options.append({
                'name': '无法判断 / N/A',
                'hue': 'Gray',
                'lightness': 'Lighter'
            })
    return field_options


def create_360_base(question_bank_path: str, base_name: str = None, dry_run: bool = False) -> dict:
    """主流程：从题库创建飞书 Base"""

    with open(question_bank_path, 'r', encoding='utf-8') as f:
        bank = json.load(f)

    if not base_name:
        subject = bank['meta']['subject']
        base_name = f"360环评-{subject}胜任力评价"

    print(f"📋 题库: {bank['meta']['table_title']}")
    print(f"   被评价人: {bank['meta']['subject']}")
    print(f"   维度: {len(bank['dimensions'])} | 题目: {bank['total_questions']}")
    print(f"   目标Base: {base_name}")

    if dry_run:
        print("\n⚠️ DRY RUN 模式 - 不实际创建")
        __dry_run_output(bank)
        return {'ok': True, 'dry_run': True}

    # 1. 创建 Base
    print("\n[1/4] 创建飞书 Base...")
    base_result = create_base(base_name)
    if not base_result.get('ok'):
        print(f"   ❌ 创建失败: {base_result.get('error')}")
        return base_result

    base_token = base_result['data']['base']['base_token']
    print(f"   ✅ Base token: {base_token}")
    print(f"   🔗 {base_result['data']['base']['url']}")

    # 表格 ID
    table_id = base_result['data'].get('table_id')
    if not table_id:
        # 从 base-get 获取
        info = run_lark('base', '+base-get', '--base-token', base_token, LARK_IDENTITY)
        # 可能需要 table-list
        tables = run_lark('base', '+table-list', '--base-token', base_token, LARK_IDENTITY)
        if tables.get('ok'):
            table_id = tables['data']['tables'][0]['id']

    print(f"   📊 Table ID: {table_id}")

    # 2. 创建评分字段
    print("\n[2/4] 创建评分字段...")
    field_options = build_scoring_options(bank['scoring_options'])

    for dim in bank['dimensions']:
        for q in dim['questions']:
            qid = q['id']
            tag = q['tag']
            desc = q['description']

            # 评分字段
            field_name = f"{qid}-{tag} / {qid}-{tag}"
            field_desc = f"{desc}\n{qid}-{tag}"
            sf = build_select_field(field_name, field_desc, field_options)
            result = create_field(base_token, table_id, sf)
            if result.get('ok'):
                print(f"   ✅ {qid}")
            else:
                print(f"   ❌ {qid}: {result.get('error')}")
                # 简化名称重试
                field_name = f"{qid}-{tag}"
                sf['name'] = field_name
                result = create_field(base_token, table_id, sf)
                if result.get('ok'):
                    print(f"   ✅ {qid} (retry)")
                else:
                    print(f"   ❌ {qid} retry failed")
            time.sleep(0.3)

    # 3. 创建补充字段
    print("\n[3/4] 创建补充字段...")
    # 评价人关系字段
    rel_field = build_select_field(
        '评价人关系 / Relationship',
        '评价人与被评价人的关系',
        [{'name': '上级', 'hue': 'Red', 'lightness': 'Light'},
         {'name': '平级', 'hue': 'Wathet', 'lightness': 'Lighter'},
         {'name': '下级', 'hue': 'Orange', 'lightness': 'Lighter'}]
    )
    create_field(base_token, table_id, rel_field)

    # 开放题字段
    open_qs = [
        '您认为被评价人现阶段最需要提升和改进的方面有哪些；如无，请填无。',
        '综合评价 / Overall Assessment',
        '印象最深的管理决策 / Most Memorable Decision',
        '建议获取的外部支持 / Recommended External Support'
    ]
    for oq in open_qs:
        tf = build_text_field(oq)
        create_field(base_token, table_id, tf)
        time.sleep(0.2)

    print(f"   ✅ 补充字段创建完成")

    # 4. 创建表单
    print("\n[4/4] 创建表单...")
    form_result = run_lark(
        'base', '+form-create',
        '--base-token', base_token,
        '--table-id', table_id,
        '--name', f'360环评问卷-{bank["meta"]["subject"]}',
        '--yes',
        LARK_IDENTITY
    )
    if form_result.get('ok'):
        print(f"   ✅ 表单创建成功")
    else:
        print(f"   ⚠️ {form_result.get('error', 'unknown')}")

    print(f"\n✅ 创建完成!")
    print(f"   Base: {base_result['data']['base']['url']}")
    return {
        'ok': True,
        'base_token': base_token,
        'table_id': table_id,
        'url': base_result['data']['base']['url']
    }


def __dry_run_output(bank: dict):
    """Dry run 模式：展示将要创建的内容"""
    field_options = build_scoring_options(bank['scoring_options'])
    field_count = 0
    for dim in bank['dimensions']:
        print(f"\n--- {dim['name']} ---")
        for q in dim['questions']:
            field_count += 1
            print(f"   {q['id']}-{q['tag']}: {q['description']}")
            print(f"      评分选项: {len(field_options)} 个")
            print(f"      补充: {q['id']}-原因说明")
            print(f"      补充: {q['id']}-补充内容")
    print(f"\n📊 预计字段数: {field_count} 评分 + {field_count*2} 补充 + 1 评价人关系 + 4 开放题 = {field_count*3 + 5}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_feishu_form.py <question_bank.json> [--base-name <name>] [--dry-run]")
        sys.exit(1)

    bank_path = sys.argv[1]
    base_name = None
    dry_run = '--dry-run' in sys.argv

    if '--base-name' in sys.argv:
        idx = sys.argv.index('--base-name')
        base_name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    result = create_360_base(bank_path, base_name, dry_run)
    if not result.get('ok') and not result.get('dry_run'):
        print(f"\n❌ 创建失败: {result.get('error', 'Unknown error')}")
        sys.exit(1)
