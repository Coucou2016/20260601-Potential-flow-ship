# -*- coding: utf-8 -*-
"""
MinerU Cloud API — PDF → Markdown 完整可复用示例

流程:
  1) POST /api/v4/file-urls/batch  申请上传 URL + batch_id
  2) PUT  upload_url               上传本地 PDF
  3) GET  /api/v4/extract-results/batch/{batch_id}  轮询直到 done
  4) GET  full_zip_url             下载结果 zip，提取 Markdown

限制 (精准解析 API):
  - 单文件 ≤ 200 MB
  - 单次解析 ≤ 200 页（可用 page_ranges 分段）
  - 支持: pdf / doc / docx / ppt / pptx / xls / xlsx

依赖:
  pip install requests
  # 可选，用于检查页数: pip install pypdf

用法:
  # 环境变量或同目录 .mineru_token 放 Token
  set MINERU_TOKEN=你的JWT

  # 单文件（≤200 页）
  python mineru_api_example.py paper.pdf -o ./out

  # 大文件分段（例: 563 页 → 1-200,201-400,401-563）
  python mineru_api_example.py book.pdf -o ./out --page-ranges 1-200,201-400,401-563

  # 作为库调用
  from mineru_api_example import convert_pdf
  md_path = convert_pdf("paper.pdf", "out", token="...")
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

import requests

API_BATCH = "https://mineru.net/api/v4/file-urls/batch"
API_POLL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"

MAX_MB = 200
MAX_PAGES = 200


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_token(token: str | None = None) -> str:
    if token and token.strip():
        return token.strip()
    env = os.environ.get("MINERU_TOKEN", "").strip()
    if env:
        return env
    for cand in (Path(".mineru_token"), Path(__file__).with_name(".mineru_token")):
        if cand.exists():
            t = cand.read_text(encoding="utf-8").strip()
            if t:
                return t
    raise SystemExit(
        "未找到 Token。请设置环境变量 MINERU_TOKEN，"
        "或在当前目录创建 .mineru_token 文件（一行 JWT）。"
        "申请: https://mineru.net/apiManage/token"
    )


def request_with_retry(fn, label: str, retries: int = 5):
    """网络抖动 / SSL 偶发失败时自动重试。"""
    err = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            err = e
            wait = 5 * (i + 1)
            print(f"  retry {i + 1}/{retries} {label}: {e}; sleep {wait}s")
            time.sleep(wait)
    raise err


def page_count(pdf: Path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf)).pages)
    except Exception:
        return None


def check_limits(pdf: Path, page_ranges: str | None) -> None:
    size_mb = pdf.stat().st_size / (1024 * 1024)
    if size_mb > MAX_MB:
        raise SystemExit(f"文件过大: {size_mb:.1f} MB > {MAX_MB} MB")
    pages = page_count(pdf)
    if pages is not None and pages > MAX_PAGES and not page_ranges:
        raise SystemExit(
            f"页数 {pages} > {MAX_PAGES}，请用 --page-ranges 分段，例如:\n"
            f"  --page-ranges 1-200,201-400,401-{pages}"
        )


# ---------------------------------------------------------------------------
# core API
# ---------------------------------------------------------------------------

def apply_batch(
    token: str,
    filename: str,
    data_id: str,
    *,
    page_ranges: str | None = None,
    language: str = "en",
    model_version: str = "vlm",
) -> tuple[str, str]:
    """申请上传 URL。返回 (batch_id, upload_url)。"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    file_item = {"name": filename, "data_id": data_id}
    if page_ranges:
        file_item["page_ranges"] = page_ranges  # 如 "1-200" 或 "2,4-6"

    payload = {
        "files": [file_item],
        "model_version": model_version,  # pipeline | vlm | MinerU-HTML
        "enable_formula": True,
        "enable_table": True,
        "language": language,  # en | ch
    }

    def _post():
        r = requests.post(API_BATCH, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        return r

    body = request_with_retry(_post, "file-urls/batch").json()
    if body.get("code") != 0:
        raise RuntimeError(f"申请上传失败: {body}")
    batch_id = body["data"]["batch_id"]
    upload_url = body["data"]["file_urls"][0]
    return batch_id, upload_url


def upload_file(upload_url: str, pdf: Path) -> None:
    def _put():
        with pdf.open("rb") as f:
            r = requests.put(upload_url, data=f, timeout=600)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"上传失败 status={r.status_code} body={r.text[:200]}")
        return r

    request_with_retry(_put, "upload")


def poll_batch(token: str, batch_id: str, timeout_sec: int = 3600) -> dict:
    """轮询直到 state=done，返回 extract_result[0]。"""
    headers = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
    url = API_POLL.format(batch_id=batch_id)
    t0 = time.time()

    while time.time() - t0 < timeout_sec:
        def _get():
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            return r

        body = request_with_retry(_get, f"poll {batch_id}", retries=3).json()
        if body.get("code") != 0:
            raise RuntimeError(f"轮询失败: {body}")

        results = body["data"].get("extract_result") or []
        if not results:
            time.sleep(8)
            continue

        item = results[0]
        state = item.get("state")
        print(f"  poll {batch_id} state={state}")
        if state == "done":
            return item
        if state == "failed":
            raise RuntimeError(item.get("err_msg") or "解析失败")
        time.sleep(10)

    raise TimeoutError(f"轮询超时 batch_id={batch_id}")


