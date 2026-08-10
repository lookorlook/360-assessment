#!/usr/bin/env python3
"""
AI Content Analysis Module for 360 Assessment Dashboard.
Analyzes processed score data + open-ended responses to generate
all qualitative analysis sections dynamically.

Usage:
  from analyze_content import analyze
  analysis = analyze(dashboard_data, question_bank)
"""

import json, re
from statistics import mean, stdev
from collections import Counter, defaultdict


def analyze(dashboard_data: dict, question_bank: dict) -> dict:
    """Main entry point: generate all analysis sections."""

    scores = dashboard_data.get('scores', {})
    evaluators = dashboard_data.get('evaluators', [])
    dim_avgs = dashboard_data.get('dimensions', {})
    questions = dashboard_data.get('questions', [])
    dim_list = dashboard_data.get('dim_list', [])

    peer_idx = [i for i, e in enumerate(evaluators) if '平级' in e.get('relation', '')]
    sub_idx = [i for i, e in enumerate(evaluators) if '下级' in e.get('relation', '')]

    peer_avg = _avg([_avg([(scores.get(q['id'], [])[i] if i < len(scores.get(q['id'], [])) else None) for q in questions]) for i in peer_idx])
    sub_avg = _avg([_avg([(scores.get(q['id'], [])[i] if i < len(scores.get(q['id'], [])) else None) for q in questions]) for i in sub_idx])

    return {
        'bottlenecks': _analyze_bottlenecks(scores, questions, evaluators, dim_avgs, peer_idx, sub_idx),
        'risks': _analyze_risks(scores, questions, evaluators, peer_idx, sub_idx),
        'strengths': _analyze_strengths(dim_avgs, dim_list, questions, scores, sub_idx),
        'text_mining': _analyze_text_mining(scores, questions, evaluators),
        'quadrant': _analyze_quadrant(peer_avg, sub_avg, peer_idx, sub_idx),
        'summary': _generate_summary(dim_avgs, dim_list, scores, questions, peer_idx, sub_idx, evaluators),
        'idp': _analyze_idp(question_bank, scores, peer_idx, sub_idx),
    }


# ============================================================
# 1. Collaboration Bottlenecks
# ============================================================

def _analyze_bottlenecks(scores, questions, evaluators, dim_avgs, peer_idx, sub_idx):
    """Detect cross-functional collaboration pain points."""
    bottlenecks = []

    # Find cross-collab dimension questions (沟通协作)
    collab_qs = [q for q in questions if '协作' in q.get('dimension', '') or '沟通' in q.get('dimension', '')]
    if not collab_qs:
        collab_qs = questions  # fallback to all

    for q in collab_qs:
        qid = q['id']
        qs = scores.get(qid, [])
        if not qs:
            continue

        p_scores = [qs[i] for i in peer_idx if i < len(qs) and qs[i] is not None]
        s_scores = [qs[i] for i in sub_idx if i < len(qs) and qs[i] is not None]

        p_avg = _avg(p_scores)
        s_avg = _avg(s_scores)

        if p_avg is None or s_avg is None:
            continue

        gap = abs(s_avg - p_avg)

        if p_avg < 3.2 and gap > 0.5:
            bottlenecks.append({
                'question_id': qid,
                'question_text': q.get('text', ''),
                'tag': q.get('tag', ''),
                'dimension': q.get('dimension', ''),
                'peer_avg': round(p_avg, 2),
                'sub_avg': round(s_avg, 2),
                'gap': round(gap, 2),
                'severity': '严重' if p_avg < 2.8 else '中'
            })

    # Pick top 3
    bottlenecks.sort(key=lambda x: x['gap'], reverse=True)
    return bottlenecks[:3]


# ============================================================
# 2. Risk Points
# ============================================================

