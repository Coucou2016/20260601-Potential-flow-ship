# -*- coding: utf-8 -*-
"""MinerU cloud precision API (vlm) — literature/data only, one file at a time."""
import io
import json
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
TOKEN_FILE = BASE / ".mineru_token"
STATE_FILE = BASE / ".mineru_cloud_state.json"
LOG_FILE = BASE / "mineru_cloud.log"
OUT_ROOT = BASE / "parsed_markdown"
TABLE_FILE = BASE / "CLOUD_MINERU_PENDING_TABLE.md"

MAX_MB = 200
MAX_PAGES = 200
API_BATCH = "https://mineru.net/api/v4/file-urls/batch"
API_POLL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"

SUPPORTED = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_token() -> str:
    t = os.environ.get("MINERU_TOKEN", "").strip()
    if not t and TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not t:
        raise SystemExit("MINERU_TOKEN not set and .mineru_token missing")
    return t


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"items": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def has_md(stem: str, parent_rel: Path) -> bool:
    root = OUT_ROOT / parent_rel
    if not root.exists():
        return False
    for p in root.rglob("*.md"):
        if p.stem == stem or p.stem.replace("_cloud_vlm", "") == stem:
            return True
    return False


def pdf_twin_has_md(path: Path) -> bool:
    if path.suffix.lower() not in {".ppt", ".pptx", ".doc", ".docx"}:
        return False
    pdf = path.with_suffix(".pdf")
    if not pdf.exists():
        return False
    rel = pdf.relative_to(BASE)
    return has_md(pdf.stem, rel.parent)


def win_long(path: Path) -> str:
    resolved = path.resolve()
    s = str(resolved)
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + s
    return s


def safe_makedirs(path: Path):
    os.makedirs(win_long(path), exist_ok=True)


def safe_extract_zip(zf: zipfile.ZipFile, out_dir: Path):
    safe_makedirs(out_dir)
    for info in zf.infolist():
        dest = out_dir / info.filename
        if info.is_dir() or info.filename.endswith("/"):
            safe_makedirs(dest)
            continue
        safe_makedirs(dest.parent)
        with zf.open(info) as src, open(win_long(dest), "wb") as dst:
            shutil.copyfileobj(src, dst)


def page_count(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception as e:
        log(f"page_count fail {path.name}: {e}")
        return None


def is_real_pdf(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return True
    with path.open("rb") as f:
        return f.read(5).startswith(b"%PDF")


def collect_targets():
    done, pending, skip = [], [], []
    for area in ("literature", "data", "code"):
        d = BASE / area
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext not in SUPPORTED:
                continue
            rel = p.relative_to(BASE)
            if has_md(p.stem, rel.parent):
                done.append(rel)
                continue
            if pdf_twin_has_md(p):
                done.append(rel)
                continue
            if ext == ".pdf" and not is_real_pdf(p):
                skip.append((rel, "fake_pdf_html_stub"))
                continue
            pending.append(p)
    return done, pending, skip


def classify(p: Path):
    size_mb = p.stat().st_size / (1024 * 1024)
    pages = page_count(p)
    reasons = []
    if size_mb > MAX_MB:
        reasons.append(f"size_{size_mb:.1f}MB>{MAX_MB}MB")
    if pages is not None and pages > MAX_PAGES:
        reasons.append(f"pages_{pages}>{MAX_PAGES}")
    return size_mb, pages, reasons


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


def upload_and_parse(token: str, path: Path, data_id: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "files": [{"name": path.name, "data_id": data_id}],
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
    log(f"uploaded {path.name} batch_id={batch_id}")
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


def save_zip_result(path: Path, zip_url: str):
    rel = path.relative_to(BASE)
    out_dir = OUT_ROOT / rel.parent / path.stem / "cloud_vlm"
    safe_makedirs(out_dir)
    zr = _request_with_retry(
        lambda: requests.get(zip_url, timeout=600), "download zip", retries=5
    )
    zr.raise_for_status()
    zpath = out_dir / "result.zip"
    with open(win_long(zpath), "wb") as f:
        f.write(zr.content)
    with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
        safe_extract_zip(zf, out_dir)
    # normalize: copy full.md to stem_cloud_vlm.md
    full_md = out_dir / "full.md"
    if not full_md.exists():
        for cand in out_dir.rglob("*.md"):
            if cand.name.lower() in ("full.md", f"{path.stem}.md"):
                full_md = cand
                break
    target = out_dir / f"{path.stem}_cloud_vlm.md"
    if full_md.exists():
        with open(win_long(full_md), "rb") as src, open(win_long(target), "wb") as dst:
            shutil.copyfileobj(src, dst)
    log(f"saved {target}")


def write_table(eligible, over_limit, skipped, state):
    lines = [
        "# MinerU Cloud API — file status",
        "",
        f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Within limits (processed or queued)",
        "| File | Size (MB) | Pages | Status |",
        "|------|-----------|-------|--------|",
    ]
    for p, size_mb, pages, st in eligible:
        lines.append(f"| `{p.relative_to(BASE)}` | {size_mb:.2f} | {pages or 'n/a'} | {st} |")
    lines += ["", "## Over API limits (need split or local)", "| File | Size (MB) | Pages | Reason |", "|------|-----------|-------|--------|"]
    for p, size_mb, pages, reasons in over_limit:
        lines.append(f"| `{p.relative_to(BASE)}` | {size_mb:.2f} | {pages or 'n/a'} | {', '.join(reasons)} |")
    lines += ["", "## Skipped", "| File | Reason |", "|------|--------|"]
    for rel, reason in skipped:
        lines.append(f"| `{rel}` | {reason} |")
    TABLE_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    token = load_token()
    state = load_state()
    done_rel, pending, skipped = collect_targets()
    log(f"already_done={len(done_rel)} pending={len(pending)} skipped={len(skipped)}")

    eligible = []
    over_limit = []
    for p in pending:
        size_mb, pages, reasons = classify(p)
        key = str(p.relative_to(BASE)).replace("\\", "/")
        if reasons:
            over_limit.append((p, size_mb, pages, reasons))
            state["items"].setdefault(key, {"status": "over_limit", "reasons": reasons})
        else:
            eligible.append((p, size_mb, pages, state["items"].get(key, {}).get("status", "pending")))

    write_table(eligible, over_limit, skipped, state)
    save_state(state)

    for p, size_mb, pages, _ in eligible:
        key = str(p.relative_to(BASE)).replace("\\", "/")
        if state["items"].get(key, {}).get("status") == "ok":
            log(f"SKIP ok {key}")
            continue
        data_id = re.sub(r"[^A-Za-z0-9._-]", "_", key)[:120]
        try:
            log(f"START cloud {key} ({size_mb:.1f}MB pages={pages})")
            batch_id = upload_and_parse(token, p, data_id)
            result = poll_batch(token, batch_id)
            zip_url = result.get("full_zip_url")
            if not zip_url:
                raise RuntimeError("no full_zip_url in result")
            save_zip_result(p, zip_url)
            state["items"][key] = {
                "status": "ok",
                "batch_id": batch_id,
                "pages": pages,
                "size_mb": round(size_mb, 2),
            }
            save_state(state)
            write_table(
                [(x[0], x[1], x[2], state["items"].get(str(x[0].relative_to(BASE)).replace('\\','/'), {}).get("status", "pending")) for x in eligible],
                over_limit,
                skipped,
                state,
            )
        except Exception as e:
            log(f"FAIL {key}: {e}")
            state["items"][key] = {"status": "failed", "error": str(e)}
            save_state(state)

    log("ALL DONE")


if __name__ == "__main__":
    main()
