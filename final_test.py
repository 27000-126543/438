import requests
BASE = "http://localhost:8000"
resp = requests.post(f"{BASE}/api/auth/login", data={"username": "testuser", "password": "Test123456"})
token = resp.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

print("=== 测试报表导出CSV ===")
r = requests.get(f"{BASE}/api/reports/export", headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误详情: {r.text[:800]}")
else:
    print(f"内容长度: {len(r.content)}")

print("\n=== 测试实时数据上报（检查安全员分配） ===")
r = requests.post(f"{BASE}/api/monitoring/data", json={
    "vehicle_id": 1, "latitude": 39.98, "longitude": 116.30,
    "speed": 130.0, "autopilot_enabled": True,
    "lane_departure": True, "obstacle_detected": True, "obstacle_distance": 1.5
}, headers=h)
print(f"状态: {r.status_code}")
if r.status_code in (200, 201):
    d = r.json()
    print(f"生成告警: {d.get('alarms_generated')}个")
    for a in d.get('alarms', []):
        print(f"  - {a.get('alarm_level')}: {a.get('title')} -> 分配给: {a.get('assigned_to')}")

print("\n=== 测试维修工单分配 ===")
r = requests.get(f"{BASE}/api/devices/work-orders", headers=h)
print(f"工单列表状态: {r.status_code}")
if r.status_code == 200 and r.json():
    order_id = r.json()[0]['id']
    print(f"尝试自动分配工单 {order_id}")
    r = requests.post(f"{BASE}/api/devices/work-orders/{order_id}/assign", headers=h)
    print(f"分配状态: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"分配给: {d.get('assigned_staff_name')}")
        print(f"技能匹配: {d.get('matched_skills')}")
        if d.get('missing_skills'):
            print(f"缺少技能: {d.get('missing_skills')}")
    else:
        print(f"错误: {r.text[:300]}")