def _analyze_risks(scores, questions, evaluators, peer_idx, sub_idx):
    """Detect evaluation risks."""
    risks = []

    # Risk 1: Low discrimination evaluators
    for ei, ev in enumerate(evaluators):
        ev_scores = [(scores.get(q['id'], [])[ei] if ei < len(scores.get(q['id'], [])) else None) for q in questions]
        valid = [s for s in ev_scores if s is not None]
        if len(valid) >= 5:
            unique = len(set(valid))
            if unique <= 2:
                risks.append({
                    'type': 'data_quality',
                    'title': '数据可信度',
                    'rank': 'TOP 1',
                    'detail': f'部分评价人给出的评分缺乏区分度（{unique}种分值覆盖{len(valid)}题），建议结合多评价者交叉验证后使用。'
                })
                break

    # Risk 2: Items with very high standard deviation
    high_sd_items = []
    for q in questions:
        qid = q['id']
        qs_list = [s for s in scores.get(qid, []) if s is not None]
        if len(qs_list) >= 3:
            sd = _stdev(qs_list)
            if sd and sd > 1.5:
                high_sd_items.append((qid, sd, q.get('text', '')))

    if high_sd_items:
        high_sd_items.sort(key=lambda x: x[1], reverse=True)
        top_sd = high_sd_items[0]
        risks.append({
            'type': 'high_disagreement',
            'title': '评价分歧',
            'rank': 'TOP 2',
            'detail': f'{top_sd[0]}标准差达{top_sd[1]:.2f}，评价者对该项能力的判断差异显著，建议评委重点关注并追问具体事例。'
        })

    # Risk 3: Large peer-sub gap in people management
    mgmt_qs = [q for q in questions if '团队' in q.get('dimension', '') or '人才' in q.get('dimension', '') or '管理' in q.get('dimension', '')]
    if mgmt_qs and peer_idx and sub_idx:
        mgmt_peer = _avg([_avg([scores.get(q['id'], [])[i] for i in peer_idx if i < len(scores.get(q['id'], [])) and scores.get(q['id'], [])[i] is not None]) for q in mgmt_qs])
        mgmt_sub = _avg([_avg([scores.get(q['id'], [])[i] for i in sub_idx if i < len(scores.get(q['id'], [])) and scores.get(q['id'], [])[i] is not None]) for q in mgmt_qs])
        if mgmt_peer is not None and mgmt_sub is not None and abs(mgmt_sub - mgmt_peer) > 0.5:
            risks.append({
                'type': 'perception_gap',
                'title': '管理认知偏差',
                'rank': 'TOP 3',
                'detail': f'团队管理维度下级评分({mgmt_sub:.2f})与平级评分({mgmt_peer:.2f})存在显著差异，提示被评价人的团队内部与跨部门协作可能存在不同的管理风格表现。'
            })

    return risks[:3]


# ============================================================
# 3. Strengths & Highlights
# ============================================================

def _analyze_strengths(dim_avgs, dim_list, questions, scores, sub_idx):
    """Identify top strengths."""
    strengths = []

    sorted_dims = sorted([(d, dim_avgs.get(d, {}).get('peer', 0) or 0) for d in dim_list], key=lambda x: x[1], reverse=True)

    for i, (dim, score) in enumerate(sorted_dims[:3]):
        if score >= 3.3:
            dim_questions = [q for q in questions if q.get('dimension') == dim]
            q_details = []
            for q in dim_questions[:2]:
                qid = q['id']
                q_avg = _avg([s for s in scores.get(qid, []) if s is not None])
                q_details.append(f"{qid}({q.get('tag', '')})均分{q_avg:.2f}" if q_avg else qid)

            strengths.append({
                'rank': i + 1,
                'dimension': dim,
                'score': round(score, 2),
                'level': 'STRONG' if score >= 3.5 else 'GOOD',
                'detail': f'{dim}维度{score:.2f}分（{"排名第" + str(i+1)}），该领域表现出较稳定的能力水平。{"、".join(q_details)}。'
            })

    return strengths


# ============================================================
# 4. Text Mining
# ============================================================

