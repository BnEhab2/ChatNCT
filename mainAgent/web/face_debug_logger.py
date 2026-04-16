"""
face_debug_logger.py - Optional Debug Layer for Face Verification Pipeline

This module saves intermediate results of the face verification pipeline
to disk for debugging and analysis. It is completely optional.

HOW TO REMOVE:
  1. Delete this file (face_debug_logger.py)
  2. Remove all 'if DEBUG_FACE_PIPELINE:' blocks from face_verifier.py
     and attendance_server.py
  3. Remove the 'from ... import debug_logger' lines
  4. Set DEBUG_FACE_PIPELINE = False (or remove it)

The rest of the project will work exactly as before.

Output folder structure:
  debug_logs/
    verify_<timestamp>_student_<student_id>/
      step_01_raw_base64.txt
      step_02_decoded_frame.jpg
      step_03_registered_photo.jpg
      step_04_downscaled_live_frame.jpg
      step_05_live_embedding.npy + .txt
      step_06_registered_embedding.npy + .txt
      step_07_cosine_distance.txt
      step_08_decision.json
      step_09_plot_embeddings.png
      frame_1/ frame_2/ ...  (for multi-frame verification)
      multi_frame_summary.txt
"""

import os
import json
import time
import numpy as np
import cv2

# Root folder where all debug logs are saved
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEBUG_LOGS_DIR = os.path.join(_ROOT_DIR, "debug_logs")


class FaceDebugLogger:
    """
    Handles saving debug artifacts to disk during face verification.

    Usage:
        logger = FaceDebugLogger()
        logger.start_session("20240471", session_code="HC8FEB")
        logger.save_image("step_02_decoded_frame", frame)
        logger.save_text("step_01_raw_base64", "data:image/jpeg;base64,...")
        ...
    """

    def __init__(self):
        self._session_dir = None
        self.current_subfolder = None  # Set by check_pose to route saves to the right subfolder

    def start_session(self, student_id: str, session_code: str = None):
        """
        Create a new debug folder for this verification attempt.
        Call this at the start of every check_identity / verify request.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        parts = [f"verify_{timestamp}"]
        if session_code:
            parts.append(f"session_{session_code}")
        parts.append(f"student_{student_id}")
        folder_name = "_".join(parts)

        self._session_dir = os.path.join(DEBUG_LOGS_DIR, folder_name)
        os.makedirs(self._session_dir, exist_ok=True)
        return self._session_dir

    def _get_dir(self, subfolder: str = None) -> str:
        """Get the current session directory, optionally with a subfolder."""
        if self._session_dir is None:
            # Fallback if start_session wasn't called
            self.start_session("unknown")
        target = self._session_dir
        if subfolder:
            target = os.path.join(self._session_dir, subfolder)
            os.makedirs(target, exist_ok=True)
        return target

    # ── Save Helpers ────────────────────────────────────────────

    def save_image(self, step_name: str, image: np.ndarray, subfolder: str = None):
        """Save an OpenCV image (BGR numpy array) as JPEG."""
        if image is None:
            return
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.jpg")
            cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        except Exception as e:
            print(f"[DEBUG-LOG] Failed to save image {step_name}: {e}")

    def save_text(self, step_name: str, text: str, subfolder: str = None):
        """Save a plain text string to a .txt file."""
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"[DEBUG-LOG] Failed to save text {step_name}: {e}")

    def save_array(self, step_name: str, arr: np.ndarray, subfolder: str = None):
        """Save a numpy array as both .npy (binary) and .txt (readable)."""
        if arr is None:
            return
        try:
            base = os.path.join(self._get_dir(subfolder), step_name)
            np.save(f"{base}.npy", arr)
            # Also save as human-readable text (one number per line)
            with open(f"{base}.txt", "w") as f:
                for val in arr.flatten():
                    f.write(f"{val:.8f}\n")
        except Exception as e:
            print(f"[DEBUG-LOG] Failed to save array {step_name}: {e}")

    def save_json(self, step_name: str, data: dict, subfolder: str = None):
        """Save a dictionary as a formatted JSON file."""
        try:
            path = os.path.join(self._get_dir(subfolder), f"{step_name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[DEBUG-LOG] Failed to save json {step_name}: {e}")

    def save_cosine_details(self, dot_product: float, norm_a: float,
                            norm_b: float, distance: float, subfolder: str = None):
        """Save cosine distance computation details."""
        text = (
            f"dot_product: {dot_product}\n"
            f"norm_a: {norm_a}\n"
            f"norm_b: {norm_b}\n"
            f"cosine_distance: {distance}\n"
        )
        self.save_text("step_07_cosine_distance", text, subfolder)

    def save_registered_photo(self, photo_path: str, subfolder: str = None):
        """Copy the registered student photo into the debug folder."""
        if photo_path and os.path.exists(photo_path):
            try:
                img = cv2.imread(photo_path)
                if img is not None:
                    self.save_image("step_03_registered_photo", img, subfolder)
            except Exception as e:
                print(f"[DEBUG-LOG] Failed to copy registered photo: {e}")

    def plot_embeddings(self, live_emb: np.ndarray, reg_emb: np.ndarray,
                        distance: float, subfolder: str = None):
        """
        Create a simple 2D scatter plot comparing live vs registered embeddings.
        Uses PCA to project 128-dim vectors to 2D.
        Requires matplotlib (skips silently if not installed).
        """
        try:
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend (no GUI window)
            import matplotlib.pyplot as plt
            from sklearn.decomposition import PCA

            # Stack both embeddings and project to 2D
            data = np.vstack([live_emb.reshape(1, -1), reg_emb.reshape(1, -1)])
            pca = PCA(n_components=2)
            projected = pca.fit_transform(data)

            fig, ax = plt.subplots(1, 1, figsize=(6, 5))
            ax.scatter(projected[0, 0], projected[0, 1], c="blue", s=120,
                       label="Live Frame", marker="o", zorder=5)
            ax.scatter(projected[1, 0], projected[1, 1], c="red", s=120,
                       label="Registered Photo", marker="s", zorder=5)

            # Draw a line between the two points
            ax.plot([projected[0, 0], projected[1, 0]],
                    [projected[0, 1], projected[1, 1]],
                    "k--", alpha=0.4)

            ax.set_title(f"Embedding Comparison (cosine dist = {distance:.4f})")
            ax.legend()
            ax.grid(True, alpha=0.3)

            path = os.path.join(self._get_dir(subfolder), "step_09_plot_embeddings.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            # matplotlib or sklearn not installed — skip silently
            pass
        except Exception as e:
            print(f"[DEBUG-LOG] Failed to plot embeddings: {e}")


# ── Singleton instance ─────────────────────────────────────────────────
# Import this in other files:  from mainAgent.web.face_debug_logger import debug_logger
debug_logger = FaceDebugLogger()
