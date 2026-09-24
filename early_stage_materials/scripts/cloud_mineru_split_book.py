# -*- coding: utf-8 -*-
"""MinerU cloud vlm — split large PDFs via page_ranges, merge chunk Markdown."""
import argparse
import io
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
TOKEN_FILE = BASE / ".mineru_token"
STATE_FILE = BASE / ".mineru_cloud_molland_state.json"
LOG_FILE = BASE / "mineru_cloud_molland.log"
OUT_ROOT = BASE / "parsed_markdown"
TABLE_FILE = BASE / "CLOUD_MINERU_PENDING_TABLE.md"

DEFAULT_PDF = BASE / "literature" / "textbooks_surveys" / "Molland_Ship_Resistance_Propulsion_BOOK.pdf"

API_BATCH = "https://mineru.net/api/v4/file-urls/batch"
API_POLL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"

CHUNKS = [
    {"part": "part_01", "page_range": "1-200", "label": "1-200"},
    {"part": "part_02", "page_range": "201-400", "label": "201-400"},
    {"part": "part_03", "page_range": "401-563", "label": "401-563"},
]

IMG_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_token() -> str:
    t = os.environ.get("MINERU_TOKEN", "").strip()
    if not t and TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not t:
        raise SystemExit("MINERU_TOKEN not set and .mineru_token missing")
    return t


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"pdf": None, "chunks": {}, "merge": {}}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _request_with_retry(fn, label: str, retries: int = 5):
    err = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            err = e
            wait = 5 * (i + 1)
            log(f"retry {i+1}/{retries} {label}: {e}; sleep {wait}s")
            time.sleep(wait)
    raise err


def cloud_vlm_root(pdf: Path) -> Path:
    rel = pdf.relative_to(BASE)
    return OUT_ROOT / rel.parent / pdf.stem / "cloud_vlm"


def chunk_dir(pdf: Path, part: str) -> Path:
    return cloud_vlm_root(pdf) / "chunks" / part


def upload_and_parse(token: str, path: Path, data_id: str, page_range: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "files": [{"name": path.name, "data_id": data_id, "page_ranges": page_range}],
        "model_version": "vlm",
        "enable_formula": True,
        "enable_table": True,
        "language": "en" if re.search(r"[A-Za-z]{4}", path.stem) else "ch",
    }

    def _post():
        r = requests.post(API_BATCH, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        return r

    r = _request_with_retry(_post, "file-urls/batch")
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"batch apply failed: {body}")
    batch_id = body["data"]["batch_id"]
    upload_url = body["data"]["file_urls"][0]

    def _put():
        with path.open("rb") as f:
            up = requests.put(upload_url, data=f, timeout=600)
        if up.status_code not in (200, 201):
            raise RuntimeError(f"upload failed status={up.status_code}")
        return up

    _request_with_retry(_put, "upload")
    log(f"uploaded {path.name} page_ranges={page_range} batch_id={batch_id}")
    return batch_id


def poll_batch(token: str, batch_id: str, timeout_sec: int = 3600) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
    url = API_POLL.format(batch_id=batch_id)
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        def _get():
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            return r

        r = _request_with_retry(_get, f"poll {batch_id}", retries=3)
        body = r.json()
        if body.get("code") != 0:
            raise RuntimeError(f"poll error: {body}")
        results = body["data"].get("extract_result", [])
        if not results:
            time.sleep(8)
            continue
        item = results[0]
        state = item.get("state")
        log(f"poll {batch_id} state={state}")
        if state == "done":
            return item
        if state == "failed":
            raise RuntimeError(item.get("err_msg") or "failed")
        time.sleep(10)
    raise TimeoutError(f"poll timeout batch_id={batch_id}")


