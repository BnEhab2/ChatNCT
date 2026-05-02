"""
face_debug_logger.py - Optional debug layer for the face verification pipeline.

This module saves intermediate artifacts, charts, and an HTML report so the
face verification pipeline can be inspected after each attempt.
"""

import base64
import html
import json
import os
import time
from typing import Dict, List

import cv2
import numpy as np


_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEBUG_LOGS_DIR = os.path.join(_ROOT_DIR, "debug_logs")


class FaceDebugLogger:
    """Handles saving debug artifacts to disk during face verification."""

    def __init__(self):
        self._session_dir = None
        self.current_subfolder = None

    def start_session(self, student_id: str, session_code: str = None):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        parts = [f"verify_{timestamp}"]
        if session_code:
            parts.append(f"session_{session_code}")
        parts.append(f"student_{student_id}")
        folder_name = "_".join(parts)

        self._session_dir = os.path.join(DEBUG_LOGS_DIR, folder_name)
        self.current_subfolder = None
        os.makedirs(self._session_dir, exist_ok=True)
        return self._session_dir

    def _get_dir(self, subfolder: str = None) -> str:
        if self._session_dir is None:
            self.start_session("unknown")
        target = self._session_dir
        if subfolder:
            target = os.path.join(self._session_dir, subfolder)
            os.makedirs(target, exist_ok=True)
        return target

    def save_image(self, step_name: str, image: np.ndarray, subfolder: str = None):
        if image is None:
            return
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.jpg")
            cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to save image {step_name}: {exc}")

    def save_text(self, step_name: str, text: str, subfolder: str = None):
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to save text {step_name}: {exc}")

    def save_array(self, step_name: str, arr: np.ndarray, subfolder: str = None):
        if arr is None:
            return
        try:
            base = os.path.join(self._get_dir(subfolder), step_name)
            np.save(f"{base}.npy", arr)
            with open(f"{base}.txt", "w", encoding="utf-8") as f:
                for val in arr.flatten():
                    f.write(f"{val:.8f}\n")
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to save array {step_name}: {exc}")

    def save_json(self, step_name: str, data: dict, subfolder: str = None):
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to save json {step_name}: {exc}")

    def save_cosine_details(
        self,
        dot_product: float,
        norm_a: float,
        norm_b: float,
        distance: float,
        threshold: float = None,
        subfolder: str = None,
    ):
        text = (
            f"dot_product: {dot_product}\n"
            f"norm_a: {norm_a}\n"
            f"norm_b: {norm_b}\n"
            f"cosine_distance: {distance}\n"
        )
        if threshold is not None:
            text += f"threshold: {threshold}\n"
            text += f"margin_to_threshold: {threshold - distance}\n"
        self.save_text("step_07_cosine_distance", text, subfolder)
        self.plot_cosine_distance(distance, threshold, subfolder)

    def save_registered_photo(self, photo_path: str, subfolder: str = None):
        if photo_path and os.path.exists(photo_path):
            try:
                img = cv2.imread(photo_path)
                if img is not None:
                    self.save_image("step_03_registered_photo", img, subfolder)
            except Exception as exc:
                print(f"[DEBUG-LOG] Failed to copy registered photo: {exc}")

    def plot_cosine_distance(self, distance: float, threshold: float = None, subfolder: str = None):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(7, 3.8))
            ax.barh(["cosine distance"], [distance], color="#ef4444", height=0.45)
            if threshold is not None:
                ax.axvline(threshold, color="#22c55e", linestyle="--", linewidth=2, label=f"threshold = {threshold:.3f}")
            ax.set_xlim(0, max(1.0, (threshold or 0) + 0.15, distance + 0.15))
            ax.set_xlabel("Distance")
            ax.set_title("Cosine Distance")
            ax.grid(axis="x", alpha=0.25)
            if threshold is not None:
                ax.legend(loc="lower right")
            ax.text(distance, 0, f" {distance:.4f}", va="center", ha="left", color="#f8fafc", fontweight="bold")
            self._save_matplotlib_figure(fig, "step_07b_cosine_distance_chart.png", subfolder)
        except ImportError:
            pass
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to plot cosine distance: {exc}")

    def plot_embeddings(self, live_emb: np.ndarray, reg_emb: np.ndarray, distance: float, subfolder: str = None):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from sklearn.decomposition import PCA

            data = np.vstack([live_emb.reshape(1, -1), reg_emb.reshape(1, -1)])
            pca = PCA(n_components=2)
            projected = pca.fit_transform(data)

            fig, ax = plt.subplots(figsize=(6, 5))
            ax.scatter(projected[0, 0], projected[0, 1], c="#38bdf8", s=130, label="Live Frame", marker="o", zorder=5)
            ax.scatter(projected[1, 0], projected[1, 1], c="#f97316", s=130, label="Registered Photo", marker="s", zorder=5)
            ax.plot(
                [projected[0, 0], projected[1, 0]],
                [projected[0, 1], projected[1, 1]],
                color="#94a3b8",
                linestyle="--",
                alpha=0.7,
            )
            ax.set_title(f"Embedding Projection (distance = {distance:.4f})")
            ax.legend()
            ax.grid(True, alpha=0.25)
            self._save_matplotlib_figure(fig, "step_09_embedding_projection.png", subfolder)
        except ImportError:
            pass
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to plot embeddings: {exc}")

    def plot_multi_frame_distances(self, distances: List[float], threshold: float = None, subfolder: str = None):
        if not distances:
            return
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            indices = list(range(1, len(distances) + 1))
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(indices, distances, marker="o", linewidth=2, color="#38bdf8")
            if threshold is not None:
                ax.axhline(threshold, color="#22c55e", linestyle="--", linewidth=2, label=f"threshold = {threshold:.3f}")
            ax.set_xticks(indices)
            ax.set_xlabel("Frame")
            ax.set_ylabel("Cosine Distance")
            ax.set_title("Per-frame Cosine Distance")
            ax.grid(True, alpha=0.25)
            if threshold is not None:
                ax.legend()
            self._save_matplotlib_figure(fig, "step_11_multi_frame_distances.png", subfolder)
        except ImportError:
            pass
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to plot frame distances: {exc}")

    def plot_motion_diffs(self, diffs: List[float], static_threshold: float = None, subfolder: str = None):
        if not diffs:
            return
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            labels = [f"{i}->{i+1}" for i in range(1, len(diffs) + 1)]
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(labels, diffs, color="#a78bfa")
            if static_threshold is not None:
                ax.axhline(static_threshold, color="#ef4444", linestyle="--", linewidth=2, label=f"static limit = {static_threshold:.2f}")
            ax.set_xlabel("Frame Pair")
            ax.set_ylabel("Average Pixel Difference")
            ax.set_title("Inter-frame Motion")
            ax.grid(axis="y", alpha=0.25)
            if static_threshold is not None:
                ax.legend()
            self._save_matplotlib_figure(fig, "step_12_motion_diffs.png", subfolder)
        except ImportError:
            pass
        except Exception as exc:
            print(f"[DEBUG-LOG] Failed to plot motion diffs: {exc}")

    def build_full_report(self, metadata: Dict[str, object] = None):
        if not self._session_dir or not os.path.isdir(self._session_dir):
            return None

        metadata = metadata or {}
        files = self._collect_session_files()
        report_path = os.path.join(self._session_dir, "FULL_REPORT.html")
        report_html = self._render_report_html(files, metadata)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        return report_path

    def _collect_session_files(self) -> Dict[str, object]:
        root_images = []
        root_texts = []
        root_json = []
        charts = []
        liveness_sections = []

        for current_root, dirnames, filenames in os.walk(self._session_dir):
            dirnames.sort()
            filenames.sort()
            rel_root = os.path.relpath(current_root, self._session_dir)
            rel_root = "" if rel_root == "." else rel_root.replace("\\", "/")

            images = []
            texts = []
            json_files = []

            for filename in filenames:
                rel_path = f"{rel_root}/{filename}" if rel_root else filename
                abs_path = os.path.join(current_root, filename)
                if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    item = {"name": filename, "rel_path": rel_path, "data_uri": self._to_data_uri(abs_path)}
                    if "plot" in filename or "chart" in filename or "graph" in filename:
                        charts.append(item)
                    else:
                        images.append(item)
                elif filename.lower().endswith(".txt"):
                    texts.append({"name": filename, "content": self._read_text(abs_path)})
                elif filename.lower().endswith(".json"):
                    json_files.append({"name": filename, "content": self._read_text(abs_path)})

            if rel_root.startswith("liveness_frame_"):
                liveness_sections.append({
                    "name": rel_root,
                    "images": images,
                    "texts": texts,
                    "json_files": json_files,
                })
            else:
                root_images.extend(images)
                root_texts.extend(texts)
                root_json.extend(json_files)

        liveness_sections.sort(key=lambda item: item["name"])
        return {
            "root_images": root_images,
            "root_texts": root_texts,
            "root_json": root_json,
            "charts": charts,
            "liveness_sections": liveness_sections,
            "total_files": sum(len(items) for items in [root_images, root_texts, root_json, charts]) + sum(
                len(section["images"]) + len(section["texts"]) + len(section["json_files"])
                for section in liveness_sections
            ),
        }

    def _render_report_html(self, files: Dict[str, object], metadata: Dict[str, object]) -> str:
        session_name = os.path.basename(self._session_dir.rstrip("\\/"))
        verdict = metadata.get("verdict", "DEBUG REPORT")
        verdict_class = "good" if str(metadata.get("verified", "")).lower() == "true" else "neutral"
        distance = metadata.get("distance", "N/A")
        threshold = metadata.get("threshold", "N/A")
        liveness_count = len(files["liveness_sections"])

        root_images_html = self._render_image_grid(files["root_images"], empty_label="No identity images saved.")
        charts_html = self._render_image_grid(files["charts"], empty_label="No charts saved.")
        root_texts_html = self._render_text_blocks(files["root_texts"] + files["root_json"], empty_label="No text logs saved.")
        liveness_html = self._render_liveness_sections(files["liveness_sections"])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Face Debug Report - {html.escape(session_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: Segoe UI, Tahoma, sans-serif; background: #09111f; color: #e5eefb; padding: 24px; line-height: 1.6; }}
  h1 {{ text-align: center; font-size: 30px; margin-bottom: 6px; color: #f8fafc; }}
  .subtitle {{ text-align: center; color: #94a3b8; margin-bottom: 24px; font-size: 14px; }}
  .verdict {{ text-align: center; font-size: 34px; font-weight: 800; margin: 18px 0 26px; }}
  .verdict.good {{ color: #22c55e; }}
  .verdict.bad {{ color: #ef4444; }}
  .verdict.neutral {{ color: #38bdf8; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }}
  .stat-card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 14px; padding: 14px 18px; }}
  .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; }}
  .value {{ font-size: 24px; font-weight: 700; color: #f8fafc; margin-top: 6px; }}
  .section {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 18px; padding: 20px; margin-bottom: 22px; }}
  .section h2 {{ font-size: 21px; margin-bottom: 14px; color: #cbd5e1; }}
  .section h3 {{ font-size: 16px; margin: 14px 0 10px; color: #93c5fd; }}
  .image-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }}
  .image-card {{ background: #111827; border: 1px solid #243041; border-radius: 14px; overflow: hidden; }}
  .image-card img {{ width: 100%; display: block; cursor: pointer; }}
  .caption {{ padding: 10px 12px; font-size: 13px; color: #cbd5e1; word-break: break-word; }}
  .text-block {{ background: #111827; border: 1px solid #243041; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; }}
  .filename {{ color: #93c5fd; font-weight: 700; margin-bottom: 8px; font-family: Consolas, monospace; }}
  pre {{ white-space: pre-wrap; word-break: break-word; color: #e2e8f0; font-family: Consolas, monospace; font-size: 13px; }}
  .empty {{ color: #94a3b8; font-style: italic; }}
  .liveness-section {{ background: #111827; border: 1px solid #243041; border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
  .lightbox {{ display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.88); z-index: 9999; align-items: center; justify-content: center; padding: 20px; }}
  .lightbox.active {{ display: flex; }}
  .lightbox img {{ max-width: 95%; max-height: 95%; border-radius: 12px; }}
</style>
</head>
<body>
<h1>Face Recognition Debug Report</h1>
<p class="subtitle">{html.escape(session_name)} | Generated: {html.escape(time.strftime("%Y-%m-%d %H:%M:%S"))}</p>
<div class="verdict {verdict_class}">{html.escape(str(verdict))}</div>

<div class="stats">
  <div class="stat-card"><div class="label">Distance</div><div class="value">{html.escape(str(distance))}</div></div>
  <div class="stat-card"><div class="label">Threshold</div><div class="value">{html.escape(str(threshold))}</div></div>
  <div class="stat-card"><div class="label">Total Files</div><div class="value">{files["total_files"]}</div></div>
  <div class="stat-card"><div class="label">Liveness Frames</div><div class="value">{liveness_count}</div></div>
</div>

<div class="section">
  <h2>Identity Images</h2>
  {root_images_html}
</div>

<div class="section">
  <h2>Charts</h2>
  {charts_html}
</div>

<div class="section">
  <h2>Text Logs</h2>
  {root_texts_html}
</div>

<div class="section">
  <h2>Liveness Frames</h2>
  {liveness_html}
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightboxImg" src="" alt="Preview">
</div>
<script>
function openLightbox(src) {{
  document.getElementById('lightboxImg').src = src;
  document.getElementById('lightbox').classList.add('active');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('active');
}}
document.addEventListener('keydown', function(event) {{
  if (event.key === 'Escape') closeLightbox();
}});
</script>
</body>
</html>"""

    def _render_image_grid(self, items: List[Dict[str, str]], empty_label: str) -> str:
        if not items:
            return f'<p class="empty">{html.escape(empty_label)}</p>'
        blocks = []
        for item in items:
            blocks.append(
                f"""<div class="image-card">
  <img src="{item["data_uri"]}" alt="{html.escape(item["name"])}" onclick="openLightbox(this.src)">
  <div class="caption">{html.escape(item["rel_path"])}</div>
</div>"""
            )
        return f'<div class="image-grid">{"".join(blocks)}</div>'

    def _render_text_blocks(self, items: List[Dict[str, str]], empty_label: str) -> str:
        if not items:
            return f'<p class="empty">{html.escape(empty_label)}</p>'
        return "".join(
            f"""<div class="text-block">
  <div class="filename">{html.escape(item["name"])}</div>
  <pre>{html.escape(item["content"])}</pre>
</div>"""
            for item in items
        )

    def _render_liveness_sections(self, sections: List[Dict[str, object]]) -> str:
        if not sections:
            return '<p class="empty">No liveness frames saved.</p>'
        parts = []
        for section in sections:
            parts.append(
                f"""<div class="liveness-section">
  <h3>{html.escape(section["name"])}</h3>
  {self._render_image_grid(section["images"], "No images for this frame.")}
  {self._render_text_blocks(section["texts"] + section["json_files"], "No logs for this frame.")}
</div>"""
            )
        return "".join(parts)

    def _save_matplotlib_figure(self, fig, filename: str, subfolder: str = None):
        path = os.path.join(self._get_dir(subfolder), filename)
        fig.savefig(path, dpi=120, bbox_inches="tight")
        fig.clf()

    def _read_text(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _to_data_uri(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"


debug_logger = FaceDebugLogger()
