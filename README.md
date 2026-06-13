# Academic Integrity Checker / 学术诚信检查器

[![952a6a598a814f19a3add8645f5fbeca.png](https://i.postimg.cc/BZr2f4dj/952a6a598a814f19a3add8645f5fbeca.png)](https://postimg.cc/6Th8dJ6K)

## English

Academic Integrity Checker is a Codex skill for pre-submission screening of scholarly manuscripts. It helps authors, reviewers, and editors identify common integrity risks before journal submission.

### Purpose

The skill is designed to flag preventable risks, not to adjudicate misconduct. It uses neutral language such as "risk", "inconsistency", "missing disclosure", and "requires verification".

### Method

The checker combines:

- manuscript text screening for missing declarations, ethics statements, data/code availability, AI-use disclosure, over-strong claims, and statistical/sample-size warning signs;
- figure screening for exact duplicates, visually near-duplicate images, and cropped/resized/embedded duplicate panels;
- online reference verification through Crossref and DOI.org when `--online-references` is enabled;
- comparison against a small curated set of proven misconduct/retraction-risk cases;
- optional local overlap checking against prior manuscripts or source files.

### Main Outputs

The Markdown report includes:

- Executive Summary
- risk score and submission recommendation
- severity table
- Priority Actions
- evidence tables
- Interpretation Notes
- Scope And Limits

Findings are classified as `critical`, `high`, `medium`, or `low`.

### Quick Start

```powershell
python academic-integrity-checker\scripts\check_manuscript.py manuscript.docx --format markdown
```

With figure and online reference checks:

```powershell
python academic-integrity-checker\scripts\check_manuscript.py manuscript.docx --figures figures --online-references --max-references 120 --format markdown
```

Supported manuscript text inputs: `.txt`, `.md`, `.docx`. For PDFs, extract text and figures first, then pass the extracted files to the checker.

### Important Limits

This tool cannot prove misconduct, originality, consent validity, or data authenticity. Online reference checks depend on third-party metadata quality. Unresolved references and image-similarity hits require human review.

## 中文

Academic Integrity Checker 是一个用于投稿前学术诚信筛查的 Codex skill。它可以帮助作者、审稿人和编辑在投稿前发现常见的学术诚信风险。

### 目的

该工具用于预警和预防，而不是判定学术不端。报告会使用中性表述，例如“风险”“不一致”“缺失声明”“需要核实”，避免直接做指控性判断。

### 方法

该检查器结合以下方法：

- 对稿件文本进行静态筛查，检查声明缺失、伦理说明、数据/代码可用性、AI 使用披露、过强结论、样本量或统计表述异常；
- 对图片进行筛查，识别完全重复、视觉近似重复、裁剪/缩放/嵌入式重复图像；
- 启用 `--online-references` 后，通过 Crossref 和 DOI.org 联网核验参考文献；
- 与小型已证实学术不端/撤稿风险案例集进行比对；
- 可选地与本地既往稿件或来源文件进行文本重叠检查。

### 主要输出

Markdown 报告包括：

- 执行摘要
- 风险评分与投稿建议
- 严重程度统计表
- 优先处理事项
- 证据表格
- 解释说明
- 范围与限制

发现项分为 `critical`、`high`、`medium`、`low` 四个级别。

### 快速使用

```powershell
python academic-integrity-checker\scripts\check_manuscript.py manuscript.docx --format markdown
```

启用图片和联网参考文献检查：

```powershell
python academic-integrity-checker\scripts\check_manuscript.py manuscript.docx --figures figures --online-references --max-references 120 --format markdown
```

支持的文本稿件格式包括 `.txt`、`.md`、`.docx`。如果是 PDF，请先提取文本和图片，再传入检查器。

### 重要限制

该工具不能证明学术不端、原创性、知情同意有效性或数据真实性。联网参考文献核验依赖第三方元数据质量。无法验证的参考文献和图片相似性结果都需要人工复核。
