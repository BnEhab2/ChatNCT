"""
face_verifier.py - Face Recognition & Liveness Detection Engine

This is the core module that handles:
  1. IDENTITY VERIFICATION: Comparing a student's live camera frame
     against their registered photo to confirm they are who they claim.
  2. LIVENESS DETECTION: Asking students to turn their head left/right/up/down
     to prove they're a real person (not just holding up a photo).

Technology Stack:
  - DeepFace (with FaceNet model): Converts face images into numeric vectors
    (called "embeddings") and compares them using cosine distance.
  - OpenCV: Detects where the face is located in each image.
  - MediaPipe FaceLandmarker: Maps 468 points on the face to determine
    which direction the person is looking (yaw = left/right, pitch = up/down).

Performance Optimizations:
  - Registered student photos are converted to embeddings ONCE and cached
    in memory, so only the live frame needs processing each time (~2x faster).
  - Large images are automatically downscaled to 640px max before processing.
  - Models are pre-loaded at startup ("warm-up") so the first request is fast.
"""

import os
import cv2
import numpy as np
import math
import time
import threading
from deepface import DeepFace

# Try to import MediaPipe for head pose detection (liveness checks).
# If it's not installed, we fall back to a simpler position-based method.
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    print("[WARN] mediapipe not installed -- head pose estimation will use fallback.")

# Path to the MediaPipe face landmark model file (~3.7MB)
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")

# ── Configuration ─────────────────────────────────────────────────────
# These settings control how face detection and verification work.
# Change these to tune accuracy vs speed.
_DETECTOR_BACKEND = "opencv"     # Which face detector to use (opencv = fastest)
_MODEL_NAME       = "Facenet"    # Which face recognition model (Facenet = good accuracy + speed)
_DISTANCE_METRIC  = "cosine"     # How to compare face embeddings (cosine = industry standard)
_MAX_IMAGE_DIM    = 640          # Downscale images larger than this (saves processing time)


def _downscale(img: np.ndarray, max_dim: int = _MAX_IMAGE_DIM) -> np.ndarray:
    """
    Shrink an image so its largest side doesn't exceed max_dim pixels.
    This speeds up face detection significantly with minimal accuracy loss.
    Does nothing if the image is already small enough.
    """
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    scale = max_dim / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


