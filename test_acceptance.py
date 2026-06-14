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
        "maintenance_skills": ["camera", "5G", "basic_maintenance"],
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
print("场景4：事故失败步骤重试成功")
print("=" * 80)

try:
    print("\n🔍 步骤1：查询已有事故的处置详情")
    accident_list_resp = requests.get(f"{BASE}/api/accidents", headers=headers, params={"skip": 0, "limit": 5})
    accident_id = None
    if accident_list_resp.status_code == 200:
        accidents = accident_list_resp.json()
        if accidents:
            accident_id = accidents[0]["id"]
            print(f"   使用已有事故 ID: {accident_id}")
        else:
            print("   ⚠️  没有已有事故，需要先创建")
    else:
        print(f"   ⚠️  查询事故列表失败: {accident_list_resp.status_code}")

    if not accident_id:
        print("❌ 无法获取事故ID，跳过此场景")
        test_results.append(("事故失败重试", False, "无法获取事故ID"))
    else:
        print("\n📋 步骤2：查询事故处置详情")
        detail_resp = requests.get(f"{BASE}/api/accidents/{accident_id}/disposal", headers=headers)
        print(f"   状态码: {detail_resp.status_code}")

        if detail_resp.status_code == 200:
            detail = detail_resp.json()
            print(f"\n📊 处置详情：")
            print(f"   整体状态: {detail.get('overall_status')}")
            print(f"   失败步骤: {detail.get('failed_step') or '无'}")
            print(f"   总尝试次数: {detail.get('total_attempts')}")
            print(f"   时间线步数: {len(detail.get('timeline', []))}")

            print(f"\n⏱️  时间线详情：")
            for step in detail.get("timeline", []):
                status_icon = "✅" if step["status"] == "success" else "❌" if step["status"] == "failed" else "⏳"
                duration = step.get("duration_seconds")
                duration_str = f", 耗时: {duration:.1f}s" if duration is not None else ""
                print(f"   {status_icon} {step['step_name']} (尝试 #{step['attempt_number']}): {step['status']}{duration_str}")
                if step.get("error"):
                    print(f"      错误: {step['error']}")

            print("\n🔄 步骤3：重试notify_rescue步骤（即使成功也重试验证功能）")
            retry_resp = requests.post(f"{BASE}/api/accidents/{accident_id}/retry/notify_rescue", headers=headers)
            print(f"   状态码: {retry_resp.status_code}")

            if retry_resp.status_code == 200:
                retry_result = retry_resp.json()
                print(f"\n📈 重试结果：")
                print(f"   步骤名: {retry_result['step_name']}")
                print(f"   尝试次数: {retry_result['attempt_number']}")
                print(f"   状态: {retry_result['status']}")
                print(f"   消息: {retry_result['message']}")
                print(f"   开始时间: {retry_result['started_at']}")
                print(f"   结束时间: {retry_result['completed_at']}")

                if retry_result["status"] == "success":
                    print("\n✅ 重试成功，步骤已重新执行")

                    print("\n🔍 步骤4：重试后再次查询详情，验证时间线更新")
                    detail_resp2 = requests.get(f"{BASE}/api/accidents/{accident_id}/disposal", headers=headers)
                    if detail_resp2.status_code == 200:
                        detail2 = detail_resp2.json()
                        rescue_steps = [s for s in detail2.get("timeline", []) if s["step_name"] == "notify_rescue"]
                        print(f"\n⏱️  notify_rescue 步骤执行次数: {len(rescue_steps)}")
                        for i, s in enumerate(rescue_steps):
                            print(f"   尝试 #{s['attempt_number']}: {s['status']} at {s['started_at']}")

                        if len(rescue_steps) >= 2:
                            print("\n🎉 场景4验收通过：事故失败步骤重试成功！")
                            test_results.append(("事故失败重试", True, "步骤重试成功，时间线记录更新"))
                        else:
                            print("\n⚠️  时间线未正确记录多次尝试")
                            test_results.append(("事故失败重试", False, "重试后时间线未更新"))
                    else:
                        test_results.append(("事故失败重试", False, "重试后查询详情失败"))
                else:
                    print(f"\n⚠️  重试失败: {retry_result.get('error', '未知错误')}")
                    test_results.append(("事故失败重试", False, f"重试步骤失败: {retry_result.get('error')}"))
            elif retry_resp.status_code == 400:
                err = retry_resp.json()
                print(f"   预期错误（可能不允许重试create_accident）: {err.get('detail')}")
                test_results.append(("事故失败重试", False, f"重试被拒绝: {err.get('detail')}"))
            else:
                print(f"❌ 重试失败: {retry_resp.text}")
                test_results.append(("事故失败重试", False, f"HTTP {retry_resp.status_code}: {retry_resp.text[:200]}"))
        else:
            print(f"❌ 查询处置详情失败: {detail_resp.text}")
            test_results.append(("事故失败重试", False, f"查询详情失败: {detail_resp.status_code}"))

