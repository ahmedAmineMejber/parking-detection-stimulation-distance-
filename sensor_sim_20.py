import time, json, random
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER_HOST = "127.0.0.1"   # replace later with Person 5 broker IP
BROKER_PORT = 1883

# 20 spots
SPOTS = [f"A{i}" for i in range(1, 11)] + [f"B{i}" for i in range(1, 11)]

THRESHOLD_CM = 50.0
READ_INTERVAL_S = 1.0

# Distances (ultrasonic-like)
DIST_FREE = (150, 280)   # cm
DIST_PARK = (10, 35)     # cm
NOISE_CM = 2.0

def now():
    return datetime.now().isoformat(timespec="seconds")

class Spot:
    """
    Each spot has its own "activity factor":
    - Busy spot changes more often
    - Calm spot changes less often
    This makes the demo feel realistic for 20 spots.
    """
    def __init__(self, spot_id: str):
        self.spot_id = spot_id
        self.has_car = False

        # activity: 0.6..1.6  (higher => more changes)
        self.activity = random.uniform(0.6, 1.6)

        self.next_switch = time.time() + self._free_duration()
        self.last_status = None

    def _park_duration(self):
        # base 45..180s, adjusted by activity
        base = random.uniform(45, 180)
        return base / self.activity

    def _free_duration(self):
        # base 30..150s, adjusted by activity
        base = random.uniform(30, 150)
        return base / self.activity

    def read_distance(self) -> float:
        # change world state when timer ends
        t = time.time()
        if t >= self.next_switch:
            self.has_car = not self.has_car
            self.next_switch = t + (self._park_duration() if self.has_car else self._free_duration())

        # simulate distance based on world state + small noise
        base = random.uniform(*(DIST_PARK if self.has_car else DIST_FREE))
        noise = random.uniform(-NOISE_CM, NOISE_CM)
        return max(0.0, base + noise)

    def status_from_distance(self, distance_cm: float) -> str:
        return "OCCUPIED" if distance_cm < THRESHOLD_CM else "FREE"

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()

    spots = [Spot(s) for s in SPOTS]
    print("20-spot sensor started. Publishing only on change...")

    try:
        while True:
            for sp in spots:
                d = sp.read_distance()
                status = sp.status_from_distance(d)

                if status != sp.last_status:
                    sp.last_status = status
                    topic = f"parking/spot/{sp.spot_id}/status"
                    payload = {
                        "spot_id": sp.spot_id,
                        "status": status,
                        "distance_cm": round(d, 1),
                        "ts": now()
                    }
                    client.publish(topic, json.dumps(payload), qos=1, retain=True)
                    print(f"{payload['ts']} | {sp.spot_id} => {status} (distance={payload['distance_cm']}cm)")
            time.sleep(READ_INTERVAL_S)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
