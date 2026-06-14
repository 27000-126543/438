import requests
import json
import asyncio
from datetime import datetime, timedelta

BASE = "http://localhost:8000"

login = requests.post(f"{BASE}/api/auth/login", data={"username": "testuser", "password": "Test123456"})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("✅ 登录成功")

# 验证1: assign接口返回完整信息
print("\n" + "=" * 80)
print("验证1: /api/devices/work-orders/{id}/assign 自动派单返回完整信息")
print("=" * 80)

route_code = "ROUTE_V1_" + datetime.utcnow().strftime("%H%M%S")
route_resp = requests.post(f"{BASE}/api/routes/apply", json={
    "route_name": "验证路线1", "route_code": route_code,
    "route_type": "urban", "test_area": "北京市海淀区",
    "start_point": "A", "end_point": "B",
    "total_distance": 5.0, "speed_limit": 60, "road_level": "city_road"
}, headers=headers)
route_id = route_resp.json().get("id")
print(f"  路线 ID: {route_id}")

dev_code = "DEV_V1_" + datetime.utcnow().strftime("%H%M%S")
dev_resp = requests.post(f"{BASE}/api/devices", json={
    "device_code": dev_code, "device_name": "验证设备1",
    "device_type": "camera", "route_id": route_id,
    "latitude": 39.98, "longitude": 116.31,
    "status": "online", "maintenance_skills": ["camera", "5G"]
}, headers=headers)
dev_id = dev_resp.json().get("id")
print(f"  设备 ID: {dev_id}")

from app.database import AsyncSessionLocal
from app.models import RoadsideDevice

async def set_offline():
    async with AsyncSessionLocal() as db:
        await db.execute(
            RoadsideDevice.__table__.update()
            .where(RoadsideDevice.device_code == dev_code)
            .values(last_heartbeat=datetime.utcnow() - timedelta(minutes=35))
        )
        await db.commit()

asyncio.run(set_offline())

check_resp = requests.post(f"{BASE}/api/devices/check-offline", headers=headers)
check_data = check_resp.json()

# 创建一个手动工单用于测试 assign 接口
manual_order_resp = requests.post(f"{BASE}/api/devices/work-orders", json={
    "device_id": dev_id,
    "order_type": "maintenance",
    "priority": "high",
    "description": "验证派单接口返回完整性",
    "required_skills": ["camera", "5G"]
}, headers=headers)
if manual_order_resp.status_code in [200, 201]:
    target_order = manual_order_resp.json()
else:
    orders_resp = requests.get(f"{BASE}/api/devices/work-orders", headers=headers)
    orders = orders_resp.json()
    target_order = None
    for o in orders:
        if o.get("device_id") == dev_id and o.get("status") in ["pending", "assigned"]:
            target_order = o
            break

if target_order:
    order_id = target_order["id"]
    print(f"  目标工单 ID: {order_id}")

    assign_resp = requests.post(f"{BASE}/api/devices/work-orders/{order_id}/assign", json={}, headers=headers)
    print(f"  状态码: {assign_resp.status_code}")
    assign_data = assign_resp.json()
    print(f"  成功: {assign_data.get('success')}")
    print(f"  分配人员: {assign_data.get('assigned_staff_name')}")
    print(f"  预计到场: {assign_data.get('estimated_arrival_time', '无')}")
    has_basis = assign_data.get("assignment_basis") is not None
    print(f"  分配依据: {'有' if has_basis else '无'}")
    rankings = assign_data.get("candidate_rankings", [])
    print(f"  候选人排名: {len(rankings)} 人")
    for c in rankings[:3]:
        print(f"    #{c['rank']} {c['staff_name']}: 得分={c['total_score']}, 可用={c['eligible']}, 淘汰={c.get('elimination_reason', '无')}")
    print(f"  总候选: {assign_data.get('total_candidates')}, 合格: {assign_data.get('eligible_count')}")

    has_rankings = len(rankings) > 0
    has_arrival = assign_data.get("estimated_arrival_time") is not None
    if has_rankings and has_basis and has_arrival:
        print("  ✅ 验证1通过: assign接口返回完整信息")
    else:
        print(f"  ❌ 验证1失败: rankings={has_rankings}, basis={has_basis}, arrival={has_arrival}")
else:
    print("  ⚠️ 没有找到目标工单")

# 验证2: 维护人员负载实时对齐
print("\n" + "=" * 80)
print("验证2: 维护人员负载与真实工单对齐")
print("=" * 80)

staff_resp = requests.get(f"{BASE}/api/maintenance-staff", headers=headers)
staff_list = staff_resp.json()
for s in staff_list:
    wl = s.get("current_workload", "?")
    avail = s.get("available", "?")
    print(f"  {s['name']}: workload={s.get('workload')}, current_workload={wl}, available={avail}")