def save_zip_result(pdf: Path, zip_url: str, part: str):
    out_dir = chunk_dir(pdf, part)
    out_dir.mkdir(parents=True, exist_ok=True)
    zr = _request_with_retry(
        lambda: requests.get(zip_url, timeout=600), "download zip", retries=5
    )
    zr.raise_for_status()
    zpath = out_dir / "result.zip"
    zpath.write_bytes(zr.content)
    with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
        zf.extractall(out_dir)
    full_md = out_dir / "full.md"
    if not full_md.exists():
        for cand in out_dir.rglob("*.md"):
            if cand.name.lower() in ("full.md", f"{pdf.stem}.md"):
                full_md = cand
                break
    target = out_dir / f"{pdf.stem}_cloud_vlm.md"
    if full_md.exists():
        shutil.copy2(full_md, target)
    log(f"saved chunk {part} -> {out_dir}")


def find_chunk_md(out_dir: Path, stem: str) -> Path | None:
    for cand in (out_dir / "full.md", out_dir / f"{stem}_cloud_vlm.md"):
        if cand.exists():
            return cand
    mds = sorted(out_dir.rglob("*.md"))
    return mds[0] if mds else None


def resolve_image_src(chunk_out: Path, ref: str) -> Path | None:
    ref = ref.strip()
    if ref.startswith("http://") or ref.startswith("https://"):
        return None
    p = Path(ref.replace("\\", "/"))
    if p.is_absolute():
        return p if p.exists() else None
    for base in (chunk_out, chunk_out / "images"):
        candidate = (chunk_out / p).resolve()
        if candidate.exists():
            return candidate
        if not str(p).startswith("images/"):
            candidate = (chunk_out / "images" / p.name).resolve()
            if candidate.exists():
                return candidate
    direct = chunk_out / ref
    if direct.exists():
        return direct
    images = chunk_out / "images" / Path(ref).name
    if images.exists():
        return images
    return None


def merge_chunks(pdf: Path) -> Path:
    stem = pdf.stem
    root = cloud_vlm_root(pdf)
    merged_images = root / "images"
    merged_images.mkdir(parents=True, exist_ok=True)
    seen_names: dict[str, str] = {}
    parts_md: list[str] = []

    for chunk in CHUNKS:
        part = chunk["part"]
        out_dir = chunk_dir(pdf, part)
        md_path = find_chunk_md(out_dir, stem)
        if not md_path:
            raise FileNotFoundError(f"no markdown in {out_dir}")
        content = md_path.read_text(encoding="utf-8")
        part_num = part.replace("part_", "")

        def _rewrite_ref(m: re.Match) -> str:
            prefix, ref, suffix = m.group(1), m.group(2), m.group(3)
            src = resolve_image_src(out_dir, ref)
            if src is None:
                return m.group(0)
            fname = src.name
            if fname in seen_names:
                dest_name = seen_names[fname]
            else:
                dest_name = fname
                dest = merged_images / dest_name
                if dest.exists():
                    dest_name = f"part{part_num}_{fname}"
                    dest = merged_images / dest_name
                shutil.copy2(src, dest)
                seen_names[fname] = dest_name
            return f"{prefix}images/{dest_name}{suffix}"

        content = IMG_REF_RE.sub(_rewrite_ref, content)
        parts_md.append(f"<!-- pages {chunk['label']} -->\n\n{content.rstrip()}")

    merged_path = root / f"{stem}_cloud_vlm.md"
    merged_path.write_text("\n\n".join(parts_md) + "\n", encoding="utf-8")
    log(f"merged -> {merged_path} ({merged_path.stat().st_size} bytes)")
    return merged_path


def process_chunk(token: str, pdf: Path, chunk: dict, state: dict) -> str:
    part = chunk["part"]
    page_range = chunk["page_range"]
    key = str(pdf.relative_to(BASE)).replace("\\", "/")
    chunk_state = state.setdefault("chunks", {}).setdefault(part, {})

    if chunk_state.get("status") == "ok" and find_chunk_md(chunk_dir(pdf, part), pdf.stem):
        log(f"SKIP ok {part} pages={page_range}")
        return "ok"

    data_id = re.sub(r"[^A-Za-z0-9._-]", "_", f"{key}_{part}")[:120]
    try:
        log(f"START {part} pages={page_range}")
        batch_id = upload_and_parse(token, pdf, data_id, page_range)
        chunk_state["batch_id"] = batch_id
        chunk_state["page_range"] = page_range
        chunk_state["status"] = "processing"
        save_state(state)

        result = poll_batch(token, batch_id)
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise RuntimeError("no full_zip_url in result")
        save_zip_result(pdf, zip_url, part)
        chunk_state["status"] = "ok"
        chunk_state.pop("error", None)
        save_state(state)
        return "ok"
    except Exception as e:
        log(f"FAIL {part}: {e}")
        chunk_state["status"] = "failed"
        chunk_state["error"] = str(e)
        save_state(state)
        return "failed"