def download_and_extract(zip_url: str, out_dir: Path) -> Path:
    """下载结果 zip，解压，返回主 Markdown 路径。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    def _get():
        r = requests.get(zip_url, timeout=600)
        r.raise_for_status()
        return r

    zr = request_with_retry(_get, "download zip")
    zpath = out_dir / "result.zip"
    zpath.write_bytes(zr.content)

    with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
        zf.extractall(out_dir)

    # 优先 full.md，其次任意 .md
    full = out_dir / "full.md"
    if full.exists():
        return full
    for cand in out_dir.rglob("*.md"):
        return cand
    raise FileNotFoundError(f"zip 中未找到 Markdown: {out_dir}")


# ---------------------------------------------------------------------------
# high-level API
# ---------------------------------------------------------------------------

def convert_one(
    pdf: Path,
    out_dir: Path,
    token: str,
    *,
    page_ranges: str | None = None,
    language: str = "en",
    model_version: str = "vlm",
) -> Path:
    """
    转换单个 PDF（或指定 page_ranges 的一段）。
    返回写出的 Markdown 路径。
    """
    pdf = Path(pdf).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data_id = re.sub(r"[^A-Za-z0-9._-]", "_", pdf.stem)[:120]
    suffix = f"_{page_ranges.replace(',', '_').replace('-', '_')}" if page_ranges else ""
    part_dir = out_dir / f"{pdf.stem}{suffix}"
    part_dir.mkdir(parents=True, exist_ok=True)

    print(f"START {pdf.name} page_ranges={page_ranges or 'all'}")
    batch_id, upload_url = apply_batch(
        token,
        pdf.name,
        data_id + suffix,
        page_ranges=page_ranges,
        language=language,
        model_version=model_version,
    )
    upload_file(upload_url, pdf)
    print(f"  uploaded batch_id={batch_id}")

    result = poll_batch(token, batch_id)
    zip_url = result.get("full_zip_url")
    if not zip_url:
        raise RuntimeError(f"结果无 full_zip_url: {result}")

    md_src = download_and_extract(zip_url, part_dir)
    md_dst = part_dir / f"{pdf.stem}_mineru.md"
    shutil.copy2(md_src, md_dst)
    print(f"SAVED {md_dst}")
    return md_dst


def merge_markdowns(md_paths: list[Path], out_path: Path, labels: list[str] | None = None) -> Path:
    """按顺序拼接多分卷 Markdown。"""
    parts = []
    for i, md in enumerate(md_paths):
        label = labels[i] if labels else f"part_{i + 1}"
        parts.append(f"<!-- {label} -->\n\n")
        parts.append(md.read_text(encoding="utf-8"))
        if not parts[-1].endswith("\n"):
            parts.append("\n")
        parts.append("\n")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(parts), encoding="utf-8")
    print(f"MERGED {out_path}")
    return out_path


def convert_pdf(
    pdf: str | Path,
    out_dir: str | Path,
    *,
    token: str | None = None,
    page_ranges: str | None = None,
    language: str = "en",
    model_version: str = "vlm",
) -> Path:
    """
    高层入口：单文件或自动按逗号分隔的 page_ranges 分卷后合并。

    page_ranges 示例:
      None          → 整本一次解析（须 ≤200 页）
      "1-200"       → 只解析第 1–200 页
      "1-200,201-400,401-563" → 三段分别解析再合并
    """
    pdf = Path(pdf)
    out_dir = Path(out_dir)
    tok = load_token(token)
    check_limits(pdf, page_ranges)

    if not page_ranges or "," not in page_ranges:
        return convert_one(
            pdf, out_dir, tok,
            page_ranges=page_ranges,
            language=language,
            model_version=model_version,
        )

    ranges = [x.strip() for x in page_ranges.split(",") if x.strip()]
    md_paths = []
    for pr in ranges:
        md_paths.append(
            convert_one(
                pdf, out_dir, tok,
                page_ranges=pr,
                language=language,
                model_version=model_version,
            )
        )
    merged = out_dir / f"{pdf.stem}_mineru.md"
    return merge_markdowns(md_paths, merged, labels=[f"pages {r}" for r in ranges])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="MinerU Cloud API: PDF → Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("pdf", type=Path, help="输入 PDF 路径")
    ap.add_argument("-o", "--out", type=Path, default=Path("mineru_out"), help="输出目录")
    ap.add_argument("--token", default=None, help="API Token（默认读 MINERU_TOKEN / .mineru_token）")
    ap.add_argument(
        "--page-ranges",
        default=None,
        help='页码范围，如 "1-200" 或 "1-200,201-400,401-563"',
    )
    ap.add_argument("--language", default="en", choices=["en", "ch"])
    ap.add_argument(
        "--model",
        default="vlm",
        choices=["vlm", "pipeline", "MinerU-HTML"],
        help="vlm=精准解析（推荐）",
    )
    args = ap.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"文件不存在: {args.pdf}")

    convert_pdf(
        args.pdf,
        args.out,
        token=args.token,
        page_ranges=args.page_ranges,
        language=args.language,
        model_version=args.model,
    )


if __name__ == "__main__":
    main()