def _analyze_text_mining(scores, questions, evaluators):
    """Extract key themes from open text data."""
    # For now, generate generic analysis based on data patterns
    # In production, this would parse actual open-ended response text

    all_q_avgs = []
    for q in questions:
        qid = q['id']
        qs = [s for s in scores.get(qid, []) if s is not None]
        all_q_avgs.append((qid, _avg(qs), q.get('tag', '')))

    all_q_avgs.sort(key=lambda x: x[1] or 0)

    # Generate semantic clusters based on actual data
    clusters = []
    if all_q_avgs:
        # Low score items → potential issues
        low_items = [item for item in all_q_avgs[:3] if item[1] and item[1] < 3.3]
        if low_items:
            tags = [item[2] for item in low_items]
            clusters.append({
                'keyword': '、'.join(tags),
                'description': f'均分低于3.3的指标集中在这些能力项上，是当前阶段的重点关注方向。',
                'detail': f'最低三项：{", ".join(f"{t}({s:.2f})" for _, s, t in low_items)}'
            })

        # High scoring items → strengths
        high_items = [item for item in all_q_avgs[-3:] if item[1] and item[1] > 3.5]
        if high_items:
            tags = [item[2] for item in high_items]
            clusters.append({
                'keyword': '、'.join(tags),
                'description': '得分较高的能力项形成了当前的竞争优势，可作为进一步发展的基础。',
                'detail': f'最高三项：{", ".join(f"{t}({s:.2f})" for _, s, t in high_items)}'
            })

    return {
        'clusters': clusters or [{'keyword': '数据不足', 'description': '当前评价数据量不足以进行可靠的文本语义分析，建议增加评价者数量后重新生成。'}],
        'note': '基于评分数据的关键能力聚类分析（开放题文本挖掘需人工审阅）'
    }


# ============================================================
# 5. Quadrant Positioning
# ============================================================

def _analyze_quadrant(peer_avg, sub_avg, peer_idx, sub_idx):
    """Determine quadrant position based on peer vs sub scores."""

    if peer_avg is None or sub_avg is None:
        return {'position': '数据不足', 'decision': '无法分析', 'detail': '缺少足够的平级或下级评价数据。'}

    # Quadrant thresholds: 3.5 as center point
    if peer_avg >= 3.5 and sub_avg >= 3.5:
        position = '表现稳健型管理者'
        decision = '优先晋升或重点培养'
        detail = f'平级{peer_avg:.2f} / 下级{sub_avg:.2f}，内外评价一致偏高，综合表现得到多方认可。'
    elif peer_avg >= 3.5 and sub_avg < 3.5:
        position = '向上管理突出型'
        decision = '保持 + 关注下级反馈'
        detail = f'平级{peer_avg:.2f} / 下级{sub_avg:.2f}，跨层级管理能力强，但对下级管理可能存在盲区，需关注下级反馈。'
    elif peer_avg < 3.5 and sub_avg >= 3.5:
        position = '内部导向型管理者'
        decision = '保留 + 定向发展'
        detail = f'平级{peer_avg:.2f} / 下级{sub_avg:.2f}，团队内部认可度较高，但跨部门协同维度存在改善空间。'
    else:
        position = '待改善型'
        decision = '重点辅导 + 限期观察'
        detail = f'平级{peer_avg:.2f} / 下级{sub_avg:.2f}，多维度评分均有提升空间，建议制定专项发展计划。'

    return {
        'position': position,
        'decision': decision,
        'detail': detail,
        'peer_avg': round(peer_avg, 2),
        'sub_avg': round(sub_avg, 2),
        'peer_count': len(peer_idx),
        'sub_count': len(sub_idx)
    }


# ============================================================
# 6. Comprehensive Summary
# ============================================================