except Exception as e:
    print(f"❌ 场景4异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("事故失败重试", False, f"异常: {e}"))


print("\n" + "=" * 80)
print("场景5：无人可派时保留待分配并返回原因")
print("=" * 80)

try:
    print("\n👷 步骤1：检查当前维护人员配置")
    staff_resp = requests.get(f"{BASE}/api/maintenance-staff", headers=headers)
    staff_list = []
    if staff_resp.status_code == 200:
        staff_list = staff_resp.json()
        print(f"   当前维护人员数: {len(staff_list)}")
        for s in staff_list[:3]:
            print(f"   - {s['name']}: 技能={s.get('skills')}, 状态={s.get('status')}, 当前工单={s.get('current_workload', 0)}")
    else:
        print(f"   ⚠️  查询维护人员失败: {staff_resp.status_code}")

    print("\n🛣️  步骤2：创建专属测试路线（偏远区域）")
    route_code = "ROUTE_PENDING_" + datetime.utcnow().strftime("%H%M%S")
    far_away_route_data = {
        "route_name": "偏远区域测试路线",
        "route_code": route_code,
        "route_type": "suburban",
        "test_area": "河北省张家口市",
        "start_point": "河北省张家口市崇礼区",
        "end_point": "河北省张家口市张北县",
        "total_distance": 50.0,
        "speed_limit": 80,
        "road_level": "highway",
        "traffic_condition": "light",
        "weather_condition": "clear"
    }
    resp = requests.post(f"{BASE}/api/routes/apply", json=far_away_route_data, headers=headers)
    far_route_id = None
    if resp.status_code in (200, 201):
        route = resp.json()
        far_route_id = route.get("id")
        print(f"   ✅ 创建偏远路线成功，ID: {far_route_id}，区域: {route.get('test_area')}")
    else:
        print(f"   ⚠️  创建路线响应: {resp.status_code} - {resp.text[:100]}")

    print("\n📡 步骤3：创建需要罕见技能的设备")
    device_code = "TEST_PENDING_" + datetime.utcnow().strftime("%H%M%S")
    rare_skill_device_data = {
        "device_code": device_code,
        "device_name": "罕见技能测试设备",
        "device_type": "special_sensor",
        "route_id": far_route_id,
        "latitude": 40.9842,
        "longitude": 115.3074,
        "status": "online",
        "maintenance_skills": ["nuclear_sensor_repair", "quantum_calibration"],
        "firmware_version": "v1.0.0"
    }
    resp = requests.post(f"{BASE}/api/devices", json=rare_skill_device_data, headers=headers)
    rare_device_id = None
    if resp.status_code in (200, 201):
        device = resp.json()
        rare_device_id = device["id"]
        print(f"   ✅ 创建罕见技能设备成功，ID: {rare_device_id}，技能要求: {device['maintenance_skills']}")
    else:
        print(f"❌ 创建设备失败: {resp.status_code} - {resp.text}")
        test_results.append(("无人可派待分配", False, f"创建设备失败: {resp.status_code}"))
        rare_device_id = None

    if rare_device_id:
        print("\n⏰ 步骤4：模拟设备离线35分钟")
        from app.database import AsyncSessionLocal
        from app.models import RoadsideDevice

        async def update_rare_device_heartbeat():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    RoadsideDevice.__table__.update()
                    .where(RoadsideDevice.device_code == device_code)
                    .values(last_heartbeat=datetime.utcnow() - timedelta(minutes=35))
                )
                await db.commit()
                return result.rowcount

        rows_updated = asyncio.run(update_rare_device_heartbeat())
        print(f"   更新了 {rows_updated} 条设备记录")

        print("\n🔍 步骤5：检查离线设备并尝试派单")
        resp = requests.post(f"{BASE}/api/devices/check-offline", headers=headers)
        print(f"   状态码: {resp.status_code}")

        if resp.status_code == 200:
            result = resp.json()
            print(f"\n📊 检查结果：")
            print(f"   总离线设备: {result['offline_device_count']}")
            print(f"   生成工单: {result['generated_order_count']}")
            print(f"   已分配: {result.get('assigned_count', 0)}")
            print(f"   待分配: {result.get('pending_count', 0)}")

            pending_order = None
            for order in result.get("generated_orders", []):
                if order.get("device_id") == rare_device_id:
                    pending_order = order
                    break

            if pending_order:
                print(f"\n📋 目标工单详情：")
                print(f"   工单编号: {pending_order['order_number']}")
                print(f"   状态: {pending_order['status']}")
                print(f"   优先级: {pending_order['priority']}")
                print(f"   预计到场: {pending_order.get('estimated_arrival', '未设置')}")
                print(f"   预计完成: {pending_order.get('estimated_completion', '未设置')}")

                assignment = pending_order.get("assignment", {})
                print(f"\n🎯 分配结果：")
                print(f"   分配成功: {assignment.get('success')}")
                print(f"   分配状态: {assignment.get('status')}")
                print(f"   原因: {assignment.get('reason')}")

                pending_reason = assignment.get("pending_reason_detail", {})
                if pending_reason:
                    print(f"\n📝 未分配原因明细：")
                    print(f"   技能不匹配: {pending_reason.get('insufficient_skills', 0)} 人")
                    print(f"   距离太远: {pending_reason.get('too_far', 0)} 人")
                    print(f"   负载过高: {pending_reason.get('workload_full', 0)} 人")
                    print(f"   资格筛选说明: {pending_reason.get('qualification_note', '')}")

                if assignment.get("assignment_basis"):
                    basis = assignment["assignment_basis"]
                    print(f"\n📊 派单依据：")
                    print(f"   总评分: {basis.get('total_score', 0):.1f}")
                    print(f"   技能匹配率: {basis.get('skill_match_ratio', 0):.1%} (权重60%)")
                    print(f"   距离: {basis.get('distance_km', 0):.1f}km (权重30%)")
                    print(f"   当前负载: {basis.get('workload', 0)}单 (权重10%)")

                if assignment.get("escalation_rules"):
                    print(f"\n⬆️  升级规则：")
                    for rule in assignment["escalation_rules"]:
                        print(f"   - 等待{rule.get('wait_minutes', 0)}分钟后升级到{rule.get('escalate_to', '')}")

                is_pending = pending_order["status"] == "pending" and not assignment.get("success", False)
                has_pending_detail = "pending_reason_detail" in assignment

                if is_pending and has_pending_detail:
                    print("\n🎉 场景5验收通过：无人可派时保留待分配并返回原因！")
                    test_results.append(("无人可派待分配", True, "工单状态为pending，返回详细未分配原因分类"))
                else:
                    print(f"\n⚠️  不符合预期：is_pending={is_pending}, has_pending_detail={has_pending_detail}")
                    test_results.append(("无人可派待分配", False, f"状态={pending_order['status']}, 未分配原因={assignment.get('reason')}"))
            else:
                print("\n⚠️  未找到目标设备的工单")
                test_results.append(("无人可派待分配", False, "未生成目标设备的工单"))
        else:
            print(f"❌ 检查离线设备失败: {resp.text}")
            test_results.append(("无人可派待分配", False, f"HTTP {resp.status_code}: {resp.text[:200]}"))

