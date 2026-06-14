import requests
import sys
from datetime import datetime, timedelta

BASE = "http://localhost:8000"

# 登录
login_data = {
    "username": "testuser",
    "password": "Test123456"
}
login_resp = requests.post(f"{BASE}/api/auth/login", data=login_data)
if login_resp.status_code != 200:
    print(f"❌ 登录失败: {login_resp.text}")
    sys.exit(1)
token = login_resp.json()["access_token"]
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}
print("✅ 登录成功")

# 创建车辆
v_vin = "TESTSCENE8" + datetime.utcnow().strftime("%H%M%S%f")[:9]
timestamp = datetime.utcnow().strftime("%H%M%S")
v_data = {
    "vin": v_vin,
    "license_plate": f"京S8{timestamp}",
    "vehicle_model": "Test Model",
    "vehicle_type": "sedan",
    "automation_level": "L4",
    "manufacture_date": "2025-01-01",
    "registration_date": "2025-06-01",
    "test_expiry_date": "2027-12-31",
    "insurance_expiry_date": "2027-12-31",
    "test_area": "北京市海淀区",
    "test_type": "performance",
    "vehicle_config": {
        "sensor_config": {
            "lidar": {"count": 1, "range": 200},
            "camera": {"count": 4, "resolution": "4K"},
            "radar": {"count": 5, "range": 150},
            "ultrasonic": {"count": 8, "range": 5}
        },
        "compute_platform": {
            "processor": "NVIDIA Orin",
            "memory_gb": 32,
            "storage_gb": 512
        },
        "communication_module": {
            "type": "5G",
            "protocol": "TCP/IP"
        },
        "safety_system": {
            "emergency_brake": True,
            "driver_monitoring": True
        }
    }
}

v_resp = requests.post(f"{BASE}/api/vehicles/register", json=v_data, headers=headers)
print(f"\n车辆注册状态: {v_resp.status_code}")
if v_resp.status_code != 200 or not v_resp.json().get("success"):
    print(f"❌ 车辆创建失败: {v_resp.text}")
    sys.exit(1)
v_id = v_resp.json()["vehicle_id"]
print(f"✅ 车辆创建成功，ID: {v_id}")

# 提交事故
accident_data = {
    "company_id": 1,
    "vehicle_id": v_id,
    "report_number": f"ACC-SCENE8-{datetime.utcnow().strftime('%H%M%S')}",
    "accident_type": "collision",
    "severity": "minor",
    "accident_time": datetime.utcnow().isoformat(),
    "location": "北京市海淀区中关村大街1号",
    "latitude": 39.98,
    "longitude": 116.31,
    "speed_before": 45.0,
    "autopilot_mode": "manual",
    "driver_name": "测试司机",
    "driver_license": "DL-SCENE8",
    "description": "测试事故编排",
    "simulate_failure_step": "trigger_insurance",
}

print(f"\n提交事故...")
try:
    acc_resp = requests.post(f"{BASE}/api/accidents", json=accident_data, headers=headers, timeout=30)
    print(f"状态码: {acc_resp.status_code}")
    if acc_resp.status_code == 201:
        acc_data = acc_resp.json()
        print(f"事故ID: {acc_data.get('accident_id')}")
        print(f"阻塞点: {acc_data.get('blocked_at_step')}")
        print(f"全部成功: {acc_data.get('all_succeeded')}")
        print(f"\n步骤:")
        for s in acc_data.get("steps", []):
            status = "✅" if s.get("success") else "❌"
            print(f"  {status} {s['step']}: {s['message']}")
            if s.get("error"):
                print(f"     错误: {s['error']}")
    else:
        print(f"响应: {acc_resp.text[:5000]}")
except Exception as e:
    print(f"异常: {e}")
    import traceback
    traceback.print_exc()
