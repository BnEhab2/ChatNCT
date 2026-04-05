"""Face Verifier — Face recognition and liveness verification module."""
import cv2
import numpy as np
from deepface import DeepFace
import os


class FaceVerifier:
    def __init__(self):
        print("Face Verifier Initialized")
        self.faceCascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def verifyIdentity(self, liveFrame: np.ndarray, registeredImagePath: str) -> dict:
        """First stage: face recognition and verification."""
        result = {
            "verified": False,
            "message": "",
            "distance": 0.0,
            "faceBox": None
        }

        if not os.path.exists(registeredImagePath):
            result["message"] = "Registered image not found."
            return result

        try:
            grayFrame = cv2.cvtColor(liveFrame, cv2.COLOR_BGR2GRAY)
            faces = self.faceCascade.detectMultiScale(grayFrame, 1.1, 4)

            if len(faces) == 0:
                result["message"] = "No face detected."
                return result

            faceBox = max(faces, key=lambda f: f[2] * f[3])
            result["faceBox"] = faceBox

            verification = DeepFace.verify(
                img1_path=liveFrame,
                img2_path=registeredImagePath,
                model_name='Facenet',
                detector_backend='opencv',
                enforce_detection=False,
                distance_metric='cosine'
            )

            result["distance"] = verification["distance"]

            if verification["verified"]:
                result["verified"] = True
                result["message"] = "Identity verified."
            else:
                result["message"] = "Identity mismatch."

        except Exception as e:
            result["message"] = f"Error: {str(e)}"

        return result

    def getHeadPose(self, frame, faceBox):
        """
        Estimate head direction using basic landmarks.
        Returns: direction (center, left, right, tilt_left, tilt_right)
        """
        x, y, w, h = faceBox

        faceRoi = frame[y:y + h, x:x + w]
        if faceRoi.size == 0:
            return "unknown"

        gray = cv2.cvtColor(faceRoi, cv2.COLOR_BGR2GRAY)

        eyesCascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        eyes = eyesCascade.detectMultiScale(gray, 1.1, 5)

        if len(eyes) >= 2:
            eyes = sorted(eyes, key=lambda e: e[0])
            leftEye = eyes[0]
            rightEye = eyes[1]

            leftCenter = (
                leftEye[0] + leftEye[2] // 2,
                leftEye[1] + leftEye[3] // 2
            )
            rightCenter = (
                rightEye[0] + rightEye[2] // 2,
                rightEye[1] + rightEye[3] // 2
            )

            eyeYDiff = leftCenter[1] - rightCenter[1]

            faceCenterX = w // 2
            eyesMidX = (leftCenter[0] + rightCenter[0]) // 2
            faceOffset = eyesMidX - faceCenterX

            if abs(eyeYDiff) > 5:
                if eyeYDiff > 0:
                    return "tilt_left"
                else:
                    return "tilt_right"
            elif abs(faceOffset) > w * 0.1:
                if faceOffset > 0:
                    return "right"
                else:
                    return "left"
            else:
                return "center"
        else:
            frameCenter = frame.shape[1] // 2
            faceCenter = x + w // 2

            if abs(faceCenter - frameCenter) > 50:
                if faceCenter > frameCenter:
                    return "right"
                else:
                    return "left"
            else:
                return "center"