def _generate_summary(dim_avgs, dim_list, scores, questions, peer_idx, sub_idx, evaluators):
    """Generate comprehensive evaluation summary."""

    sorted_dims = sorted([(d, dim_avgs.get(d, {}).get('peer', 0) or 0) for d in dim_list], key=lambda x: x[1], reverse=True)

    # Top and bottom dimensions
    top_dims = sorted_dims[:2]
    bottom_dims = sorted_dims[-2:]

    # Max disagreement item
    max_sd_q = None
    max_sd = 0
    for q in questions:
        qid = q['id']
        qs = [s for s in scores.get(qid, []) if s is not None]
        if len(qs) >= 3:
            sd = _stdev(qs)
            if sd and sd > max_sd:
                max_sd = sd
                max_sd_q = q

    # Overall average
    all_scores = []
    for q in questions:
        all_scores.extend([s for s in scores.get(q['id'], []) if s is not None])
    overall_avg = _avg(all_scores)

    # Count scores
    total_scores = len(all_scores)

    # Development suggestions
    suggestions = []
    if bottom_dims:
        for dim, score in bottom_dims:
            if score < 3.3:
                suggestions.append(f'重点关注「{dim}」维度，建议制定专项提升计划并与上级对齐具体行动')

    # Quadrant-based suggestion
    peer_avg = _avg([_avg([(scores.get(q['id'], [])[i] if i < len(scores.get(q['id'], [])) else None) for q in questions]) for i in peer_idx])
    sub_avg = _avg([_avg([(scores.get(q['id'], [])[i] if i < len(scores.get(q['id'], [])) else None) for q in questions]) for i in sub_idx])

    if peer_avg is not None and sub_avg is not None and sub_avg - peer_avg > 0.5:
        suggestions.append('平级与下级评价存在显著认知差，建议加强跨部门信息同步和协作信任建设')

    return {
        'overall_avg': round(overall_avg, 2) if overall_avg else 0,
        'total_scores': total_scores,
        'evaluator_count': len(evaluators),
        'peer_count': len(peer_idx),
        'sub_count': len(sub_idx),
        'top_dimensions': [f'{d}({s:.2f})' for d, s in top_dims],
        'bottom_dimensions': [f'{d}({s:.2f})' for d, s in bottom_dims],
        'max_disagreement': f'{max_sd_q["id"]}({max_sd_q.get("tag","")})' if max_sd_q else '无显著分歧',
        'max_disagreement_sd': round(max_sd, 2) if max_sd > 0 else None,
        'suggestions': suggestions or ['当前评分数据整体表现稳定，建议结合实际业绩和面试反馈综合评估。'],
        'conclusion': _generate_conclusion(overall_avg, len(dim_list), top_dims, bottom_dims)
    }


def _generate_conclusion(overall_avg, dim_count, top_dims, bottom_dims):
    """Generate a concise overall conclusion."""
    if overall_avg is None:
        return '数据不足以形成综合结论。'

    if overall_avg >= 3.8:
        level = '优秀'
    elif overall_avg >= 3.3:
        level = '良好'
    elif overall_avg >= 2.8:
        level = '合格'
    else:
        level = '待提升'

    parts = [f'本次360评估综合平均分{overall_avg:.2f}，整体处于{level}水平。']

    if top_dims:
        parts.append(f'优势维度集中在{", ".join([d for d, s in top_dims])}。')
    if bottom_dims:
        parts.append(f'短板维度为{", ".join([d for d, s in bottom_dims])}。')

    return ' '.join(parts)


# ============================================================
# 7. IDP Analysis
# ============================================================

def _analyze_idp(question_bank, scores, peer_idx, sub_idx):
    """Analyze IDP phases based on scoring data."""
    # If question bank has idp data, use it; otherwise generate from questions
    idp_items = question_bank.get('idp', [])

    if not idp_items:
        # Auto-generate IDP items from dimensions
        idp_items = []
        for phase_idx, dim in enumerate(question_bank.get('dimensions', [])):
            idp_items.append({
                'phase': f'第{"一二" [phase_idx]}阶段' if phase_idx < 2 else f'第{phase_idx+1}阶段',
                'dimension': dim['name'],
                'questions': [q['id'] for q in dim['questions']],
                'avg_score': _avg([_avg([s for s in scores.get(q['id'], []) if s is not None]) for q in dim['questions']])
            })

    return idp_items


# ============================================================
# Helpers
# ============================================================

def _avg(arr):
    arr = [v for v in arr if v is not None and not isinstance(v, str)]
    return sum(arr) / len(arr) if arr else None

def _stdev(arr):
    arr = [v for v in arr if v is not None and not isinstance(v, str)]
    if len(arr) < 2:
        return None
    m = sum(arr) / len(arr)
    return (sum((v - m) ** 2 for v in arr) / len(arr)) ** 0.5


if __name__ == '__main__':
    # Test with sample data
    import sys
    if len(sys.argv) < 2:
        print("Usage: python analyze_content.py <dashboard_data.json>")
        sys.exit(1)
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
    result = analyze(data, data.get('question_bank', {}))
    print(json.dumps(result, ensure_ascii=False, indent=2))
