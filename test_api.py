import requests
import json
import sys

BASE = "http://localhost:8000"

print("=" * 70)
print("智能网联汽车测试与运营监管系统 - 核心API测试")
print("=" * 70)

# 登录获取token
try:
    resp = requests.post(
        f"{BASE}/api/auth/login",
        data={"username": "testuser", "password": "Test123456"}
    )
    if resp.status_code != 200:
        print(f"❌ 登录失败: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ [1/9] 用户认证 - 登录成功")
except Exception as e:
    print(f"❌ 登录异常: {e}")
    sys.exit(1)

# 1. 测试车辆注册 - 合格配置
print("\n📋 [2/9] 测试车辆注册校验（合格配置）")
vehicle_data = {
    "vin": "LBV1Z3108KM000002",
    "license_plate": "京A20002",
    "vehicle_model": "Model X Pro",
    "vehicle_type": "SUV",
    "automation_level": "L4",
    "test_type": "autonomous_driving",
    "test_area": "北京市海淀区",
    "manufacture_date": "2024-06-01",
    "registration_date": "2024-07-01",
    "test_expiry_date": "2027-12-31",
    "insurance_expiry_date": "2027-12-14",
    "vehicle_config": {
        "sensor_config": {"lidar": True, "camera": True, "radar": True, "ultrasonic": True},
        "compute_platform": {"processor": "NVIDIA Orin X", "memory_gb": 64, "storage_gb": 1024},
        "communication_module": {"type": "5G", "protocol": "C-V2X"},
        "safety_system": {"emergency_brake": True, "driver_monitoring": True}
    }
}
resp = requests.post(f"{BASE}/api/vehicles/register", json=vehicle_data, headers=headers)
print(f"   状态码: {resp.status_code}")
if resp.status_code in (200, 201):
    result = resp.json()
    if result.get("success"):
        print(f"   ✅ 车辆注册成功！ID: {result.get('vehicle_id')}")
        print(f"   车牌: {result.get('vehicle',{}).get('license_plate')}，等级: {result.get('vehicle',{}).get('automation_level')}")
    else:
        print(f"   ❌ 注册被拒绝: {result.get('message')}")
        errors = result.get("errors", [])
        for e in errors[:3]:
            print(f"      - {e.get('field')}: {e.get('message')}")
else:
    print(f"   ⚠️  响应: {resp.text[:300]}")

# 2. 测试车辆注册 - 不合格（保险过期+配置缺失）
print("\n🚫 [3/9] 测试车辆注册校验（不合格配置）")
bad_vehicle = {
    "vin": "LBV1Z3108KM000099",
    "license_plate": "京A99999",
    "vehicle_model": "Bad Model",
    "automation_level": "L8",
    "insurance_expiry_date": "2025-01-01",
    "test_expiry_date": "2026-01-01",
    "vehicle_config": {
        "sensor_config": {"lidar": False, "camera": False, "radar": False},
        "compute_platform": {"processor": "Old CPU", "memory_gb": 4},
        "communication_module": {"type": "2G"},
        "safety_system": {"emergency_brake": False}
    }
}
resp = requests.post(f"{BASE}/api/vehicles/register", json={**vehicle_data, **bad_vehicle}, headers=headers)
print(f"   状态码: {resp.status_code}")
if resp.status_code in (200, 201):
    result = resp.json()
    if not result.get("success"):
        errors = result.get("errors", [])
        print(f"   ✅ 正确拒绝注册！发现 {len(errors)} 个问题:")
        for e in errors[:5]:
            print(f"      ❌ {e.get('field')}: {e.get('message')}")
        notice = result.get("correction_notice", {})
        if notice:
            print(f"   📧 补正通知已生成，截止: {notice.get('deadline')[:30]}")
    else:
        print(f"   ⚠️  错误：本应拒绝但通过了")

