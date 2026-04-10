"""Face Verifier — Face recognition and liveness verification module.

Uses DeepFace (Facenet + ssd) for fast identity verification
and MediaPipe FaceLandmarker (Tasks API) for accurate head-pose estimation.

Performance optimisations
─────────────────────────
- **ssd** detector backend instead of retinaface (~10× faster)
- Models pre-loaded at startup via a warm-up call
- Images down-scaled before verification to reduce processing time
"""
import os
import cv2
import numpy as np
import math
from deepface import DeepFace

# Try to import mediapipe Tasks API for head pose estimation
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    print("[WARN] mediapipe not installed -- head pose estimation will use fallback.")

# Path to the FaceLandmarker model file
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")

# ── Tunable knobs ─────────────────────────────────────────────────────
_DETECTOR_BACKEND = "opencv"     # fast + returns eye landmarks for alignment
_MODEL_NAME       = "Facenet"    # Good balance of speed & accuracy
_DISTANCE_METRIC  = "cosine"
_MAX_IMAGE_DIM    = 640          # Down-scale large images to this max dimension


def _downscale(img: np.ndarray, max_dim: int = _MAX_IMAGE_DIM) -> np.ndarray:
    """Shrink image so its largest side is ≤ max_dim. No-op if already small."""
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    scale = max_dim / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