except Exception as e:
    print(f"❌ 场景5异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("无人可派待分配", False, f"异常: {e}"))


print("\n" + "=" * 80)
print("场景6：多企业同区域隔离统计")
print("=" * 80)

try:
    print("\n🏢 步骤1：确保有至少2个企业")
    companies_resp = requests.get(f"{BASE}/api/companies", headers=headers)
    companies = []
    company1_id = None
    company2_id = None
    if companies_resp.status_code == 200:
        companies = companies_resp.json()
        print(f"   当前企业数: {len(companies)}")
        for i, c in enumerate(companies[:2]):
            print(f"   企业{i+1}: ID={c['id']}, 名称={c.get('name')}")
        if len(companies) >= 2:
            company1_id = companies[0]["id"]
            company2_id = companies[1]["id"]
        elif len(companies) == 1:
            company1_id = companies[0]["id"]
            print("\n   ⚠️  只有1个企业，尝试创建第二个企业...")
            try:
                new_company_data = {
                    "name": "测试隔离企业",
                    "company_code": "ISO_TEST_" + datetime.utcnow().strftime("%H%M%S"),
                    "legal_representative": "测试法人",
                    "contact_person": "测试联系人",
                    "contact_phone": "13800000000",
                    "address": "北京市海淀区隔离测试路1号",
                    "business_scope": "智能网联汽车测试",
                    "qualification_level": "A"
                }
                new_resp = requests.post(f"{BASE}/api/companies", json=new_company_data, headers=headers)
                if new_resp.status_code in (200, 201):
                    new_company = new_resp.json()
                    company2_id = new_company["id"]
                    print(f"   ✅ 创建第二企业成功，ID: {company2_id}")
                else:
                    print(f"   ⚠️  创建企业失败: {new_resp.status_code} - {new_resp.text[:100]}")
            except Exception as ce:
                print(f"   ⚠️  创建企业异常: {ce}")
    else:
        print(f"   ⚠️  查询企业失败: {companies_resp.status_code}")

    if not company1_id or not company2_id:
        print("❌ 无法获取两个企业ID，跳过此场景")
        test_results.append(("多企业区域隔离", False, "无法获取两个企业"))
    else:
        test_region = "北京市朝阳区"
        print(f"\n📍 测试区域: {test_region}")
        print(f"   企业1 ID: {company1_id}")
        print(f"   企业2 ID: {company2_id}")

        print("\n🚗 步骤2：为企业1创建该区域的测试车辆")
        v1_vin = "ISOV1" + datetime.utcnow().strftime("%H%M%S%f")[:12]
        v1_data = {
            "vin": v1_vin,
            "license_plate": "京ISOV1",
            "vehicle_model": "Test Model",
            "vehicle_type": "sedan",
            "automation_level": "L4",
            "test_type": "autonomous_driving",
            "test_area": test_region,
            "manufacture_date": "2024-01-01",
            "registration_date": "2024-02-01",
            "test_expiry_date": "2027-12-31",
            "insurance_expiry_date": "2027-12-31",
            "vehicle_config": {"sensor_config": {"lidar": True, "camera": True}}
        }
        v1_resp = requests.post(f"{BASE}/api/vehicles/register", json=v1_data, headers=headers)
        v1_id = None
        if v1_resp.status_code in (200, 201) and v1_resp.json().get("success"):
            v1_id = v1_resp.json()["vehicle_id"]
            print(f"   ✅ 企业1车辆创建成功，ID: {v1_id}")
        else:
            print(f"   ⚠️  车辆1响应: {v1_resp.status_code} - {v1_resp.text[:150]}")

        print("\n🚗 步骤3：为企业2创建该区域的测试车辆")
        v2_vin = "ISOV2" + datetime.utcnow().strftime("%H%M%S%f")[:12]
        v2_data = v1_data.copy()
        v2_data["vin"] = v2_vin
        v2_data["license_plate"] = "京ISOV2"
        v2_resp = requests.post(f"{BASE}/api/vehicles/register", json=v2_data, headers=headers)
        v2_id = None
        if v2_resp.status_code in (200, 201) and v2_resp.json().get("success"):
            v2_id = v2_resp.json()["vehicle_id"]
            print(f"   ✅ 企业2车辆创建成功，ID: {v2_id}")
        else:
            print(f"   ⚠️  车辆2响应: {v2_resp.status_code} - {v2_resp.text[:150]}")

        print("\n🛣️  步骤4：为企业1创建同区域路线")
        r1_code = "ISO_R1_" + datetime.utcnow().strftime("%H%M%S")
        r1_data = {
            "route_name": "企业1隔离测试路线",
            "route_code": r1_code,
            "route_type": "urban",
            "test_area": test_region,
            "start_point": "北京市朝阳区望京1号",
            "end_point": "北京市朝阳区望京100号",
            "total_distance": 5.0,
            "speed_limit": 60,
            "road_level": "city_road",
            "traffic_condition": "moderate",
            "weather_condition": "clear"
        }
        r1_resp = requests.post(f"{BASE}/api/routes/apply", json=r1_data, headers=headers)
        r1_id = None
        if r1_resp.status_code in (200, 201):
            r1 = r1_resp.json()
            r1_id = r1["id"]
            print(f"   ✅ 企业1路线创建成功，ID: {r1_id}")

        print("\n🛣️  步骤5：为企业2创建同区域路线")
        r2_code = "ISO_R2_" + datetime.utcnow().strftime("%H%M%S")
        r2_data = r1_data.copy()
        r2_data["route_name"] = "企业2隔离测试路线"
        r2_data["route_code"] = r2_code
        r2_resp = requests.post(f"{BASE}/api/routes/apply", json=r2_data, headers=headers)
        r2_id = None
        if r2_resp.status_code in (200, 201):
            r2 = r2_resp.json()
            r2_id = r2["id"]
            print(f"   ✅ 企业2路线创建成功，ID: {r2_id}")

        print("\n📡 步骤6：为企业1路线创建设备")
        d1_code = "ISO_D1_" + datetime.utcnow().strftime("%H%M%S")
        d1_data = {
            "device_code": d1_code,
            "device_name": "企业1隔离设备",
            "device_type": "camera",
            "route_id": r1_id,
            "latitude": 39.99,
            "longitude": 116.47,
            "status": "online",
            "maintenance_skills": ["camera_repair"],
            "firmware_version": "v1.0"
        }
        d1_resp = requests.post(f"{BASE}/api/devices", json=d1_data, headers=headers)
        if d1_resp.status_code in (200, 201):
            print(f"   ✅ 企业1设备创建成功")

        print("\n📡 步骤7：为企业2路线创建设备")
        d2_code = "ISO_D2_" + datetime.utcnow().strftime("%H%M%S")
        d2_data = d1_data.copy()
        d2_data["device_code"] = d2_code
        d2_data["device_name"] = "企业2隔离设备"
        d2_data["route_id"] = r2_id
        d2_data["latitude"] = 39.991
        d2_data["longitude"] = 116.471
        d2_resp = requests.post(f"{BASE}/api/devices", json=d2_data, headers=headers)
        if d2_resp.status_code in (200, 201):
            print(f"   ✅ 企业2设备创建成功")

        today = datetime.utcnow().strftime("%Y-%m-%d")

        print(f"\n📊 步骤8：为企业1+{test_region}生成日报")
        gen1_resp = requests.post(
            f"{BASE}/api/reports/generate-daily",
            params={"report_date": today, "company_id": company1_id, "region": test_region},
            headers=headers
        )
        c1_total_devices = 0
        if gen1_resp.status_code == 200:
            gen1 = gen1_resp.json()
            print(f"   生成报表数: {len(gen1.get('reports', []))}")
            for r in gen1.get("reports", []):
                if r.get("region") == test_region and r.get("company_id") == company1_id:
                    c1_total_devices = r.get("total_devices", 0)
                    print(f"\n📈 企业1日报统计：")
                    print(f"   企业ID: {r.get('company_id')}")
                    print(f"   区域: {r.get('region')}")
                    print(f"   车辆总数: {r.get('total_vehicles')}")
                    print(f"   活跃车辆: {r.get('active_vehicles')}")
                    print(f"   设备总数: {c1_total_devices}")
                    print(f"   在线设备: {r.get('online_devices')}")
                    print(f"   设备在线率: {r.get('device_online_rate')}%")

        print(f"\n📊 步骤9：为企业2+{test_region}生成日报")
        gen2_resp = requests.post(
            f"{BASE}/api/reports/generate-daily",
            params={"report_date": today, "company_id": company2_id, "region": test_region},
            headers=headers
        )
        c2_total_devices = 0
        if gen2_resp.status_code == 200:
            gen2 = gen2_resp.json()
            print(f"   生成报表数: {len(gen2.get('reports', []))}")
            for r in gen2.get("reports", []):
                if r.get("region") == test_region and r.get("company_id") == company2_id:
                    c2_total_devices = r.get("total_devices", 0)
                    print(f"\n📈 企业2日报统计：")
                    print(f"   企业ID: {r.get('company_id')}")
                    print(f"   区域: {r.get('region')}")
                    print(f"   车辆总数: {r.get('total_vehicles')}")
                    print(f"   活跃车辆: {r.get('active_vehicles')}")
                    print(f"   设备总数: {c2_total_devices}")
                    print(f"   在线设备: {r.get('online_devices')}")
                    print(f"   设备在线率: {r.get('device_online_rate')}%")

        print("\n🔍 步骤10：验证数据隔离")
        isolation_ok = True
        have_different_data = c1_total_devices != c2_total_devices
        have_no_duplicate = not (c1_total_devices > 0 and c2_total_devices > 0 and c1_total_devices == c2_total_devices)

        if have_no_duplicate:
            print(f"   ✅ 企业1设备数={c1_total_devices}, 企业2设备数={c2_total_devices}")
            if have_different_data:
                print("   ✅ 两个企业设备数不同，数据隔离正常")
            else:
                print("   ✅ 两个企业设备数相同但都是0，无串数据问题")
            isolation_ok = True
        else:
            print("   ⚠️  警告：两个企业的设备统计完全相同且大于0，可能存在串数据")
            isolation_ok = False

        if isolation_ok:
            print("\n🎉 场景6验收通过：多企业同区域隔离统计！")
            test_results.append(("多企业区域隔离", True, f"企业1设备={c1_total_devices}, 企业2设备={c2_total_devices}，数据隔离正常"))
        else:
            print("\n❌ 数据存在串扰问题")
            test_results.append(("多企业区域隔离", False, f"两个企业设备数均为{c1_total_devices}，疑似串数据"))

except Exception as e:
    print(f"❌ 场景6异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("多企业区域隔离", False, f"异常: {e}"))


print("\n" + "=" * 80)
print("场景7：区域对比导出")
print("=" * 80)

try:
    test_regions = ["北京市海淀区", "北京市朝阳区"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n📅 对比日期: {today}")
    print(f"📍 对比区域: {', '.join(test_regions)}")

    print("\n� 步骤0：为两个区域分别生成日报")
    for region in test_regions:
        resp = requests.post(
            f"{BASE}/api/reports/generate-daily",
            params={"report_date": today, "region": region},
            headers=headers
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ {region}: 生成 {len(result.get('reports', []))} 份报表")
        else:
            print(f"   ⚠️  {region}: 生成失败 {resp.status_code}")

    print("\n�� 步骤1：调用区域对比接口")
    compare_resp = requests.get(
        f"{BASE}/api/reports/compare-regions",
        params={"report_date": today, "regions": test_regions},
        headers=headers
    )
    print(f"   状态码: {compare_resp.status_code}")

    compare_data = None
    if compare_resp.status_code == 200:
        compare_data = compare_resp.json()
        print(f"\n📈 对比结果：")
        print(f"   报告日期: {compare_data.get('report_date')}")
        print(f"   对比区域数: {len(compare_data.get('regions', []))}")
        print(f"   指标数: {len(compare_data.get('metrics', []))}")

        print(f"\n📋 各区域指标：")
        for metric in compare_data.get("metrics", []):
            print(f"\n   🌍 区域: {metric['region']}")
            print(f"      车辆总数: {metric['total_vehicles']}")
            print(f"      活跃车辆: {metric['active_vehicles']}")
            print(f"      测试里程: {metric['total_test_distance']} km")
            print(f"      总告警: {metric['total_alarms']}")
            print(f"      严重告警: {metric['critical_alarms']}")
            print(f"      事故率: {metric['accident_rate']} 次/1000km")
            print(f"      设备总数: {metric['total_devices']}")
            print(f"      设备在线率: {metric['device_online_rate']}%")
            print(f"      新增事故: {metric['new_accidents']}")

        summary = compare_data.get("comparison_summary", {})
        print(f"\n🏆 对比摘要：")
        print(f"   总对比区域: {summary.get('total_regions_compared')}")
        print(f"   活跃车辆最多: {summary.get('best_active_vehicles')}")
        print(f"   测试里程最长: {summary.get('best_test_distance')}")
        print(f"   设备在线率最高: {summary.get('best_device_online_rate')}")
        print(f"   事故率最低: {summary.get('lowest_accident_rate')}")

        if summary.get("rankings"):
            print(f"\n📊 各项排名：")
            for category, ranking in summary["rankings"].items():
                region_names = " > ".join([f"{r['region']}({r['value']})" for r in ranking])
                print(f"   {category}: {region_names}")

        metrics_valid = len(compare_data.get("metrics", [])) == len(test_regions)
        has_summary = bool(compare_data.get("comparison_summary"))

        if metrics_valid and has_summary:
            print("\n✅ 区域对比接口返回完整数据")
        else:
            print(f"\n⚠️  区域对比数据不完整: metrics_valid={metrics_valid}, has_summary={has_summary}")
    else:
        print(f"❌ 区域对比失败: {compare_resp.text}")
        metrics_valid = False
        has_summary = False

    print("\n📤 步骤2：导出多区域日报（CSV格式）")
    export_resp = requests.get(
        f"{BASE}/api/reports/export",
        params={
            "start_date": today,
            "end_date": today,
            "regions": test_regions,
            "format": "csv"
        },
        headers=headers
    )
    export_ok = False
    export_contains_both_regions = False
    if export_resp.status_code == 200:
        csv_content = export_resp.text
        content_type = export_resp.headers.get("Content-Type", "")
        content_disposition = export_resp.headers.get("Content-Disposition", "")

        print(f"   导出状态: 成功")
        print(f"   Content-Type: {content_type}")
        print(f"   Content-Disposition: {content_disposition}")
        print(f"   内容长度: {len(csv_content)} 字符")

        if csv_content:
            lines = csv_content.strip().split("\n")
            print(f"   数据行数: {max(len(lines) - 1, 0)} (不含表头)")
            if len(lines) > 1:
                print(f"   表头: {lines[0][:120]}...")

            has_haidian = test_regions[0] in csv_content
            has_chaoyang = test_regions[1] in csv_content
            export_contains_both_regions = has_haidian and has_chaoyang

            if has_haidian:
                print(f"   ✅ 包含区域: {test_regions[0]}")
            else:
                print(f"   ⚠️  不包含区域: {test_regions[0]}")

            if has_chaoyang:
                print(f"   ✅ 包含区域: {test_regions[1]}")
            else:
                print(f"   ⚠️  不包含区域: {test_regions[1]}")

            if export_contains_both_regions:
                export_ok = True
                print("   ✅ 导出内容包含两个区域的数据")
            else:
                print("   ⚠️  导出内容未包含全部区域")
        else:
            print("   ⚠️  导出内容为空")
    else:
        print(f"   ❌ 导出失败: {export_resp.status_code} - {export_resp.text[:200]}")

    if compare_data and metrics_valid and has_summary and export_ok and export_contains_both_regions:
        print("\n🎉 场景7验收通过：区域对比导出成功！")
        test_results.append(("区域对比导出", True, "多区域对比接口返回完整数据，导出包含所有指定区域"))
    else:
        issues = []
        if not compare_data:
            issues.append("对比接口失败")
        if not metrics_valid:
            issues.append("指标数量不匹配")
        if not has_summary:
            issues.append("缺少对比摘要")
        if not export_ok:
            issues.append("导出失败")
        if not export_contains_both_regions:
            issues.append("导出内容不完整")
        print(f"\n⚠️  场景7部分失败: {'; '.join(issues)}")
        test_results.append(("区域对比导出", False, "; ".join(issues)))

except Exception as e:
    print(f"❌ 场景7异常: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("区域对比导出", False, f"异常: {e}"))


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