# 3. 测试路线推荐
print("\n🛣️  [4/9] 测试路线推荐与冲突检测")
route_req = {
    "start_point": "中关村软件园",
    "end_point": "望京SOHO",
    "scheduled_start": "2026-06-16T09:00:00",
    "scheduled_end": "2026-06-16T11:00:00",
    "road_level": "urban_primary",
    "traffic_condition": "moderate",
    "weather_condition": "rainy"
}
resp = requests.post(f"{BASE}/api/routes/recommend", json=route_req, headers=headers)
print(f"   状态码: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    routes = data.get("recommended_routes", [])
    conflicts = data.get("conflicts", [])
    print(f"   ✅ 推荐 {len(routes)} 条安全路线")
    for i, r in enumerate(routes[:3]):
        print(f"      路线{i+1}: {r.get('road_level')}，风险:{r.get('accident_risk_score')}，限速:{r.get('speed_limit')}km/h")
        tips = r.get("safety_tips", [])
        if tips:
            print(f"        提示: {tips[0][:40]}")
    print(f"   建议综合限速: {data.get('suggested_speed_limit')} km/h")
    print(f"   综合风险评分: {data.get('risk_score')}")
    if conflicts:
        print(f"   ⚠️  检测到 {len(conflicts)} 个时段冲突")
else:
    print(f"   ⚠️  响应: {resp.text[:300]}")

# 4. 测试实时数据上报 - 超速场景
print("\n📡 [5/9] 测试实时数据上报与告警检测")
data_point = {
    "vehicle_id": 1,
    "latitude": 39.9847,
    "longitude": 116.3047,
    "speed": 125.0,
    "heading": 90.0,
    "autopilot_enabled": True,
    "autopilot_mode": "highway_pilot",
    "sensor_data": {"lidar": "ok", "camera": "ok"},
    "lane_departure": True,
    "obstacle_detected": True,
    "obstacle_distance": 2.5
}
resp = requests.post(f"{BASE}/api/monitoring/data", json=data_point, headers=headers)
print(f"   状态码: {resp.status_code}，速度125km/h + 车道偏离 + 近距离障碍物")
if resp.status_code in (200, 201):
    result = resp.json()
    num = result.get("alarms_generated", 0)
    print(f"   ✅ 数据上报成功")
    print(f"   ⚠️  自动生成 {num} 条告警工单:")
    for a in result.get("alarms", [])[:4]:
        print(f"      🔔 {a.get('alarm_level').upper()}: {a.get('title')} - 分配给: {a.get('assigned_to', '待分配')}")

# 5. 查询告警列表
resp = requests.get(f"{BASE}/api/monitoring/alarms", headers=headers)
if resp.status_code == 200:
    alarms = resp.json()
    count = len(alarms) if isinstance(alarms, list) else alarms.get("total", 0)
    print(f"\n   📊 当前累计告警总数: {count}")

# 6. 路侧设备管理
print("\n📱 [6/9] 测试路侧设备管理（离线检测+工单分配）")

# 心跳上报
resp = requests.post(f"{BASE}/api/devices/heartbeat", json={
    "device_code": "RSU-TEST-001",
    "device_name": "测试路侧设备001",
    "device_type": "rsu",
    "latitude": 39.98,
    "longitude": 116.30,
    "status": "online",
    "last_heartbeat": "2026-06-14T06:00:00"
}, headers=headers)
print(f"   设备创建/心跳: {resp.status_code}")

# 检查离线设备
resp = requests.post(f"{BASE}/api/devices/check-offline", headers=headers)
print(f"   离线检测状态: {resp.status_code}")
if resp.status_code == 200:
    result = resp.json()
    if isinstance(result, dict):
        print(f"   ✅ 离线设备: {result.get('offline_count', 0)}台")
        generated = result.get("generated_orders", [])
        if isinstance(generated, list):
            print(f"   🔧 生成维修工单: {len(generated)}个")
            for o in generated[:2]:
                if isinstance(o, dict):
                    print(f"      - {o.get('title', '工单')}: {o.get('assigned_to', '自动分配中')}")

# 7. 测试结题报告
print("\n📝 [7/9] 测试结题报告（里程/覆盖率/脱管统计）")
vehicle_id_for_report = 1
resp = requests.get(f"{BASE}/api/completion/vehicle/{vehicle_id_for_report}/stats", headers=headers)
print(f"   车辆{vehicle_id_for_report}统计: {resp.status_code}")
if resp.status_code == 200:
    stats = resp.json()
    print(f"   ✅ 累积测试里程: {stats.get('total_distance', 0)} km")
    print(f"   🎯 场景覆盖率: {stats.get('scene_coverage_rate', 0)}%")
    print(f"   🔄 脱管次数: {stats.get('disengagement_count', 0)}次")
    print(f"   ⚠️  告警数: {stats.get('total_alarms', 0)}次")

# 8. 数据管理 - 目录和脱敏
print("\n💾 [8/9] 测试数据管理（脱敏+目录+查询）")
try:
    resp = requests.post(f"{BASE}/api/data/catalogs/generate", json={
        "data_type": "vehicle_realtime",
        "time_range_start": "2026-06-01T00:00:00",
        "time_range_end": "2026-06-14T23:59:59"
    }, headers=headers)
    print(f"   自动生成目录: {resp.status_code}")
except Exception as e:
    print(f"   目录生成: 跳过 ({e})")

# 脱敏测试
resp = requests.post(f"{BASE}/api/data/desensitize", json={
    "phone": "13800138000",
    "email": "test@example.com",
    "vin": "LBV1Z3108KM000001",
    "license_plate": "京A12345",
    "data": {"driver_name": "张三"}
}, headers=headers)
if resp.status_code == 200:
    result = resp.json()
    print(f"   ✅ 脱敏测试成功:")
    print(f"      手机号: {result.get('phone', 'N/A')}")
    print(f"      车牌号: {result.get('license_plate', 'N/A')}")

# 查询脱敏数据
resp = requests.get(f"{BASE}/api/data/query?data_type=vehicle_realtime", headers=headers)
print(f"   数据查询: {resp.status_code}，自动脱敏")

# 9. 每日运营报表
print("\n📊 [9/9] 测试运营报表（多维度统计）")
resp = requests.post(f"{BASE}/api/reports/generate-daily", json={
    "report_date": "2026-06-14",
    "region": "北京市海淀区"
}, headers=headers)
print(f"   日报生成: {resp.status_code}")
if resp.status_code == 200:
    report = resp.json()
    if isinstance(report, dict):
        print(f"   ✅ 报表生成成功")
        print(f"   🚗 活跃车辆数: {report.get('active_vehicles', 0)} / {report.get('total_vehicles', 0)}")
        print(f"   🛣️  测试里程: {report.get('total_test_distance', 0)} km")
        print(f"   🤖 自动驾驶: {report.get('autopilot_distance', 0)} km")
        ar = report.get('accident_rate', 0)
        print(f"   💥 事故率: {ar} {'✅' if ar == 0 else '⚠️'}")
        dor = report.get('device_online_rate', 0)
        print(f"   📡 设备在线率: {dor}%")
        print(f"   🔔 告警数: {report.get('total_alarms', 0)} (严重:{report.get('critical_alarms',0)})")
        print(f"   🏥 维修工单: {report.get('total_maintenance_orders', 0)}")
        print(f"   📈 安全指数: {report.get('safety_index', 'N/A')}")

# 报表导出
try:
    resp = requests.get(f"{BASE}/api/reports/export?start_date=2026-06-14&end_date=2026-06-14&format=csv", headers=headers)
    print(f"   📤 报表导出CSV: {resp.status_code}")
except:
    pass

# 统计概览
resp = requests.get(f"{BASE}/api/reports/statistics/overview", headers=headers)
if resp.status_code == 200:
    overview = resp.json()
    if isinstance(overview, dict):
        print(f"\n   🎯 系统总览:")
        for k, v in list(overview.items())[:6]:
            print(f"      {k}: {v}")

print("\n" + "=" * 70)
print("🎉 全部核心API测试完成！")
print("📚 Swagger文档: http://localhost:8000/docs")
print("🏥 健康检查:   http://localhost:8000/health")
print("=" * 70)
