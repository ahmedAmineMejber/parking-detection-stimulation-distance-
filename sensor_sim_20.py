import time, json, random
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER_HOST = "broker.emqx.io"
BROKER_PORT = 1883

SPOTS = [f"P{i:02d}" for i in range(1, 21)]

THRESHOLD_CM = 50.0
READ_INTERVAL_S = 1.0
DEBOUNCE_N = 4

DIST_FREE = (150, 280)
DIST_PARK = (10, 35)
NOISE_CM = 2.0

def now():
    return datetime.now().isoformat(timespec="seconds")

class Spot:
    def __init__(self, spot_id: str):
        self.spot_id = spot_id
        self.has_car = False
        self.activity = random.uniform(0.6, 1.6)
        self.next_switch = time.time() + self._free_duration()
        self.stable_status = "FREE"
        self.occ_count = 0
        self.free_count = 0

    def _park_duration(self):
        base = random.uniform(45, 180)
        return base / self.activity

    def _free_duration(self):
        base = random.uniform(30, 150)
        return base / self.activity

    def _update_world(self):
        t = time.time()
        if t >= self.next_switch:
            self.has_car = not self.has_car
            self.next_switch = t + (self._park_duration() if self.has_car else self._free_duration())

    def read_distance(self) -> float:
        self._update_world()
        base = random.uniform(*(DIST_PARK if self.has_car else DIST_FREE))
        noise = random.uniform(-NOISE_CM, NOISE_CM)
        return max(0.0, base + noise)

    def update_debounced_status(self, distance_cm: float) -> str:
        detected_occ = distance_cm < THRESHOLD_CM

        if detected_occ:
            self.occ_count += 1
            self.free_count = 0
        else:
            self.free_count += 1
            self.occ_count = 0

        if self.stable_status != "OCCUPIED" and self.occ_count >= DEBOUNCE_N:
            self.stable_status = "OCCUPIED"
            self.occ_count = 0
            self.free_count = 0

        elif self.stable_status != "FREE" and self.free_count >= DEBOUNCE_N:
            self.stable_status = "FREE"
            self.occ_count = 0
            self.free_count = 0

        return self.stable_status

def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="SmartPark2026_P1"
    )
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()

    spots = [Spot(s) for s in SPOTS]
    last_published = {s: None for s in SPOTS}

    try:
        while True:
            for sp in spots:
                d = sp.read_distance()
                status = sp.update_debounced_status(d)

                if status != last_published[sp.spot_id]:
                    last_published[sp.spot_id] = status
                    topic = f"smart_parking_2026/parking/spots/{sp.spot_id}/status"
                    payload = {
                        "spot_id": sp.spot_id,
                        "status": status,
                        "distance_cm": round(d, 1),
                        "threshold_cm": THRESHOLD_CM,
                        "debounce_n": DEBOUNCE_N,
                        "ts": now()
                    }
                    client.publish(topic, json.dumps(payload), qos=1, retain=True)
                    print(f"{payload['ts']} | {sp.spot_id} => {status} (distance={payload['distance_cm']}cm)")
            time.sleep(READ_INTERVAL_S)

    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
