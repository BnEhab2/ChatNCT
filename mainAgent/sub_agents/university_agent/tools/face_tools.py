"""Face recognition tools — webcam-based identity verification & liveness detection.

These tools receive the photo path from the root agent (which gets it via the database agent).
No direct database access here.
"""

import os
import time
import cv2
import numpy as np

# Resolve the package root for constructing absolute paths
_PACKAGE_DIR = os.path.dirname(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Haar cascades (loaded once globally for efficiency)
# ---------------------------------------------------------------------------
_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_eyes_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)


def _resolve_photo_path(photo_path: str) -> str:
    """Turn a relative photo path into an absolute one."""
    if os.path.isabs(photo_path):
        return photo_path
    return os.path.join(_PACKAGE_DIR, photo_path)


# =============================================================================
# 🔧 INTERNAL CORE: FaceVerifier Class (Encapsulated Logic)
# =============================================================================
class _FaceVerifierCore:
    """
    Internal engine for face verification and pose estimation.
    Uses optimized logic from the enhanced implementation.
    """
    
    def __init__(self):
        self.face_cascade = _face_cascade
        self.eyes_cascade = _eyes_cascade

    def verify_identity_frame(self, live_frame: np.ndarray, registered_path: str) -> dict:
        """Compare a live frame against a registered photo using DeepFace."""
        result = {
            "verified": False,
            "distance": 0.0,
            "message": "",
            "face_box": None
        }

        if not os.path.exists(registered_path):
            result["message"] = "Registered image not found."
            return result

        try:
            gray = cv2.cvtColor(live_frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)

            if len(faces) == 0:
                result["message"] = "No face detected."
                return result

            # Pick the largest face (most likely the user)
            face_box = max(faces, key=lambda f: f[2] * f[3])
            result["face_box"] = face_box

            from deepface import DeepFace
            verification = DeepFace.verify(
                img1_path=live_frame,
                img2_path=registered_path,
                model_name='Facenet',
                detector_backend='opencv',
                enforce_detection=False,
                distance_metric='cosine'
            )

            result["distance"] = round(verification["distance"], 4)
            result["verified"] = verification["verified"]
            result["message"] = "Identity verified." if verification["verified"] else "Identity mismatch."

        except Exception as e:
            result["message"] = f"Error: {str(e)}"

        return result

    def estimate_head_pose(self, frame: np.ndarray, face_box: tuple) -> str:
        """
        Estimate head direction using eye landmarks.
        Returns: 'center', 'left', 'right', 'tilt_left', 'tilt_right', or 'unknown'
        """
        x, y, w, h = face_box
        face_roi = frame[y:y + h, x:x + w]
        
        if face_roi.size == 0:
            return "unknown"

        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        eyes = self.eyes_cascade.detectMultiScale(gray, 1.1, 5)

        if len(eyes) >= 2:
            eyes = sorted(eyes, key=lambda e: e[0])
            left_eye, right_eye = eyes[0], eyes[1]

            # Calculate eye centers
            lc = (left_eye[0] + left_eye[2] // 2, left_eye[1] + left_eye[3] // 2)
            rc = (right_eye[0] + right_eye[2] // 2, right_eye[1] + right_eye[3] // 2)

            # Check for head tilt (vertical difference)
            eye_y_diff = lc[1] - rc[1]
            if abs(eye_y_diff) > 5:
                return "tilt_left" if eye_y_diff > 0 else "tilt_right"

            # Check for horizontal look direction
            face_center_x = w // 2
            eyes_mid_x = (lc[0] + rc[0]) // 2
            offset = eyes_mid_x - face_center_x

            if abs(offset) > w * 0.1:
                return "right" if offset > 0 else "left"
            return "center"
        else:
            # Fallback: use face position in frame
            frame_cx = frame.shape[1] // 2
            face_cx = x + w // 2
            if abs(face_cx - frame_cx) > 50:
                return "right" if face_cx > frame_cx else "left"
            return "center"


# =============================================================================
# 🚀 PUBLIC API: Tool Functions (Maintain Project Contract)
# =============================================================================

def verify_student_face(photo_path: str) -> dict:
    """
    Open webcam, capture frame, and verify face against registered photo.
    
    Returns dict compatible with root agent expectations.
    """
    registered_path = _resolve_photo_path(photo_path)

    if not os.path.exists(registered_path):
        return {
            "status": "error",
            "message": f"Photo file not found at '{registered_path}'. Please register a photo first.",
        }

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return {"status": "error", "message": "Could not open webcam."}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Initialize core engine
    verifier = _FaceVerifierCore()
    
    result = {
        "status": "error",
        "verified": False,
        "distance": 0.0,
        "message": "",
    }

    try:
        start_time = time.time()
        best_frame = None
        best_area = 0

        # Capture loop: find the best face frame within 5 seconds
        while time.time() - start_time < 5:
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = verifier.face_cascade.detectMultiScale(gray, 1.1, 4)

            # Visual feedback
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            remaining = max(0, int(5 - (time.time() - start_time)))
            cv2.putText(frame, f"Position face... {remaining}s", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("Face Verification", frame)
            cv2.waitKey(1)

            # Track the largest/clearest face frame
            if len(faces) > 0:
                largest = max(faces, key=lambda f: f[2] * f[3])
                area = largest[2] * largest[3]
                if area > best_area:
                    best_area = area
                    best_frame = frame.copy()

        if best_frame is None:
            result["message"] = "No face detected during capture window."
            return result

        # Perform verification using the core engine
        verification = verifier.verify_identity_frame(best_frame, registered_path)
        
        result["status"] = "success"
        result["verified"] = verification["verified"]
        result["distance"] = verification["distance"]
        result["message"] = verification["message"]

    except Exception as e:
        result["message"] = f"Verification error: {str(e)}"
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return result


def run_liveness_check(photo_path: str) -> dict:
    """
    Run full liveness verification: identity check + head-pose challenge sequence.
    
    Returns dict with identity_verified, liveness_passed, and challenge details.
    """
    registered_path = _resolve_photo_path(photo_path)

    if not os.path.exists(registered_path):
        return {
            "status": "error",
            "message": f"Photo file not found at '{registered_path}'. Please register a photo first.",
        }

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return {"status": "error", "message": "Could not open webcam."}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Initialize core engine
    verifier = _FaceVerifierCore()

    # State Machine Constants
    STATE_IDENTITY, STATE_LIVENESS, STATE_COMPLETE = 0, 1, 2
    
    # Challenge Configuration
    challenges = [
        ("center", "Look Straight"),
        ("left", "Look Left"),
        ("right", "Look Right"),
        ("center", "Look Straight Again"),
    ]
    TIMEOUT = 10  # seconds per challenge

    # State Variables
    state = STATE_IDENTITY
    challenge_idx = 0
    challenge_start = 0
    identity_verified = False
    liveness_passed = False
    current_face_box = None
    last_check = 0

    result = {
        "status": "error",
        "identity_verified": False,
        "liveness_passed": False,
        "message": "",
        "challenges_passed": 0,
    }

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            now = time.time()
            status_text = ""
            color = (255, 255, 255)  # Default white

            # ───────── STATE: IDENTITY CHECK ─────────
            if state == STATE_IDENTITY:
                status_text = "Verifying Identity..."
                
                if now - last_check > 2:  # Check every 2 seconds
                    last_check = now
                    verification = verifier.verify_identity_frame(frame, registered_path)
                    current_face_box = verification.get("face_box")
                    status_text = verification["message"]

                    if verification["verified"]:
                        identity_verified = True
                        state = STATE_LIVENESS
                        challenge_idx = 0
                        challenge_start = now
                        status_text = "✓ Identity OK! Starting liveness..."
                        print("Identity verified. Starting liveness challenge.")
                    else:
                        color = (0, 165, 255)  # Orange for warning

            # ───────── STATE: LIVENESS CHALLENGE ─────────
            elif state == STATE_LIVENESS:
                if current_face_box is None:
                    status_text = "Face lost! Re-detecting..."
                    color = (0, 0, 255)  # Red
                    # Try to re-acquire face
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = verifier.face_cascade.detectMultiScale(gray, 1.1, 4)
                    if faces:
                        current_face_box = max(faces, key=lambda f: f[2] * f[3])
                else:
                    target_pose, instruction = challenges[challenge_idx]
                    status_text = f"Challenge: {instruction}"
                    color = (0, 255, 255)  # Cyan for active challenge

                    # Estimate pose using core engine
                    current_pose = verifier.estimate_head_pose(frame, current_face_box)

                    if current_pose == target_pose:
                        # ✓ Challenge passed
                        challenge_idx += 1
                        print(f"✓ Passed: {instruction}")
                        
                        if challenge_idx >= len(challenges):
                            state = STATE_COMPLETE
                            liveness_passed = True
                            print("Liveness challenge complete!")
                        else:
                            challenge_start = now
                            status_text = challenges[challenge_idx][1]
                    else:
                        # Show timeout countdown
                        elapsed = now - challenge_start
                        remaining = int(TIMEOUT - elapsed)
                        if remaining < 0:
                            # ✗ Timeout - reset challenge sequence
                            print(f"✗ Timeout on: {instruction}")
                            challenge_idx = 0
                            challenge_start = now
                            status_text = "Timeout! Restarting..."
                        else:
                            status_text += f" ({remaining}s)"

            # ───────── STATE: COMPLETE ─────────
            elif state == STATE_COMPLETE:
                status_text = "Verification Complete!"
                color = (0, 255, 0)  # Green
                
                cv2.putText(frame, "SUCCESS! ✓", (10, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                cv2.imshow("Face Verification", frame)
                cv2.waitKey(2000)  # Show success for 2 seconds
                break

            # ───────── DRAWING & FEEDBACK ─────────
            if current_face_box is not None and state != STATE_COMPLETE:
                x, y, w, h = current_face_box
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, "FACE", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Status text overlay
            cv2.putText(frame, status_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Progress bar for liveness challenge
            if state == STATE_LIVENESS and current_face_box is not None:
                elapsed = now - challenge_start
                progress = min(elapsed / TIMEOUT, 1.0)
                bar_w = int(200 * progress)
                cv2.rectangle(frame, (10, 470), (210, 480), (100, 100, 100), -1)
                cv2.rectangle(frame, (10, 470), (10 + bar_w, 480), color, -1)

            cv2.imshow("Face Verification", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                result["message"] = "User cancelled."
                break

    except Exception as e:
        result["message"] = f"Error: {str(e)}"
    finally:
        cap.release()
        cv2.destroyAllWindows()

    # ───────── FINALIZE RESULT DICT ─────────
    result["status"] = "success"
    result["identity_verified"] = identity_verified
    result["liveness_passed"] = liveness_passed
    result["challenges_passed"] = challenge_idx if not liveness_passed else len(challenges)

    if liveness_passed and identity_verified:
        result["message"] = "PASSED identity + liveness verification."
    elif identity_verified and not liveness_passed:
        result["message"] = f"Passed identity but FAILED liveness (completed {challenge_idx}/{len(challenges)} challenges)."
    else:
        result["message"] = result.get("message") or "FAILED identity verification."

    return result