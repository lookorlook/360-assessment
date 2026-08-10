---
name: 360-assessment
description: >
  This skill handles the full 360-degree competency assessment workflow:
  1) Parse an offline Excel question bank (auto-detecting sheet names, dimensions,
  questions, scorers, and scoring options with flexible format support);
  2) Create a Feishu (Lark) Base table + form from the question bank structure;
  3) Process collected survey responses from the Feishu Base into analytics data;
  4) Generate an interactive HTML dashboard with Chart.js visualizations (KPI cards,
  dimension comparison bars, radar chart, score heatmap table, and evaluator matrix).
  Triggers: "360环评", "360评估", "胜任力评价", "生成360看板", "360 assessment",
  "competency evaluation", "360 dashboard", "环评看板", "检验题库", "题库模板".
agent_created: true
---

# 360° Competency Assessment Dashboard

## Purpose

End-to-end workflow for running 360-degree competency evaluations:

1. **Parse** an offline Excel question bank → structured JSON
2. **Create** a Feishu Base table and survey form from the parsed structure
3. **Process** survey responses from the Base into analytics
4. **Generate** an interactive HTML dashboard with charts, tables, and scoring analytics

## Quick Start

The user triggers this skill with a single sentence, e.g.:

- "帮我生成360看板，题库是这个Excel"
- "检验这个题库能不能用"
- "用这张表创建一个飞书问卷"
- "刷新360看板数据"

If the user provides no Excel path, ask for it.

---

## Workflow

### Step 1: Validate the Question Bank

Run the parser to check if the Excel file is compatible:

```bash
python "{SKILL_ROOT}/scripts/parse_excel.py" "<excel_path>"
```

Report these findings to the user:
- Detected sheets (question bank, evaluator list, scoring options)
- Subject name, title, table name
- Dimensions count, questions per dimension, total questions
- Evaluator list with levels (上级/平级/下级)

If parsing fails or dimension/question counts look wrong, tell the user which sheet/row format to fix, referencing the detection rules below.

### Step 2: Create Feishu Base + Form (on demand)

When the user wants to publish the question bank as a Feishu survey, run:

```bash
python "{SKILL_ROOT}/scripts/parse_excel.py" "<excel_path>" --output "<temp>/question_bank.json"
python "{SKILL_ROOT}/scripts/create_feishu_form.py" "<temp>/question_bank.json" --base-name "<name>"
```

Use `--dry-run` first to preview the field structure before actual creation.

The Feishu Base creation uses `lark-cli` (`lark-cli base +base-create`, `+field-create`, `+form-create`). The script auto-detects the lark-cli path from `~/.workbuddy/binaries/node/` (cross-platform, supports both Windows and macOS).

### Step 3: Process Responses + Generate Dashboard

When survey data has been collected in the Feishu Base:

```bash
python "{SKILL_ROOT}/scripts/generate_dashboard.py" "<excel_path>" "<data_json>" --output "<output_path>/360-dashboard.html"
```

The `data_json` can be:
- A JSON file exported from the Feishu Base (via `lark-cli base +record-list`)
- A JSON file with inline dashboard DATA format (for re-processing existing dashboards)

After generation, use `present_files` to show the dashboard HTML to the user.

### AI Content Analysis

The dashboard generator automatically runs `analyze_content.py` to produce qualitative analysis sections driven by real score data:

| Section | Logic |
|---------|-------|
| Collaboration bottlenecks | Low peer scores + peer-sub gap > 0.5 on cross-team questions |
| Evaluation risks | Low discrimination evaluators (<=2 unique scores), high SD items (>1.5), management perception gaps |
| Strengths & highlights | Top 3 dimensions by peer score with supporting question details |
| Text mining clusters | Low-score and high-score capability clusters based on actual question averages |
| Quadrant positioning | Peer avg vs sub avg mapped to 4 quadrants with talent decision guidance |
| Comprehensive summary | Overall conclusion + data-driven development suggestions |
| IDP phase analysis | Each dimension as a development phase with covered indicators and avg scores |