class FaceVerifier:
    """
    Main class that handles all face-related operations.
    
    Created once when the attendance server starts, then reused for every request.
    Maintains a cache of student photo embeddings to avoid reprocessing.
    """

    # How similar two faces need to be to count as a "match".
    # Lower = stricter (fewer false positives, more rejections).
    # Higher = more lenient (fewer rejections, but might match wrong person).
    # Default FaceNet threshold is 0.40, but we relaxed it to 0.55
    # because student registration photos are often low quality.
    VERIFY_THRESHOLD = 0.55

    def __init__(self):
        print("[OK] Face Verifier Initialized (DeepFace + MediaPipe)")

        # ── Embedding Cache ────────────────────────────────────────
        # Stores {image_path: embedding_vector} so we don't recompute
        # the same student's registered photo embedding on every request.
        # Thread-safe because multiple students might verify simultaneously.
        self._embedding_cache = {}
        self._cache_lock = threading.Lock()

        # ── MediaPipe FaceLandmarker Setup ─────────────────────────
        # This model detects 468 facial landmarks (eyes, nose, jawline, etc.)
        # and is used to determine head direction for liveness challenges.
        self._landmarker = None
        if _MP_AVAILABLE:
            # Download the model file if it doesn't exist yet
            if not os.path.exists(_MODEL_PATH):
                print(f"[FaceVerifier] Downloading MediaPipe model...")
                import urllib.request
                try:
                    urllib.request.urlretrieve(
                        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
                        _MODEL_PATH
                    )
                except Exception as e:
                    print(f"Error downloading model: {e}")

            # Load the model
            if os.path.exists(_MODEL_PATH):
                try:
                    base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
                    options = mp_vision.FaceLandmarkerOptions(
                        base_options=base_options,
                        running_mode=mp_vision.RunningMode.IMAGE,
                        num_faces=1,                       # Only detect one face
                        min_face_detection_confidence=0.5, # 50% minimum confidence
                        min_face_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
                    print("[OK] MediaPipe FaceLandmarker ready.")
                except Exception as e:
                    print(f"[WARN] FaceLandmarker init failed: {e}")
            else:
                print(f"[WARN] FaceLandmarker model not found at {_MODEL_PATH}")

        # Pre-load the face recognition model into memory
        self._warmup()

    def _warmup(self):
        """
        Pre-load DeepFace models at startup by running them on a dummy image.
        Without this, the first real request would be very slow (~10s) while
        models download and load. After warm-up, requests take ~0.3s.
        """
        try:
            print("[LOADING] Warming up DeepFace models (this only happens once)...")
            # Create a tiny fake image with a bright square (so the detector finds "something")
            dummy = np.zeros((160, 160, 3), dtype=np.uint8)
            dummy[60:100, 60:100] = 200
            DeepFace.represent(
                img_path=dummy,
                model_name=_MODEL_NAME,
                detector_backend=_DETECTOR_BACKEND,
                enforce_detection=False,
            )
            print("[OK] DeepFace models loaded & ready.")
        except Exception as e:
            print(f"[WARN] Warm-up skipped: {e}")

    # ══════════════════════════════════════════════════════════════
    # EMBEDDING CACHE
    # 
    # An "embedding" is a list of 128 numbers that represent a face.
    # Similar faces have similar numbers. We cache the registered
    # student photo's embedding so we only compute it once.
    # ══════════════════════════════════════════════════════════════

    def cache_embedding(self, image_path: str) -> bool:
        """
        Pre-compute and store the face embedding for a student's registered photo.
        Returns True if successful, False if the photo couldn't be processed.
        """
        # Skip if already cached
        with self._cache_lock:
            if image_path in self._embedding_cache:
                return True
        try:
            t0 = time.time()
            result = DeepFace.represent(
                img_path=image_path,
                model_name=_MODEL_NAME,
                detector_backend=_DETECTOR_BACKEND,
                enforce_detection=False,
            )
            if result and len(result) > 0:
                emb = np.array(result[0]["embedding"])
                with self._cache_lock:
                    self._embedding_cache[image_path] = emb
                elapsed = time.time() - t0
                print(f"[CACHE] Embedding cached for {os.path.basename(image_path)} ({elapsed:.3f}s)")
                return True
        except Exception as e:
            print(f"[WARN] Failed to cache embedding for {image_path}: {e}")
        return False

    def _get_cached_embedding(self, image_path: str):
        """Get a cached embedding, computing it first if not cached yet."""
        with self._cache_lock:
            if image_path in self._embedding_cache:
                return self._embedding_cache[image_path]
        # Not cached yet - compute and cache it now
        self.cache_embedding(image_path)
        with self._cache_lock:
            return self._embedding_cache.get(image_path)

    @staticmethod
    def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate how different two face embeddings are.
        Returns a value between 0 and 1:
          - 0.0 = identical faces
          - 0.3 = very similar (likely same person)
          - 0.6 = quite different (likely different people)
          - 1.0 = completely different
        """
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 1.0
        return 1.0 - (dot_product / (norm_a * norm_b))

    # ══════════════════════════════════════════════════════════════
    # STAGE 1: IDENTITY VERIFICATION
    #
    # Compares a live camera frame against the student's registered
    # photo to confirm they are who they claim to be.
    # Uses cached embeddings for speed (~2x faster than fresh comparison).
    # ══════════════════════════════════════════════════════════════

    def verifyIdentity(self, liveFrame: np.ndarray, registeredImagePath: str) -> dict:
        """
        Check if the face in liveFrame matches the registered student photo.

        Args:
            liveFrame:           The current camera frame (numpy array from webcam)
            registeredImagePath: File path to the student's registered photo

        Returns:
            dict with:
              - verified (bool):   True if faces match
              - message (str):     Human-readable status message
              - distance (float):  How different the faces are (0=same, 1=different)
              - faceBox (list):    [x, y, width, height] of detected face, or None
        """
        result = {
            "verified": False,
            "message": "",
            "distance": 1.0,
            "faceBox": None,
        }

        # Check that the registered photo file exists
        if not os.path.exists(registeredImagePath):
            result["message"] = "Registered image not found."
            return result

        # Get the pre-computed embedding for the registered photo (from cache)
        registered_emb = self._get_cached_embedding(registeredImagePath)
        if registered_emb is None:
            result["message"] = "Could not compute registered image embedding."
            return result

        # Shrink the live frame if it's too large (saves processing time)
        liveFrame = _downscale(liveFrame)

        try:
            t0 = time.time()

            # Convert the live camera frame into a face embedding
            live_result = DeepFace.represent(
                img_path=liveFrame,
                model_name=_MODEL_NAME,
                detector_backend=_DETECTOR_BACKEND,
                enforce_detection=False,
            )
            elapsed = time.time() - t0

            if not live_result or len(live_result) == 0:
                result["message"] = "No face detected."
                return result

            live_data = live_result[0]
            live_emb = np.array(live_data["embedding"])

            # Extract the bounding box of the detected face (for UI overlay)
            facial_area = live_data.get("facial_area", {})
            if facial_area:
                x = facial_area.get("x", 0)
                y = facial_area.get("y", 0)
                w = facial_area.get("w", 0)
                h = facial_area.get("h", 0)
                if w > 0 and h > 0:
                    result["faceBox"] = [int(x), int(y), int(w), int(h)]

            # Compare the two face embeddings
            distance = float(self._cosine_distance(registered_emb, live_emb))
            result["distance"] = distance

            # Decide if it's a match
            if distance <= self.VERIFY_THRESHOLD:
                result["verified"] = True
                result["message"] = "Identity verified."
            elif distance > 0.8:
                # Very high distance usually means no real face was detected
                result["message"] = "No face detected."
            else:
                result["message"] = f"Identity mismatch (distance={distance:.3f})."

            print(f"[PERF] verifyIdentity took {elapsed:.3f}s (represent) | distance={distance:.3f}")

        except ValueError as e:
            # DeepFace raises ValueError when no face is found in the image
            err = str(e).lower()
            if "face" in err and ("detect" in err or "found" in err):
                result["message"] = "No face detected."
            else:
                result["message"] = f"Verification error: {e}"
        except Exception as e:
            result["message"] = f"Error: {e}"

        return result

    # ══════════════════════════════════════════════════════════════
    # STAGE 2: HEAD POSE ESTIMATION (Liveness Detection)
    #
    # After identity is confirmed, we check that the student is
    # physically present (not just showing a photo of themselves).
    # We do this by asking them to look in specific directions
    # and verifying their head actually moves.
    # ══════════════════════════════════════════════════════════════

    def getHeadPose(self, frame: np.ndarray, faceBox: list) -> dict:
        """
        Determine which direction the person is looking.

        Args:
            frame:   The camera frame (numpy array)
            faceBox: [x, y, width, height] of the face area

        Returns:
            dict with:
              - pose (str):   "center", "left", "right", "up", or "down"
              - yaw (float):  Horizontal angle (negative=left, positive=right)
              - pitch (float): Vertical angle (negative=up, positive=down)
              - debug (str):  Status info for debugging
        """
        # Use MediaPipe if available (more accurate)
        if self._landmarker is not None:
            return self._getHeadPoseMediaPipe(frame, faceBox)

        # Fallback: simple position-based guess
        pose = self._getHeadPoseFallback(frame, faceBox)
        return {"pose": pose, "yaw": 0, "pitch": 0, "debug": "fallback"}

    def _getHeadPoseMediaPipe(self, frame: np.ndarray, faceBox: list) -> dict:
        """
        Use MediaPipe to precisely determine head direction.

        How it works:
        1. Detect 468 facial landmarks (points on the face)
        2. Compare the nose tip position relative to the eyes
           - If nose is shifted left of eye center -> looking left
           - If nose is shifted right -> looking right
        3. Compare nose position relative to forehead/chin
           - If nose is higher than center -> looking up
           - If nose is lower -> looking down

        Key landmarks used:
            #1   = Nose tip
            #33  = Left eye outer corner
            #263 = Right eye outer corner
            #10  = Top of forehead
            #152 = Bottom of chin
        """
        # MediaPipe expects RGB format (OpenCV uses BGR)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self._landmarker.detect(mp_image)

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "no_landmarks"}

        lm = result.face_landmarks[0]

        # Get key facial landmark positions (values are normalized 0.0 to 1.0)
        nose = lm[1]           # Nose tip
        left_eye = lm[33]     # Left eye outer corner
        right_eye = lm[263]   # Right eye outer corner
        forehead = lm[10]     # Top of forehead
        chin = lm[152]        # Bottom of chin

        # ── Calculate YAW (left/right rotation) ──
        # Measure where the nose sits between the two eyes.
        # If perfectly centered, nose_ratio = 0.5
        eye_width = right_eye.x - left_eye.x
        if abs(eye_width) < 0.001:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "eyes_too_close"}

        nose_ratio = (nose.x - left_eye.x) / eye_width
        yaw = (nose_ratio - 0.5) * 100  # Scale to roughly -50 to +50

        # ── Calculate PITCH (up/down tilt) ──
        # Measure where the nose sits between forehead and chin.
        face_height = chin.y - forehead.y
        if abs(face_height) < 0.001:
            return {"pose": "unknown", "yaw": 0, "pitch": 0, "debug": "face_too_flat"}

        nose_v_ratio = (nose.y - forehead.y) / face_height
        pitch = (nose_v_ratio - 0.45) * 100  # 0.45 is roughly center

        # ── Classify the pose based on thresholds ──
        YAW_THRESH = 5     # How much yaw is needed to count as "left" or "right"
        PITCH_THRESH = 8   # How much pitch is needed to count as "up" or "down"

        if abs(yaw) < YAW_THRESH and abs(pitch) < PITCH_THRESH:
            pose = "center"
        elif yaw < -YAW_THRESH:
            pose = "left"
        elif yaw > YAW_THRESH:
            pose = "right"
        elif pitch < -PITCH_THRESH:
            pose = "up"
        elif pitch > PITCH_THRESH:
            pose = "down"
        else:
            pose = "center"

        return {"pose": pose, "yaw": round(yaw, 1), "pitch": round(pitch, 1), "debug": "ok"}

    @staticmethod
    def _getHeadPoseFallback(frame: np.ndarray, faceBox: list) -> str:
        """
        Simple fallback when MediaPipe is not available.
        Just checks if the face is shifted left or right of the frame center.
        Less accurate than MediaPipe but works as a basic alternative.
        """
        x, y, w, h = faceBox
        frame_cx = frame.shape[1] // 2   # Center of frame (horizontal)
        face_cx = x + w // 2             # Center of face (horizontal)

        offset = face_cx - frame_cx
        if abs(offset) > w * 0.15:
            return "left" if offset > 0 else "right"
        return "center"
