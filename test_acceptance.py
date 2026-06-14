import requests
import json
import sys
import asyncio
from datetime import datetime, timedelta

BASE = "http://localhost:8000"

print("=" * 80)
print("智能网联汽车测试与运营监管系统 - 验收测试")
print("=" * 80)

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
    print("✅ 登录成功，获取访问令牌")
except Exception as e:
    print(f"❌ 登录异常: {e}")
    sys.exit(1)

test_results = []

print("\n" + "=" * 80)
print("场景1：事故一键处置成功")
print("=" * 80)

try:
    print("\n📝 步骤1：创建测试车辆（如果不存在）")
    vehicles_resp = requests.get(f"{BASE}/api/vehicles", headers=headers)
    vehicles = vehicles_resp.json()
    vehicle_id = None
    if vehicles:
        vehicle_id = vehicles[0]["id"]
        print(f"   使用现有车辆 ID: {vehicle_id}")
    else:
        vehicle_data = {
            "vin": "TESTACC0000000001",
            "license_plate": "京TEST001",
            "vehicle_model": "Test Model",
            "vehicle_type": "sedan",
            "automation_level": "L4",
            "test_type": "autonomous_driving",
            "test_area": "北京市海淀区",
            "manufacture_date": "2024-01-01",
            "registration_date": "2024-02-01",
            "test_expiry_date": "2027-12-31",
            "insurance_expiry_date": "2027-12-31",
            "vehicle_config": {
                "sensor_config": {"lidar": True, "camera": True, "radar": True, "ultrasonic": True},
                "compute_platform": {"processor": "Test", "memory_gb": 32, "storage_gb": 1024},
                "communication_module": {"type": "5G", "protocol": "C-V2X"},
                "safety_system": {"emergency_brake": True, "driver_monitoring": True}
            }
        }
        resp = requests.post(f"{BASE}/api/vehicles/register", json=vehicle_data, headers=headers)
        result = resp.json()
        if result.get("success"):
            vehicle_id = result["vehicle_id"]
            print(f"   ✅ 创建测试车辆成功，ID: {vehicle_id}")
        else:
            print(f"   ⚠️  车辆创建响应: {result}")

    if not vehicle_id:
        print("❌ 无法获取测试车辆，跳过此场景")
        test_results.append(("事故一键处置", False, "无法获取测试车辆"))
    else:
        print("\n🚗 步骤2：提交事故并一键处置")
        accident_time = datetime.utcnow().isoformat()
        vehicle_logs = [
            {
                "timestamp": (datetime.utcnow() - timedelta(seconds=30)).isoformat(),
                "speed": 65,
                "autopilot_enabled": True,
                "latitude": 39.9842,
                "longitude": 116.3074,
                "brake_status": False,
                "lane_departure": False,
                "obstacle_detected": False
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(seconds=15)).isoformat(),
                "speed": 75,
                "autopilot_enabled": True,
                "latitude": 39.9845,
                "longitude": 116.3078,
                "brake_status": False,
                "lane_departure": True,
                "obstacle_detected": True,
                "obstacle_distance": 2.5
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(seconds=5)).isoformat(),
                "speed": 45,
                "acceleration": -9.5,
                "autopilot_enabled": True,
                "latitude": 39.9847,
                "longitude": 116.3081,
                "brake_status": True,
                "lane_departure": True,
                "obstacle_detected": True,
                "obstacle_distance": 1.2
            }
        ]
        roadside_data = {
            "camera_id": "CAM_001",
            "traffic_light": "green",
            "weather": "clear",
            "road_condition": "dry",
            "nearby_vehicles": 3,
            "pedestrians": 2
        }

        accident_data = {
            "company_id": 1,
            "vehicle_id": vehicle_id,
            "report_number": "",
            "accident_type": "rear_end",
            "severity": "moderate",
            "accident_time": accident_time,
            "location": "北京市海淀区中关村大街",
            "latitude": 39.9847,
            "longitude": 116.3081,
            "weather_condition": "clear",
            "road_condition": "dry",
            "traffic_condition": "moderate",
            "speed_before": 75.0,
            "autopilot_mode": "autopilot",
            "driver_name": "测试司机",
            "driver_license": "TEST12345",
            "passenger_count": 2,
            "description": "自动驾驶模式下发生追尾事故",
            "injuries": "轻微擦伤",
            "damages": "车辆前部损坏",
            "vehicle_log_data": vehicle_logs,
            "roadside_sensor_data": roadside_data
        }

        resp = requests.post(f"{BASE}/api/accidents", json=accident_data, headers=headers)
        print(f"   状态码: {resp.status_code}")

        if resp.status_code == 201:
            result = resp.json()
            print(f"\n📊 事故一键处置结果：")
            print(f"   事故ID: {result['accident_id']}")
            print(f"   报告编号: {result['report_number']}")
            print(f"   全部成功: {result['all_succeeded']}")

            print(f"\n📋 各步骤执行状态：")
            for step in result["steps"]:
                status_icon = "✅" if step["success"] else "❌"
                print(f"   {status_icon} {step['step']}: {step['message']}")
                if step.get("error"):
                    print(f"      错误: {step['error']}")

            print(f"\n📈 分析摘要：")
            if result.get("analysis_summary"):
                summary = result["analysis_summary"]
                print(f"   车辆: {summary['accident_summary'].get('license_plate')}")
                print(f"   地点: {summary['accident_summary'].get('location')}")
                print(f"   严重程度: {summary['accident_summary'].get('severity')}")
                print(f"   时间线事件数: {len(summary.get('timeline_reconstruction', []))}")
                print(f"   建议措施: {len(summary.get('recommended_actions', []))} 条")
            else:
                print("   ⚠️  无分析摘要")

            print(f"\n⚖️  责任划分结果：")
            if result.get("liability_result"):
                liability = result["liability_result"]
                print(f"   判定方: {liability['determined_by']}")
                print(f"   判定依据: {liability['determination_basis']}")
                print(f"   责任分配:")
                for party in liability["responsible_parties"]:
                    print(f"      - {party['party']}: {party['ratio']}%")
            else:
                print("   ⚠️  无责任划分结果")

            print(f"\n💳 保险理赔：")
            print(f"   理赔编号: {result.get('insurance_claim_number', '无')}")

            print(f"\n🚔 通知状态：")
            print(f"   交警通知时间: {result.get('police_notified_at', '未通知')}")
            print(f"   救援通知时间: {result.get('rescue_notified_at', '未通知')}")

            all_steps_ok = all(s["success"] for s in result["steps"])
            has_analysis = result.get("analysis_summary") is not None
            has_liability = result.get("liability_result") is not None
            has_insurance = result.get("insurance_claim_number") is not None
            has_police = result.get("police_notified_at") is not None
            has_rescue = result.get("rescue_notified_at") is not None

            if all_steps_ok and has_analysis and has_liability and has_insurance and has_police and has_rescue:
                print("\n🎉 场景1验收通过：事故一键处置成功！")
                test_results.append(("事故一键处置", True, "所有步骤执行成功，返回完整数据"))
            else:
                print("\n⚠️  场景1部分成功，请检查上述输出")
                test_results.append(("事故一键处置", False, "部分步骤失败或数据不完整"))
        else:
            print(f"❌ 提交事故失败: {resp.text}")
            test_results.append(("事故一键处置", False, f"HTTP {resp.status_code}: {resp.text[:200]}"))