def update_pending_table(pdf: Path, note: str):
    if not TABLE_FILE.exists():
        return
    rel = pdf.relative_to(BASE)
    text = TABLE_FILE.read_text(encoding="utf-8")
    row_pat = re.compile(
        rf"\| `{re.escape(str(rel).replace(chr(92), chr(92)+chr(92)))}` \|[^\n]+\n"
    )
    completed_row = (
        f"| `{rel}` | 563 | "
        f"`parsed_markdown/.../{pdf.stem}_cloud_vlm.md` | ok — {note} |\n"
    )
    if "## Over API limits" in text and str(rel) in text:
        text = row_pat.sub("", text)
        insert_at = text.find("## Skipped")
        if insert_at == -1:
            text += "\n## Completed (split merge)\n\n" + completed_row
        else:
            block = "## Completed (split merge)\n\n| File | Pages | Output | Status |\n|------|-------|--------|--------|\n"
            if "## Completed (split merge)" not in text:
                text = text[:insert_at] + block + completed_row + text[insert_at:]
            else:
                pos = text.find("|------|-------|--------|--------|")
                if pos != -1:
                    end = text.find("\n", pos)
                    text = text[: end + 1] + completed_row + text[end + 1 :]
    text = re.sub(
        r"Updated: .+",
        f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        text,
        count=1,
    )
    TABLE_FILE.write_text(text, encoding="utf-8")
    log("updated CLOUD_MINERU_PENDING_TABLE.md")


def main():
    parser = argparse.ArgumentParser(description="MinerU cloud split-book processor")
    parser.add_argument("pdf", nargs="?", default=str(DEFAULT_PDF), help="PDF path")
    parser.add_argument("--merge-only", action="store_true", help="merge existing chunks only")
    args = parser.parse_args()

    pdf = Path(args.pdf).resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")

    token = load_token()
    state = load_state()
    state["pdf"] = str(pdf.relative_to(BASE)).replace("\\", "/")
    save_state(state)

    results: dict[str, str] = {}
    if not args.merge_only:
        for chunk in CHUNKS:
            results[chunk["part"]] = process_chunk(token, pdf, chunk, state)

    all_ok = all(
        state.get("chunks", {}).get(c["part"], {}).get("status") == "ok"
        for c in CHUNKS
    )
    merged_path = None
    if all_ok:
        try:
            merged_path = merge_chunks(pdf)
            line_count = len(merged_path.read_text(encoding="utf-8").splitlines())
            state["merge"] = {
                "status": "ok",
                "output": str(merged_path.relative_to(BASE)).replace("\\", "/"),
                "lines": line_count,
                "bytes": merged_path.stat().st_size,
            }
            save_state(state)
            update_pending_table(pdf, "split 3 parts merged")
            log(f"MERGE OK lines={line_count} path={merged_path}")
        except Exception as e:
            log(f"MERGE FAIL: {e}")
            state["merge"] = {"status": "failed", "error": str(e)}
            save_state(state)
            sys.exit(1)
    else:
        log("merge skipped — not all chunks ok")
        for part, st in results.items():
            log(f"  {part}: {st}")
        sys.exit(1)

    log("ALL DONE")
    for part in CHUNKS:
        st = state.get("chunks", {}).get(part["part"], {}).get("status", "unknown")
        log(f"  {part['part']} ({part['label']}): {st}")
    if merged_path:
        log(f"  merged: {merged_path} ({merged_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