class FaceVerifier:
    """Handles face verification and head-pose liveness checks."""

    # DeepFace verification threshold (cosine distance for Facenet)
    # Relaxed from default 0.40 because registered images are small/low-quality
    VERIFY_THRESHOLD = 0.55

    def __init__(self):
        print("[OK] Face Verifier Initialized (DeepFace + MediaPipe)")

        # ── MediaPipe FaceLandmarker for head pose ─────────────────
        self._landmarker = None
        if _MP_AVAILABLE:
            if os.path.exists(_MODEL_PATH):
                try:
                    base_options = mp_python.BaseOptions(
                        model_asset_path=_MODEL_PATH
                    )
                    options = mp_vision.FaceLandmarkerOptions(
                        base_options=base_options,
                        running_mode=mp_vision.RunningMode.IMAGE,
                        num_faces=1,
                        min_face_detection_confidence=0.5,
                        min_face_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
                    print("[OK] MediaPipe FaceLandmarker ready.")
                except Exception as e:
                    print(f"[WARN] FaceLandmarker init failed: {e}")
            else:
                print(f"[WARN] FaceLandmarker model not found at {_MODEL_PATH}")

        # ── Warm-up: pre-load DeepFace models so first request is fast ──
        self._warmup()

    def _warmup(self):
        """Force DeepFace to download & cache its model weights at startup."""
        try:
            print("[LOADING] Warming up DeepFace models (this only happens once)...")
            # Build a tiny dummy image so DeepFace loads the model graph
            dummy = np.zeros((160, 160, 3), dtype=np.uint8)
            dummy[60:100, 60:100] = 200        # bright square so detector sees *something*
            DeepFace.represent(
                img_path=dummy,
                model_name=_MODEL_NAME,
                detector_backend=_DETECTOR_BACKEND,
                enforce_detection=False,
            )
            print("[OK] DeepFace models loaded & ready.")
        except Exception as e:
            # Non-fatal — first real request will trigger the download instead
            print(f"[WARN] Warm-up skipped: {e}")

    # ──────────────────────────────────────────────────────────────
    # Stage 1: Identity Verification
    # ──────────────────────────────────────────────────────────────
    def verifyIdentity(self, liveFrame: np.ndarray, registeredImagePath: str) -> dict:
        """Verify that the face in *liveFrame* matches *registeredImagePath*.

        Returns dict with keys:
            verified (bool), message (str), distance (float), faceBox ([x,y,w,h] | None)
        """
        result = {
            "verified": False,
            "message": "",
            "distance": 0.0,
            "faceBox": None,
        }

        if not os.path.exists(registeredImagePath):
            result["message"] = "Registered image not found."
            return result

        # Down-scale for speed
        liveFrame = _downscale(liveFrame)

        try:
            # DeepFace.verify handles detection internally
            verification = DeepFace.verify(
                img1_path=liveFrame,
                img2_path=registeredImagePath,
                model_name=_MODEL_NAME,
                detector_backend=_DETECTOR_BACKEND,
                enforce_detection=False,
                distance_metric=_DISTANCE_METRIC,
            )

            result["distance"] = verification["distance"]

            # Extract detected face region from DeepFace response
            facial_area = verification.get("facial_areas", {}).get("img1")
            if facial_area:
                x = facial_area.get("x", 0)
                y = facial_area.get("y", 0)
                w = facial_area.get("w", 0)
                h = facial_area.get("h", 0)
                if w > 0 and h > 0:
                    result["faceBox"] = [int(x), int(y), int(w), int(h)]

            # Use our own threshold (more lenient than DeepFace default)
            if verification["distance"] <= self.VERIFY_THRESHOLD:
                result["verified"] = True
                result["message"] = "Identity verified."
            else:
                result["message"] = f"Identity mismatch (distance={verification['distance']:.3f})."

        except ValueError as e:
            # DeepFace raises ValueError when no face is detected
            err = str(e).lower()
            if "face" in err and ("detect" in err or "found" in err):
                result["message"] = "No face detected."
            else:
                result["message"] = f"Verification error: {e}"
        except Exception as e:
            result["message"] = f"Error: {e}"

        return result

    # ──────────────────────────────────────────────────────────────
    # Stage 2: Head Pose Estimation (Liveness)
    # ──────────────────────────────────────────────────────────────
    def getHeadPose(self, frame: np.ndarray, faceBox: list) -> dict:
        """Estimate head direction from *frame*.

        Uses MediaPipe FaceLandmarker to compute yaw/pitch angles.
        Returns dict: {"pose": str, "yaw": float, "pitch": float, "debug": str}
        """
        if self._landmarker is not None:
            return self._getHeadPoseMediaPipe(frame, faceBox)

        # Fallback: simple position-based heuristic
        pose = self._getHeadPoseFallback(frame, faceBox)
        return {"pose": pose, "yaw": 0, "pitch": 0, "debug": "fallback"}

    # ── MediaPipe-based pose ──────────────────────────────────────
    def _getHeadPoseMediaPipe(self, frame: np.ndarray, faceBox: list) -> dict:
        """Use MediaPipe FaceLandmarker — simple landmark-ratio approach.

        Instead of complex PnP solving, we compare the nose tip position
        relative to the eye landmarks to determine head direction.
        This works reliably with mobile front cameras.

        Key landmarks:
            1   - nose tip
            33  - left eye outer corner  (right side of image for front cam)
            263 - right eye outer corner (left side of image for front cam)
            10  - forehead top
            152 - chin bottom
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self._landmarker.detect(mp_image)

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "no_landmarks"}

        lm = result.face_landmarks[0]

        # Get key landmark positions (normalized 0-1)
        nose = lm[1]           # nose tip
        left_eye = lm[33]     # left eye outer
        right_eye = lm[263]   # right eye outer
        forehead = lm[10]     # top of forehead
        chin = lm[152]        # bottom of chin

        # ── YAW (left/right) ──
        # Compute nose position as ratio between left eye and right eye
        eye_width = right_eye.x - left_eye.x
        if abs(eye_width) < 0.001:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "eyes_too_close"}

        # nose_ratio: 0.5 = centered, <0.5 = looking right, >0.5 = looking left
        nose_ratio = (nose.x - left_eye.x) / eye_width
        yaw = (nose_ratio - 0.5) * 100  # scale to roughly -50..+50

        # ── PITCH (up/down) ──
        face_height = chin.y - forehead.y
        if abs(face_height) < 0.001:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "face_too_flat"}

        # nose vertical position as ratio between forehead and chin
        nose_v_ratio = (nose.y - forehead.y) / face_height
        pitch = (nose_v_ratio - 0.45) * 100  # 0.45 is roughly center

        # ── Classify ──
        YAW_THRESH = 8
        PITCH_THRESH = 10

        if abs(yaw) < YAW_THRESH and abs(pitch) < PITCH_THRESH:
            pose = "center"
        elif yaw < -YAW_THRESH:
            pose = "right"    # nose moved toward left eye = looking right
        elif yaw > YAW_THRESH:
            pose = "left"     # nose moved toward right eye = looking left
        elif pitch < -PITCH_THRESH:
            pose = "up"
        elif pitch > PITCH_THRESH:
            pose = "down"
        else:
            pose = "center"

        return {"pose": pose, "yaw": round(yaw, 1), "pitch": round(pitch, 1), "debug": "ok"}

    # ── Fallback (no mediapipe) ───────────────────────────────────
    @staticmethod
    def _getHeadPoseFallback(frame: np.ndarray, faceBox: list) -> str:
        """Simple heuristic: compare face center to frame center."""
        x, y, w, h = faceBox
        frame_cx = frame.shape[1] // 2
        face_cx = x + w // 2

        offset = face_cx - frame_cx
        if abs(offset) > w * 0.15:
            return "right" if offset > 0 else "left"
        return "center"