except Exception as e:
    print(f"❌ 场景1异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("事故一键处置", False, f"异常: {e}"))

print("\n" + "=" * 80)
print("场景2：离线设备自动派单成功")
print("=" * 80)

try:
    print("\n🛣️  步骤0：创建测试路线（带区域信息）")
    route_code = "ROUTE_TEST_" + datetime.utcnow().strftime("%H%M%S")
    route_data = {
        "route_name": "中关村测试路线",
        "route_code": route_code,
        "route_type": "urban",
        "test_area": "北京市海淀区",
        "start_point": "北京市海淀区中关村大街1号",
        "end_point": "北京市海淀区中关村大街100号",
        "total_distance": 5.5,
        "speed_limit": 60,
        "road_level": "city_road",
        "traffic_condition": "moderate",
        "weather_condition": "clear"
    }
    resp = requests.post(f"{BASE}/api/routes/apply", json=route_data, headers=headers)
    route_id = None
    if resp.status_code in (200, 201):
        route = resp.json()
        route_id = route.get("id")
        print(f"   ✅ 创建路线成功，ID: {route_id}，区域: {route.get('test_area')}")
    else:
        print(f"   ⚠️  创建路线响应: {resp.status_code} - {resp.text[:100]}")
        print(f"   尝试获取现有路线...")
        resp_list = requests.get(f"{BASE}/api/routes", headers=headers)
        if resp_list.status_code == 200:
            routes = resp_list.json()
            if routes:
                route = routes[0]
                route_id = route["id"]
                print(f"   使用现有路线 ID: {route_id}")

    print("\n📡 步骤1：创建测试路侧设备")
    device_code = "TEST_OFFLINE_" + datetime.utcnow().strftime("%H%M%S")
    device_data = {
        "device_code": device_code,
        "device_name": "测试自动派单设备",
        "device_type": "camera",
        "route_id": route_id,
        "latitude": 39.9842,
        "longitude": 116.3074,
        "status": "online",
        "maintenance_skills": ["camera_repair", "basic_maintenance"],
        "firmware_version": "v1.0.0"
    }
    resp = requests.post(f"{BASE}/api/devices", json=device_data, headers=headers)
    if resp.status_code in (200, 201):
        device = resp.json()
        device_id = device["id"]
        print(f"   ✅ 创建设备成功，ID: {device_id}，编号: {device['device_code']}")
    else:
        print(f"❌ 创建设备失败: {resp.status_code} - {resp.text}")
        test_results.append(("离线设备自动派单", False, f"创建设备失败: {resp.status_code}"))
        device_id = None

    if device_id:
        print("\n⏰ 步骤2：上报心跳后直接修改数据库模拟离线超过30分钟")
        heartbeat_data = {
            "device_code": device_code,
            "status": "online",
            "latitude": 39.9842,
            "longitude": 116.3074,
            "firmware_version": "v1.0.0",
            "sensor_data": {"temperature": 25}
        }
        resp = requests.post(f"{BASE}/api/devices/heartbeat", json=heartbeat_data, headers=headers)
        print(f"   心跳上报状态: {resp.status_code}")
        
        print("\n🗄️  直接修改数据库心跳时间为35分钟前")
        from app.database import AsyncSessionLocal
        from app.models import RoadsideDevice
        
        async def update_heartbeat():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    RoadsideDevice.__table__.update()
                    .where(RoadsideDevice.device_code == device_code)
                    .values(last_heartbeat=datetime.utcnow() - timedelta(minutes=35))
                )
                await db.commit()
                return result.rowcount
        
        rows_updated = asyncio.run(update_heartbeat())
        print(f"   更新了 {rows_updated} 条设备记录")

        print("\n🔍 步骤3：检查离线设备并自动派单")
        resp = requests.post(f"{BASE}/api/devices/check-offline", headers=headers)
        print(f"   状态码: {resp.status_code}")

        if resp.status_code == 200:
            result = resp.json()
            print(f"\n📊 检查结果：")
            print(f"   消息: {result['message']}")
            print(f"   离线设备数: {result['offline_device_count']}")
            print(f"   生成工单数量: {result['generated_order_count']}")
            print(f"   已分配工单: {result.get('assigned_count', 0)}")
            print(f"   待分配工单: {result.get('pending_count', 0)}")

            print(f"\n📋 工单详情：")
            for order in result.get("generated_orders", []):
                print(f"\n   工单编号: {order['order_number']}")
                print(f"   设备ID: {order['device_id']}")
                print(f"   优先级: {order['priority']}")
                print(f"   状态: {order['status']}")

                assignment = order.get("assignment", {})
                if assignment.get("success"):
                    print(f"   ✅ 分配状态: 成功")
                    print(f"   分配人员: {assignment.get('staff_name')} (ID: {assignment.get('staff_id')})")
                    print(f"   匹配技能: {', '.join(assignment.get('matched_skills', []))}")
                    print(f"   匹配评分: {assignment.get('score', 0):.1f}")
                    print(f"   分配消息: {assignment.get('message')}")
                else:
                    print(f"   ⚠️  分配状态: 未分配")
                    print(f"   原因: {assignment.get('reason')}")
                    print(f"   说明: {assignment.get('message')}")

            if result.get("assigned_count", 0) > 0:
                assigned_order = next(
                    (o for o in result.get("generated_orders", []) if o["status"] == "assigned"),
                    None
                )
                if assigned_order and assigned_order.get("assignment", {}).get("success"):
                    print("\n🎉 场景2验收通过：离线设备自动派单成功！")
                    test_results.append(("离线设备自动派单", True, "工单生成并自动分配成功"))
                else:
                    print("\n⚠️  工单已生成但未成功分配，检查是否有可用维护人员")
                    test_results.append(("离线设备自动派单", False, "工单生成但未自动分配"))
            elif result.get("generated_order_count", 0) > 0:
                print("\n⚠️  工单已生成但无匹配人员，检查维护人员初始化数据")
                test_results.append(("离线设备自动派单", False, "无可用或匹配的维护人员"))
            else:
                print("\n⚠️  未生成工单，可能设备未检测为离线")
                test_results.append(("离线设备自动派单", False, "未检测到离线设备或未生成工单"))
        else:
            print(f"❌ 检查离线设备失败: {resp.text}")
            test_results.append(("离线设备自动派单", False, f"HTTP {resp.status_code}: {resp.text[:200]}"))

