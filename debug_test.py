import requests, json
BASE = "http://localhost:8000"
resp = requests.post(f"{BASE}/api/auth/login", data={"username": "testuser", "password": "Test123456"})
token = resp.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

print("=== 1. 路线推荐 ===")
r = requests.post(f"{BASE}/api/routes/recommend", json={
    "start_point": "中关村", "end_point": "望京",
    "scheduled_start": "2026-06-16T09:00:00"
}, headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误: {r.text[:500]}")
else:
    d = r.json()
    print(f"  推荐路线: {len(d.get('recommended_routes', []))}条")
    print(f"  风险评分: {d.get('risk_score')}")
    print(f"  建议限速: {d.get('suggested_speed_limit')}")

print("\n=== 2. 监控数据上报 ===")
r = requests.post(f"{BASE}/api/monitoring/data", json={
    "vehicle_id": 1, "latitude": 39.98, "longitude": 116.30,
    "speed": 85.0, "autopilot_enabled": True
}, headers=h)
print(f"状态: {r.status_code}")
if r.status_code not in (200, 201):
    print(f"错误: {r.text[:500]}")
else:
    d = r.json()
    print(f"  生成告警: {d.get('alarms_generated', 0)}个")

print("\n=== 3. 数据目录生成 ===")
r = requests.post(f"{BASE}/api/data/catalogs/generate", json={
    "data_type": "vehicle_realtime",
    "time_range_start": "2026-06-01T00:00:00",
    "time_range_end": "2026-06-14T23:59:59"
}, headers=h)
print(f"状态: {r.status_code}")
if r.status_code not in (200, 201):
    print(f"错误: {r.text[:500]}")

print("\n=== 4. 报表导出 ===")
r = requests.get(f"{BASE}/api/reports/export?start_date=2026-06-14&end_date=2026-06-14", headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误: {r.text[:500]}")

print("\n=== 5. 车辆注册（不合格） ===")
r = requests.post(f"{BASE}/api/vehicles/register", json={
    "vin": "TESTBADVIN001",
    "license_plate": "BAD001",
    "automation_level": "L8",
    "insurance_expiry_date": "2025-01-01",
    "test_expiry_date": "2026-01-01"
}, headers=h)
print(f"状态: {r.status_code}")
print(f"响应: {r.text[:500]}")

print("\n=== 6. 设备心跳 ===")
r = requests.post(f"{BASE}/api/devices/heartbeat", json={
    "device_code": "RSU-TEST-002",
    "device_name": "测试设备002",
    "device_type": "rsu",
    "latitude": 39.98,
    "longitude": 116.30,
    "status": "online"
}, headers=h)
print(f"状态: {r.status_code}")
if r.status_code not in (200, 201):
    print(f"错误: {r.text[:500]}")
