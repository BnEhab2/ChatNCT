"""
Quick script to generate the missing debug images from saved data.
Run this after a verification attempt to get:
  - step_09_plot_embeddings.png (cosine distance graph)
  - step_landmarks_overlay.jpg (face with landmarks)
"""
import os
import sys
import glob
import numpy as np
import cv2

# Find the latest debug session
debug_root = os.path.join(os.path.dirname(__file__), "debug_logs")
sessions = sorted(glob.glob(os.path.join(debug_root, "verify_*")), key=os.path.getmtime)

if not sessions:
    print("No debug sessions found!")
    sys.exit(1)

latest = sessions[-1]
print(f"Processing: {os.path.basename(latest)}")

# ── 1) Generate Embedding Plot ──────────────────────────────────
live_path = os.path.join(latest, "step_05_live_embedding.npy")
reg_path = os.path.join(latest, "step_06_registered_embedding.npy")
dist_path = os.path.join(latest, "step_07_cosine_distance.txt")

if os.path.exists(live_path) and os.path.exists(reg_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    live_emb = np.load(live_path)
    reg_emb = np.load(reg_path)

    # Read distance
    distance = 0.0
    if os.path.exists(dist_path):
        with open(dist_path) as f:
            for line in f:
                if "cosine_distance" in line:
                    distance = float(line.split(":")[1].strip())

    # Bar chart comparing embedding dimensions
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: Overlay of both embeddings
    ax1 = axes[0, 0]
    x = range(len(live_emb))
    ax1.plot(x, live_emb, alpha=0.7, label="Live Frame", linewidth=0.8)
    ax1.plot(x, reg_emb, alpha=0.7, label="Registered Photo", linewidth=0.8)
    ax1.set_title(f"Embedding Overlay (128 dimensions)\nCosine Distance: {distance:.4f}")
    ax1.set_xlabel("Dimension")
    ax1.set_ylabel("Value")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Difference between embeddings
    ax2 = axes[0, 1]
    diff = live_emb - reg_emb
    colors = ['red' if d > 0 else 'blue' for d in diff]
    ax2.bar(x, diff, color=colors, alpha=0.6, width=1.0)
    ax2.set_title("Embedding Difference (Live - Registered)")
    ax2.set_xlabel("Dimension")
    ax2.set_ylabel("Difference")
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Scatter plot (PCA projection)
    ax3 = axes[1, 0]
    try:
        from sklearn.decomposition import PCA
        data = np.vstack([live_emb.reshape(1, -1), reg_emb.reshape(1, -1)])
        # Need more samples for PCA, so add some noise
        noisy = np.vstack([data, data + np.random.normal(0, 0.01, data.shape)])
        pca = PCA(n_components=2)
        projected = pca.fit_transform(noisy)
        ax3.scatter(projected[0, 0], projected[0, 1], c="blue", s=200, label="Live", marker="o", zorder=5)
        ax3.scatter(projected[1, 0], projected[1, 1], c="red", s=200, label="Registered", marker="s", zorder=5)
        ax3.plot([projected[0, 0], projected[1, 0]], [projected[0, 1], projected[1, 1]], "k--", alpha=0.4)
        ax3.set_title("PCA Projection (2D)")
        ax3.legend()
    except Exception as e:
        ax3.text(0.5, 0.5, f"PCA failed: {e}", ha='center', va='center')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Decision summary
    ax4 = axes[1, 1]
    ax4.axis("off")
    decision_path = os.path.join(latest, "step_08_decision.json")
    import json
    if os.path.exists(decision_path):
        with open(decision_path) as f:
            decision = json.load(f)
        text = (
            f"Verified: {decision.get('verified', '?')}\n"
            f"Distance: {decision.get('distance', '?'):.4f}\n"
            f"Threshold: {decision.get('threshold', '?')}\n"
            f"Message: {decision.get('message', '?')}\n"
            f"Time: {decision.get('timestamp', '?')}\n"
            f"Elapsed: {decision.get('elapsed_represent_s', '?')}s"
        )
    else:
        text = f"Cosine Distance: {distance:.4f}"
    
    color = "green" if distance < 0.55 else "red"
    ax4.text(0.5, 0.6, "MATCH" if distance < 0.55 else "NO MATCH",
             fontsize=36, ha='center', va='center', color=color, fontweight='bold')
    ax4.text(0.5, 0.3, text, fontsize=12, ha='center', va='center', 
             fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    out = os.path.join(latest, "step_09_plot_embeddings.png")
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved: {out}")
else:
    print("[SKIP] No embedding files found.")

# ── 2) Generate Landmarks Overlay ────────────────────────────────
frame_path = os.path.join(latest, "step_04_downscaled_live_frame.jpg")
if os.path.exists(frame_path):
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        model_path = os.path.join(os.path.dirname(__file__), "mainAgent", "web", "face_landmarker.task")
        if not os.path.exists(model_path):
            print(f"[SKIP] MediaPipe model not found: {model_path}")
        else:
            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.IMAGE,
                num_faces=1
            )
            landmarker = mp_vision.FaceLandmarker.create_from_options(options)

            frame = cv2.imread(frame_path)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)

            if result.face_landmarks:
                lm = result.face_landmarks[0]
                debug_frame = frame.copy()
                fh, fw = debug_frame.shape[:2]

                # Draw all 468 landmarks
                for p in lm:
                    cx, cy = int(p.x * fw), int(p.y * fh)
                    cv2.circle(debug_frame, (cx, cy), 1, (0, 255, 0), -1)

                # Key landmarks with labels
                key_points = {
                    1: ("Nose", (0, 0, 255)),
                    33: ("L-Eye", (255, 0, 0)),
                    263: ("R-Eye", (255, 0, 0)),
                    10: ("Forehead", (0, 255, 255)),
                    152: ("Chin", (0, 255, 255)),
                }
                coords = {}
                for idx, (name, color) in key_points.items():
                    px, py = int(lm[idx].x * fw), int(lm[idx].y * fh)
                    coords[idx] = (px, py)
                    cv2.circle(debug_frame, (px, py), 5, color, -1)
                    cv2.putText(debug_frame, name, (px + 8, py - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                # Connections
                cv2.line(debug_frame, coords[33], coords[263], (255, 255, 0), 1)
                cv2.line(debug_frame, coords[10], coords[152], (0, 200, 200), 1)
                cv2.line(debug_frame, coords[33], coords[1], (200, 200, 0), 1)
                cv2.line(debug_frame, coords[263], coords[1], (200, 200, 0), 1)

                out = os.path.join(latest, "step_landmarks_overlay.jpg")
                cv2.imwrite(out, debug_frame)
                print(f"[OK] Saved: {out}")
            else:
                print("[SKIP] No face landmarks detected in frame.")

            landmarker.close()
    except ImportError as e:
        print(f"[SKIP] MediaPipe not available: {e}")
else:
    print("[SKIP] No downscaled frame found.")

print("\nDone! Check:", latest)