except Exception as e:
    print(f"❌ 场景2异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("离线设备自动派单", False, f"异常: {e}"))

print("\n" + "=" * 80)
print("场景3：按区域生成和导出日报")
print("=" * 80)

try:
    test_region = "北京市海淀区"
    print(f"\n📍 测试区域: {test_region}")

    print("\n📊 步骤1：生成指定区域的日报")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    resp = requests.post(
        f"{BASE}/api/reports/generate-daily",
        params={"report_date": today, "region": test_region},
        headers=headers
    )
    print(f"   状态码: {resp.status_code}")

    if resp.status_code == 200:
        result = resp.json()
        print(f"   消息: {result['message']}")
        print(f"   报表日期: {result['report_date']}")
        print(f"   生成报表数: {len(result.get('reports', []))}")

        regional_report = None
        for report in result.get("reports", []):
            if report.get("region") == test_region:
                regional_report = report
                break

        if regional_report:
            print(f"\n📈 区域日报统计数据：")
            print(f"   区域: {regional_report.get('region')}")
            print(f"   总车辆数: {regional_report.get('total_vehicles')}")
            print(f"   活跃车辆: {regional_report.get('active_vehicles')}")
            print(f"   测试里程: {regional_report.get('total_test_distance')} km")
            print(f"   总告警数: {regional_report.get('total_alarms')}")
            print(f"   严重告警: {regional_report.get('critical_alarms')}")
            print(f"   新事故数: {regional_report.get('new_accidents')}")
            print(f"   事故率: {regional_report.get('accident_rate')} 次/1000km")
            print(f"   设备总数: {regional_report.get('total_devices')}")
            print(f"   在线设备: {regional_report.get('online_devices')}")
            print(f"   设备在线率: {regional_report.get('device_online_rate')}%")

            region_metrics = all([
                regional_report.get("region") == test_region,
                regional_report.get("total_vehicles") is not None,
                regional_report.get("active_vehicles") is not None,
                regional_report.get("total_test_distance") is not None,
                regional_report.get("total_alarms") is not None,
                regional_report.get("accident_rate") is not None,
                regional_report.get("device_online_rate") is not None,
            ])

            if region_metrics:
                print("\n✅ 区域日报包含完整统计指标")
            else:
                print("\n⚠️  区域日报部分指标缺失")
        else:
            print(f"\n⚠️  未找到区域为 '{test_region}' 的日报")
            region_metrics = False

        print("\n📋 步骤2：查询今日同区域的报表列表")
        resp = requests.get(
            f"{BASE}/api/reports",
            params={"region": test_region, "start_date": today, "end_date": today},
            headers=headers
        )
        if resp.status_code == 200:
            queried_reports = resp.json()
            print(f"   查询到报表数: {len(queried_reports)}")

            queried_report = None
            for r in queried_reports:
                if r.get("region") == test_region:
                    queried_report = r
                    break

            if queried_report and regional_report:
                metrics_match = all([
                    queried_report.get("total_vehicles") == regional_report.get("total_vehicles"),
                    queried_report.get("active_vehicles") == regional_report.get("active_vehicles"),
                    queried_report.get("total_test_distance") == regional_report.get("total_test_distance"),
                    queried_report.get("total_alarms") == regional_report.get("total_alarms"),
                    queried_report.get("accident_rate") == regional_report.get("accident_rate"),
                    queried_report.get("device_online_rate") == regional_report.get("device_online_rate"),
                ])

                if metrics_match:
                    print("   ✅ 查询结果与生成结果一致")
                else:
                    print("   ⚠️  查询结果与生成结果不一致")
            else:
                print("   ⚠️  无法对比查询和生成结果")
        else:
            print(f"   ⚠️  查询报表失败: {resp.status_code}")

        print("\n📤 步骤3：导出同区域的日报（CSV格式）")
        resp = requests.get(
            f"{BASE}/api/reports/export",
            params={
                "start_date": today,
                "end_date": today,
                "region": test_region,
                "format": "csv"
            },
            headers=headers
        )
        if resp.status_code == 200:
            content_disposition = resp.headers.get("Content-Disposition", "")
            content_type = resp.headers.get("Content-Type", "")
            csv_content = resp.text

            print(f"   导出状态: 成功")
            print(f"   Content-Type: {content_type}")
            print(f"   Content-Disposition: {content_disposition}")
            print(f"   内容长度: {len(csv_content)} 字符")

            if csv_content:
                lines = csv_content.strip().split("\n")
                print(f"   数据行数: {len(lines) - 1} (不含表头)")
                if len(lines) > 1:
                    print(f"   表头: {lines[0][:100]}...")
                    print(f"   首行数据: {lines[1][:100]}...")

                if test_region in csv_content:
                    print(f"   ✅ 导出内容包含区域 '{test_region}'")
                    export_contains_region = True
                else:
                    print(f"   ⚠️  导出内容不包含区域信息")
                    export_contains_region = False

                if regional_report and len(lines) > 1:
                    export_match = str(regional_report.get("active_vehicles")) in csv_content and \
                                   str(regional_report.get("total_test_distance")) in csv_content
                    if export_match:
                        print("   ✅ 导出内容与生成报表数据一致")
                    else:
                        print("   ⚠️  导出内容与生成报表数据可能不一致")
                else:
                    export_match = False
            else:
                print("   ⚠️  导出内容为空")
                export_contains_region = False
                export_match = False
        else:
            print(f"   ❌ 导出失败: {resp.status_code} - {resp.text[:200]}")
            export_contains_region = False
            export_match = False

        if regional_report and region_metrics and export_contains_region:
            print("\n🎉 场景3验收通过：按区域生成和导出日报成功！")
            test_results.append(("按区域日报", True, "生成、查询、导出均按区域正确筛选"))
        else:
            print("\n⚠️  场景3部分功能待验证")
            issues = []
            if not regional_report:
                issues.append("未找到区域日报")
            if not region_metrics:
                issues.append("指标不完整")
            if not export_contains_region:
                issues.append("导出内容不含区域")
            test_results.append(("按区域日报", False, "; ".join(issues)))
    else:
        print(f"❌ 生成日报失败: {resp.text}")
        test_results.append(("按区域日报", False, f"HTTP {resp.status_code}: {resp.text[:200]}"))

except Exception as e:
    print(f"❌ 场景3异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("按区域日报", False, f"异常: {e}"))

print("\n" + "=" * 80)
print("验收测试总结")
print("=" * 80)

passed = sum(1 for _, success, _ in test_results if success)
total = len(test_results)

print(f"\n总测试数: {total}")
print(f"通过数: {passed}")
print(f"失败数: {total - passed}")
print(f"通过率: {(passed/total*100):.1f}%\n")

for name, success, detail in test_results:
    status = "✅ 通过" if success else "❌ 失败"
    print(f"{status} - {name}")
    print(f"   {detail}\n")

if passed == total:
    print("🎉 所有验收场景全部通过！")
    sys.exit(0)
else:
    print(f"⚠️  有 {total - passed} 个场景未通过，请检查上述详情")
    sys.exit(1)
