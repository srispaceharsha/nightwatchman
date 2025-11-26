import cv2
import time
import math
import statistics
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

HOLD_SECONDS = 2.0
LOSS_GRACE_SECONDS = 0.4
MIN_FOLDED_FINGERS = 2      # how many non-thumb fingers must be folded
FOLDED_ANGLE_MAX = 120      # angle at PIP < this => folded

RED = "\033[91m"
RESET = "\033[0m"


def angle_at(p1, p2, p3):
    """Angle (in degrees) at point p2 formed by p1-p2-p3 using 3D coords."""
    v1 = (p1.x - p2.x, p1.y - p2.y, p1.z - p2.z)
    v2 = (p3.x - p2.x, p3.y - p2.y, p3.z - p2.z)

    dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
    n1 = math.sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
    n2 = math.sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cosang = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cosang))


def classify_thumbs_down(hand_landmarks):
    """
    Returns:
        is_down (bool),
        variant ('palm' | 'back' | 'fist' | None),
        folded_count (int)
    """
    lm = hand_landmarks.landmark

    # Thumb down: tip lower (larger y) than MCP + index MCP
    thumb_tip = lm[4]
    thumb_mcp = lm[2]
    index_mcp = lm[5]
    thumb_down = (thumb_tip.y > thumb_mcp.y) and (thumb_tip.y > index_mcp.y)

    # Fold detection via angles at PIP joints
    finger_joints = {
        "index": (5, 6, 8),
        "middle": (9, 10, 12),
        "ring": (13, 14, 16),
        "pinky": (17, 18, 20),
    }

    folded = {}
    for name, (mcp_i, pip_i, tip_i) in finger_joints.items():
        a = angle_at(lm[mcp_i], lm[pip_i], lm[tip_i])
        folded[name] = a < FOLDED_ANGLE_MAX

    folded_count = sum(1 for v in folded.values() if v)

    if not thumb_down or folded_count < MIN_FOLDED_FINGERS:
        return False, None, folded_count

    # Orientation: palm / back / fist
    fingertip_ids = [8, 12, 16, 20]
    mcp_ids = [5, 9, 13, 17]
    tip_z_avg = statistics.mean(lm[i].z for i in fingertip_ids)
    mcp_z_avg = statistics.mean(lm[i].z for i in mcp_ids)

    if folded_count >= 3:
        variant = "fist"
    else:
        if tip_z_avg < mcp_z_avg - 0.01:
            variant = "palm"
        elif tip_z_avg > mcp_z_avg + 0.01:
            variant = "back"
        else:
            variant = "palm"

    return True, variant, folded_count


def main():
    cap = cv2.VideoCapture(0)

    gesture_start_time = None
    last_seen_time = None
    gesture_confirmed = False
    current_variant = None

    print("[INFO] Starting thumbs-down detector...")
    print(f"[INFO] Need to hold thumbs down for {HOLD_SECONDS} seconds.")

    with mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4
    ) as hands:

        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                print("[WARN] Empty camera frame.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)
            rgb.flags.writeable = True

            now = time.time()
            hand_present = results.multi_hand_landmarks is not None
            thumbs_down_now = False
            elapsed = (now - gesture_start_time) if gesture_start_time else 0.0

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
                    )

                    is_down, variant, _ = classify_thumbs_down(hand_landmarks)
                    if is_down:
                        thumbs_down_now = True
                        current_variant = variant

            if thumbs_down_now:
                if gesture_start_time is None:
                    gesture_start_time = now
                    last_seen_time = now
                    gesture_confirmed = False
                else:
                    last_seen_time = now

                elapsed = now - gesture_start_time

                if not gesture_confirmed and elapsed >= HOLD_SECONDS:
                    gesture_confirmed = True
                    v = current_variant or "unknown"
                    print(
                        f"{RED}👎 [CONFIRM] Thumbs down ({v}) confirmed at t={now:.3f}, "
                        f"held_for={elapsed:.3f}s{RESET}",
                        flush=True,
                    )
            else:
                if last_seen_time is not None and gesture_start_time is not None:
                    if now - last_seen_time > LOSS_GRACE_SECONDS:
                        gesture_start_time = None
                        last_seen_time = None
                        gesture_confirmed = False
                        elapsed = 0.0
                        current_variant = None

            # UI overlay
            if thumbs_down_now and gesture_start_time is not None:
                label = f"Thumbs down ({current_variant or '...'}): {elapsed:.1f}s"
                cv2.putText(frame, label, (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 255, 0), 2, cv2.LINE_AA)
            elif hand_present:
                cv2.putText(frame, "Hand detected, waiting for thumbs down...",
                            (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 255, 255), 2, cv2.LINE_AA)
            else:
                cv2.putText(frame, "No hand detected",
                            (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 0, 255), 2, cv2.LINE_AA)

            cv2.imshow("Thumbs Down Detection", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Exiting.")


if __name__ == "__main__":
    main()