all_consistent = all(s.get("current_workload") == s.get("workload") for s in staff_list)
if all_consistent:
    print("  ✅ 验证2通过: 所有维护人员 current_workload 与 workload 一致")
else:
    print("  ❌ 验证2失败: workload 不一致")

# 验证3: 事故处置详情时间线顺序
print("\n" + "=" * 80)
print("验证3: 事故处置详情时间线按执行顺序排列")
print("=" * 80)

acc_list_resp = requests.get(f"{BASE}/api/accidents?limit=1", headers=headers)
acc_list = acc_list_resp.json()
if acc_list:
    acc_id = acc_list[0]["id"]
    detail_resp = requests.get(f"{BASE}/api/accidents/{acc_id}/disposal", headers=headers)
    detail_data = detail_resp.json()
    timeline = detail_data.get("timeline", [])
    step_names = [t["step_name"] for t in timeline]
    print(f"  事故ID: {acc_id}")
    print(f"  时间线步骤: {step_names}")

    expected_order = ["create_accident", "generate_analysis", "determine_liability", "trigger_insurance", "notify_police", "notify_rescue"]
    unique_steps = list(dict.fromkeys(step_names))
    is_ordered = all(
        expected_order.index(unique_steps[i]) < expected_order.index(unique_steps[i + 1])
        for i in range(len(unique_steps) - 1)
    ) if len(unique_steps) > 1 else True

    if is_ordered:
        print("  ✅ 验证3通过: 时间线按执行顺序排列")
    else:
        print(f"  ❌ 验证3失败: 步骤顺序不正确 {unique_steps}")
else:
    print("  ⚠️ 没有事故数据")

# 验证4: 重试返回真实时间
print("\n" + "=" * 80)
print("验证4: 重试步骤返回真实的开始/结束时间")
print("=" * 80)

v_vin = "V4X" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
ts = datetime.utcnow().strftime("%H%M%S")
v_resp = requests.post(f"{BASE}/api/vehicles/register", json={
    "vin": v_vin, "license_plate": f"京V4{ts}",
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
v_data = v_resp.json()
v_id = v_data.get("vehicle_id") or v_data.get("id")
print(f"  车辆 ID: {v_id} (响应: {list(v_data.keys())[:5]})")

acc_resp = requests.post(f"{BASE}/api/accidents", json={
    "company_id": 1, "vehicle_id": v_id,
    "report_number": f"ACC-V4-{ts}",
    "accident_type": "collision", "severity": "minor",
    "accident_time": datetime.utcnow().isoformat(),
    "location": "北京市海淀区", "latitude": 39.98, "longitude": 116.31,
    "speed_before": 45.0, "autopilot_mode": "manual",
    "driver_name": "司机", "driver_license": "DL-V4",
    "description": "验证重试返回时间",
    "simulate_failure_step": "trigger_insurance"
}, headers=headers)

if acc_resp.status_code == 201:
    acc_data = acc_resp.json()
    acc_id = acc_data["accident_id"]
    blocked = acc_data.get("blocked_at_step")
    print(f"  事故 ID: {acc_id}, 阻塞点: {blocked}")

    retry_resp = requests.post(f"{BASE}/api/accidents/{acc_id}/retry/trigger_insurance", headers=headers)
    retry_data = retry_resp.json()
    print(f"  重试成功: {retry_data.get('success')}")
    print(f"  重试 started_at: {retry_data.get('started_at')}")
    print(f"  重试 completed_at: {retry_data.get('completed_at')}")
    print(f"  重试 result_data: {'有' if retry_data.get('result_data') else '无'}")

    sub_exec = retry_data.get("subsequent_executed", [])
    print(f"  后续执行: {len(sub_exec)} 步")
    for sub in sub_exec:
        s_at = sub.get("started_at")
        c_at = sub.get("completed_at")
        rd = "有" if sub.get("result_data") else "无"
        print(f"    {sub['step_name']}: started={s_at}, completed={c_at}, result_data={rd}")

    has_times = retry_data.get("started_at") is not None and retry_data.get("completed_at") is not None
    sub_has_times = all(s.get("started_at") and s.get("completed_at") for s in sub_exec) if sub_exec else True

    if has_times and sub_has_times:
        print("  ✅ 验证4通过: 重试返回真实的开始/结束时间，后续步骤也有时间")
    else:
        print(f"  ❌ 验证4失败: has_times={has_times}, sub_has_times={sub_has_times}")
else:
    print(f"  ⚠️ 事故创建失败: {acc_resp.status_code} - {acc_resp.text[:200]}")

print("\n" + "=" * 80)
print("验证完成")
print("=" * 80)