Analysis is fully data-driven — no hardcoded content. Different score distributions produce different analytical conclusions.

### Chart.js Dependency

The generated dashboard loads Chart.js from CDN:
```
https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js
```

No local installation needed.

---

## Question Bank Format (Auto-Detection)

This skill uses a **flexible parser** — no fixed sheet names or column positions. The Excel file needs at minimum these elements:

### Sheet 1: Question Bank (auto-detected)

**Identity info (optional, any order):**
- A row starting with `被评价人：` → subject name
- A row starting with `职级：` or `职位：` → title
- Before the first dimension, a plain text row (>=4 chars, not a question) → table name

**Dimensions:**
- Plain Chinese title (2-8 characters), on its own row
- Examples: `战略思维`, `团队管理`, `执行落地`

**Questions:**
- Must contain a numbering prefix followed by description
- Supported numbering: `一、二、三` / `1. 2. 3.` / `①②③`
- Optional tag in parentheses at end: `一、能分析业务趋势。（战略视野）`
- Each question gets an auto-incrementing ID (Q1, Q2, Q3...)

### Sheet 2: Evaluator List (auto-detected)

- Header row with keywords like `级别/关系/人员/姓名/职位`
- Data rows with `上级` / `平级` / `下级` in the level column
- Same-level evaluators can leave the level cell blank (inherits from above)

### Sheet 3: Scoring Options (auto-detected)

- Rows containing `N分` format (e.g., `5分：...`)
- One row for "无法判断" / "N/A" / "不适用"

### Automatic Sheet Detection

Sheets are identified by both name keywords and content patterns:

| Role | Name keywords | Content pattern |
|------|--------------|-----------------|
| Question bank | 评价表/胜任力/问卷/360/环评 | >=2 dimension-like rows or >=3 question-like rows |
| Evaluators | 评价人/名单/人员 | "级别"/"关系" in header; "上级"/"平级"/"下级" in data |
| Scoring | 辅助/勿删/选项/评分 | >=2 rows with "N分" pattern or "无法判断" |

---

## Dashboard Output

The generated HTML includes both **data visualization** and **AI content analysis**:

### Data Visualization
- **KPI cards**: Overall average, highest/lowest dimension, subordinate vs peer comparison, largest standard deviation item
- **Dimension comparison**: Horizontal bar chart (peer vs subordinate by dimension) + Radar chart (Chart.js)
- **Score list**: All questions sorted with individual averages and standard deviations
- **Heatmap table**: Evaluator x Question matrix with color-coded scores

### AI Content Analysis (auto-generated)
- **Collaboration bottlenecks**: Detects cross-team issues from low peer scores + perception gaps
- **Evaluation risks**: Identifies low-discrimination evaluators, high-disagreement items, management perception gaps
- **Strengths & highlights**: Top-performing dimensions with detailed question breakdowns
- **Text mining clusters**: Capability clusters based on actual score distributions
- **Quadrant positioning**: Peer vs subordinate mapping with talent decision guidance
- **Comprehensive summary**: Data-driven conclusions + actionable development suggestions
- **IDP phase analysis**: Per-dimension development phases with indicator coverage and averages
- **Dark theme**: Optimized for dark IDE/viewing environments

---

## Edge Cases & Troubleshooting

| Issue | Solution |
|-------|----------|
| Parser reports wrong metric count | Check dimension names are pure Chinese, 2-8 chars, no punctuation prefix |
| Question tag not detected | Ensure tag is in Chinese full-width parentheses `（...）` |
| Feishu form creation fails | Run `--dry-run` first; check lark-cli auth with `lark-cli auth status` |
| Base has no records | Tell user to share the form link and collect responses first |
| Dashboard data format mismatch | The processor auto-detects inline DATA format vs raw Base records |
