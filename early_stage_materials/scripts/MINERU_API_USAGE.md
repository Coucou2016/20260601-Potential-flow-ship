# MinerU Cloud API 用法（PDF → Markdown）

可复用脚本：[`mineru_api_example.py`](./mineru_api_example.py)  
本仓库批量脚本：`cloud_mineru_convert.py`（批量）、`cloud_mineru_split_book.py`（大书分段）

---

## 1. 准备

```bash
pip install requests pypdf
```

1. 打开 [mineru.net Token 管理](https://mineru.net/apiManage/token) 创建 Token  
2. 任选一种方式提供 Token：

```bash
# Windows PowerShell
$env:MINERU_TOKEN = "eyJ..."

# 或写入文件（一行 JWT，勿提交到 Git）
echo eyJ... > .mineru_token
```

---

## 2. 一键转换（推荐）

### 单文件（≤200 页、≤200 MB）

```bash
python mineru_api_example.py paper.pdf -o ./out
```

输出示例：

```
out/paper/paper_mineru.md
out/paper/full.md
out/paper/result.zip
out/paper/images/   # 若有图
```

### 大文件（>200 页）— 分段再合并

```bash
python mineru_api_example.py book.pdf -o ./out --page-ranges 1-200,201-400,401-563
```

会生成各分段目录，并合并为：

```
out/book_mineru.md
```

### 中文文档 / 换模型

```bash
python mineru_api_example.py 论文.pdf -o ./out --language ch --model vlm
```

| `--model` | 说明 |
|-----------|------|
| `vlm` | 精准解析（公式友好，**推荐**） |
| `pipeline` | 通用流水线 |
| `MinerU-HTML` | HTML 向 |

---

## 3. 作为 Python 库调用

```python
from pathlib import Path
from mineru_api_example import convert_pdf

# 小文件
md = convert_pdf("paper.pdf", "out", language="en", model_version="vlm")
print(md.read_text(encoding="utf-8")[:500])

# 大文件分段
md = convert_pdf(
    "book.pdf",
    "out",
    page_ranges="1-200,201-400,401-563",
)
```

底层分步 API（需要更细控制时）：

```python
from mineru_api_example import (
    load_token, apply_batch, upload_file, poll_batch, download_and_extract,
)

token = load_token()
batch_id, upload_url = apply_batch(token, "paper.pdf", "job001", page_ranges=None)
upload_file(upload_url, Path("paper.pdf"))
item = poll_batch(token, batch_id)
md = download_and_extract(item["full_zip_url"], Path("out/paper"))
```

---

## 4. API 流程（官方 v4）

```
┌─────────────┐   POST /api/v4/file-urls/batch    ┌──────────────┐
│ 本地 PDF    │ ────────────────────────────────► │ batch_id +   │
│             │                                   │ upload_url   │
└─────────────┘                                   └──────┬───────┘
                                                         │
                                                         │ PUT upload_url
                                                         ▼
                                                  ┌──────────────┐
                                                  │ 云端自动提交  │
                                                  │ 解析任务      │
                                                  └──────┬───────┘
                                                         │
              GET /api/v4/extract-results/batch/{id}     │ 轮询
              state: pending → running → done            │
                                                         ▼
                                                  ┌──────────────┐
                                                  │ full_zip_url │
                                                  │ → Markdown   │
                                                  └──────────────┘
```

关键请求体示例：

```json
{
  "files": [
    {
      "name": "paper.pdf",
      "data_id": "my_job_001",
      "page_ranges": "1-200"
    }
  ],
  "model_version": "vlm",
  "enable_formula": true,
  "enable_table": true,
  "language": "en"
}
```

`page_ranges` 格式：

| 写法 | 含义 |
|------|------|
| `1-200` | 第 1–200 页 |
| `2,4-6` | 第 2、4、5、6 页 |
| `2--2` | 第 2 页到倒数第 2 页 |

---

## 5. 限制与注意

| 项 | 限制 |
|----|------|
| 文件大小 | ≤ 200 MB |
| 页数（单次） | ≤ 200 页（更大请分段） |
| Token | 勿提交仓库；聊天中暴露后请轮换 |
| 网络 | SSL 偶发失败 → 脚本已内置重试 |
| Windows 长路径 | 深目录解压可能失败，输出路径尽量短 |

不支持的旧格式（如伪装成 `.doc` 的 RTF）需先本地转 PDF/纯文本。

---

## 6. 与本仓库脚本的关系

| 脚本 | 用途 |
|------|------|
| `mineru_api_example.py` | **可拷贝到其他项目的最小完整示例** |
| `cloud_mineru_convert.py` | 本仓库批量：literature/data/code + 断点续跑 |
| `cloud_mineru_split_book.py` | 本仓库 Molland 等大书：分段 + 图片合并 |

复制到其他项目时，只需带走 `mineru_api_example.py` 和 Token 即可。
