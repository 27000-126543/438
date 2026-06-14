import requests
import json
from datetime import datetime, timedelta

BASE = "http://localhost:8000"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiY29tcGFueV9pZCI6MSwiZXhwIjoxNzUwMTM5NjAwfQ.test"
}

# 先登录获取正确的token
login_data = {
    "username": "testuser",
    "password": "Test123456"
}
login_resp = requests.post(f"{BASE}/api/auth/login", data=login_data)
if login_resp.status_code == 200:
    token = login_resp.json().get("access_token")
    headers["Authorization"] = f"Bearer {token}"
    print(f"✅ 登录成功")
else:
    print(f"❌ 登录失败: {login_resp.status_code} - {login_resp.text}")
    exit(1)

# 先创建一个车辆
v_vin = "TESTDEBUG" + datetime.utcnow().strftime("%H%M%S%f")[:9]
v_data = {
    "vin": v_vin,
    "license_plate": f"京DBG{datetime.utcnow().strftime('%H%M%S')}",
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
print(f"\n车辆注册响应: {v_resp.status_code}")
print(v_resp.text[:500])

if v_resp.status_code != 200 or not v_resp.json().get("success"):
    print("❌ 车辆创建失败")
    exit(1)

v_id = v_resp.json()["vehicle_id"]
print(f"✅ 车辆创建成功，ID: {v_id}")

# 提交事故，故意让 trigger_insurance 失败
accident_data = {
    "company_id": 1,
    "vehicle_id": v_id,
    "report_number": f"ACC-DEBUG-{datetime.utcnow().strftime('%H%M%S')}",
    "accident_type": "collision",
    "severity": "minor",
    "accident_time": datetime.utcnow().isoformat(),
    "location": "北京市海淀区中关村大街1号",
    "latitude": 39.98,
    "longitude": 116.31,
    "speed_before": 45.0,
    "autopilot_mode": "manual",
    "driver_name": "测试司机",
    "driver_license": "DL-DEBUG",
    "description": "测试事故编排",
    "simulate_failure_step": "trigger_insurance",
}

print(f"\n提交事故数据: {json.dumps(accident_data, indent=2, ensure_ascii=False)[:500]}")

acc_resp = requests.post(f"{BASE}/api/accidents", json=accident_data, headers=headers)
print(f"\n事故提交响应: {acc_resp.status_code}")
if acc_resp.status_code == 201:
    acc_data = acc_resp.json()
    print(f"事故ID: {acc_data.get('accident_id')}")
    print(f"阻塞点: {acc_data.get('blocked_at_step')}")
    print(f"全部成功: {acc_data.get('all_succeeded')}")
    print(f"\n步骤执行情况:")
    for s in acc_data.get("steps", []):
        status = "✅" if s.get("success") else "❌"
        print(f"  {status} {s['step']}: {s['message']}")
        if s.get("error"):
            print(f"     错误: {s['error']}")
else:
    print(f"响应内容: {acc_resp.text[:3000]}")
