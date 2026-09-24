"""Deterministically rebuild Sun (2007) Fig. 2.6 panel images from its PDF.

This is a source-PDF rasterization utility only.  It does not digitize curves,
compare output with historical JPEG files, or make an uncertainty claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = (
    REPOSITORY_ROOT
    / "benchmarks"
    / "sun2007_fig2_6_wedge_similarity"
    / "sun2007_boundary_element_method.pdf"
)
FIGURE_PAGE_INDEX_ZERO_BASED = 39
DEFAULT_RENDER_SCALE = 4.0
MANIFEST_FILENAME = "fig2_6_pdf_rebuild_manifest.json"


@dataclass(frozen=True)
class PanelSpec:
    """One fixed Fig. 2.6 crop in unrotated PDF-page points."""

    name: str
    filename: str
    crop_points: tuple[int, int, int, int]


# Coordinates use an origin at the rendered page's upper-left corner.  They
# include each plot's axes, labels, and legend while excluding neighbouring
# panels and the figure caption.
PANEL_SPECS = (
    PanelSpec("beta10_free_surface", "fig2_6_beta10_free_surface.png", (50, 78, 252, 230)),
    PanelSpec("beta10_pressure", "fig2_6_beta10_pressure.png", (248, 78, 460, 230)),
    PanelSpec("beta20_free_surface", "fig2_6_beta20_free_surface.png", (50, 244, 252, 396)),
    PanelSpec("beta20_pressure", "fig2_6_beta20_pressure.png", (248, 244, 460, 396)),
    PanelSpec("beta30_free_surface", "fig2_6_beta30_free_surface.png", (50, 409, 252, 561)),
    PanelSpec("beta30_pressure", "fig2_6_beta30_pressure.png", (248, 409, 460, 561)),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _distribution_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _crop_pixels(crop_points: tuple[int, int, int, int], scale: float) -> tuple[int, int, int, int]:
    return tuple(round(value * scale) for value in crop_points)  # type: ignore[return-value]


def _validate_crop(name: str, crop: tuple[int, int, int, int], image_size: tuple[int, int]) -> None:
    left, upper, right, lower = crop
    width, height = image_size
    if not (0 <= left < right <= width and 0 <= upper < lower <= height):
        raise ValueError(
            f"Crop for {name!r} is out of bounds for rendered page {width}x{height}: {crop}"
        )


def _render_page(pdf_path: Path, page_index: int, render_scale: float) -> tuple[Image.Image, int, tuple[float, float]]:
    document = pdfium.PdfDocument(pdf_path)
    try:
        page_count = len(document)
        if not 0 <= page_index < page_count:
            raise ValueError(
                f"PDF page index {page_index} is out of bounds for a {page_count}-page PDF "
                f"(valid range: 0..{page_count - 1})."
            )

        page = document[page_index]
        try:
            page_size_points = tuple(float(value) for value in page.get_size())
            bitmap = page.render(
                scale=render_scale,
                rotation=0,
                may_draw_forms=False,
            )
            try:
                # Copy the pixels before closing the Pdfium bitmap.  Saving an
                # RGB image with explicit PNG options avoids ambient metadata.
                bitmap_image = bitmap.to_pil()
                try:
                    rendered = Image.frombytes(
                        "RGB",
                        bitmap_image.size,
                        bitmap_image.convert("RGB").tobytes(),
                    )
                finally:
                    bitmap_image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()
    return rendered, page_count, page_size_points


def rebuild_from_pdf(
    pdf_path: Path | str,
    output_dir: Path | str,
    *,
    page_index: int = FIGURE_PAGE_INDEX_ZERO_BASED,
    render_scale: float = DEFAULT_RENDER_SCALE,
) -> Path:
    """Render one PDF page and write the six fixed Fig. 2.6 panel crops.

    Returns the path to the JSON manifest.  ``render_scale`` is pixels per
    PDF point; the default of 4.0 corresponds to 288 dpi.
    """

    source_pdf = Path(pdf_path)
    destination = Path(output_dir)
    if not source_pdf.is_file():
        raise FileNotFoundError(source_pdf)
    if not math.isfinite(render_scale) or render_scale <= 0:
        raise ValueError(f"render_scale must be a finite positive number, got {render_scale!r}")

    rendered_page, page_count, page_size_points = _render_page(
        source_pdf,
        page_index,
        render_scale,
    )
    try:
        crop_records: list[tuple[PanelSpec, tuple[int, int, int, int]]] = []
        for panel in PANEL_SPECS:
            crop = _crop_pixels(panel.crop_points, render_scale)
            _validate_crop(panel.name, crop, rendered_page.size)
            crop_records.append((panel, crop))

        destination.mkdir(parents=True, exist_ok=True)
        outputs: list[dict[str, object]] = []
        for panel, crop in crop_records:
            output_path = destination / panel.filename
            panel_image = rendered_page.crop(crop)
            try:
                stable_pixels = Image.frombytes("RGB", panel_image.size, panel_image.convert("RGB").tobytes())
                try:
                    stable_pixels.save(
                        output_path,
                        format="PNG",
                        optimize=False,
                        compress_level=9,
                    )
                finally:
                    stable_pixels.close()
            finally:
                panel_image.close()
            outputs.append(
                {
                    "panel": panel.name,
                    "filename": panel.filename,
                    "crop_points": list(panel.crop_points),
                    "crop_pixels": list(crop),
                    "size_px": [crop[2] - crop[0], crop[3] - crop[1]],
                    "sha256": _sha256(output_path),
                }
            )

        manifest = {
            "artifact": "Sun 2007 Fig. 2.6 source-PDF panel crops",
            "scope": (
                "Source-PDF rasterization only; no curve digitization, historical JPEG "
                "hash comparison, or digitization-uncertainty closure is asserted."
            ),
            "source_pdf": {
                "path": str(source_pdf),
                "sha256": _sha256(source_pdf),
                "page_index_zero_based": page_index,
                "page_count": page_count,
                "page_size_points": list(page_size_points),
            },
            "render": {
                "backend": "pypdfium2",
                "pypdfium2_version": _distribution_version("pypdfium2"),
                "pdfium_version": str(pdfium.version.PDFIUM_INFO),
                "pillow_version": Image.__version__,
                "scale_pixels_per_point": render_scale,
                "dpi": render_scale * 72.0,
                "rotation_degrees": 0,
                "may_draw_forms": False,
                "image_mode": "RGB",
                "rendered_page_size_px": list(rendered_page.size),
                "png": {"optimize": False, "compress_level": 9},
            },
            "crop_coordinate_space": (
                "PDF points and rendered-page pixels use an upper-left origin; crop boxes are "
                "[left, upper, right, lower] with right and lower bounds exclusive."
            ),
            "outputs": outputs,
        }
        manifest_path = destination / MANIFEST_FILENAME
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest_path
    finally:
        rendered_page.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild six Sun 2007 Fig. 2.6 panels directly from the source PDF."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help="Source PDF path (default: repository benchmark PDF).",
    )
    parser.add_argument("--out", type=Path, required=True, help="Directory for six PNGs and manifest.")
    parser.add_argument(
        "--page-index",
        type=int,
        default=FIGURE_PAGE_INDEX_ZERO_BASED,
        help="Zero-based source-PDF page index (default: 39).",
    )
    parser.add_argument(
        "--render-scale",
        type=float,
        default=DEFAULT_RENDER_SCALE,
        help="Pixels per PDF point (default: 4.0, equivalent to 288 dpi).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest_path = rebuild_from_pdf(
        args.pdf,
        args.out,
        page_index=args.page_index,
        render_scale=args.render_scale,
    )
    print(manifest_path)


if __name__ == "__main__":
    main()
