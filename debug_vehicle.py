import requests
import json
from datetime import datetime

BASE = "http://localhost:8000"
login = requests.post(f"{BASE}/api/auth/login", data={"username": "testuser", "password": "Test123456"})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

v_vin = "DEBUG" + datetime.utcnow().strftime("%H%M%S%f")[:9]
ts = datetime.utcnow().strftime("%H%M%S")
resp = requests.post(f"{BASE}/api/vehicles/register", json={
    "vin": v_vin, "license_plate": f"京D{ts}",
    "vehicle_model": "Test", "vehicle_type": "sedan",
    "automation_level": "L4", "test_area": "北京市海淀区",
    "test_type": "performance",
    "manufacture_date": "2025-01-01", "registration_date": "2025-06-01",
    "test_expiry_date": "2027-12-31", "insurance_expiry_date": "2027-12-31",
    "vehicle_config": {
        "sensor_config": {"lidar": True, "camera": True, "radar": True, "ultrasonic": True},
        "compute_platform": {"processor": "Test", "memory_gb": 32, "storage_gb": 1024},
        "communication_module": {"type": "5G", "protocol": "C-V2X"},
        "safety_system": {"emergency_brake": True, "driver_monitoring": True}
    }
}, headers=headers)
print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
print(f"Status: {resp.status_code}")
