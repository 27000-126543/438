from app.schemas.vehicle import VehicleRegisterCreate

print("=== 测试 VehicleRegisterCreate Pydantic 模型 ===")
print()

# 测试缺少所有字段的情况
print("1. 测试空对象:")
data = {}
try:
    obj = VehicleRegisterCreate(**data)
    print("   ✅ 创建成功（不会报422错误）")
    print(f"   vin: {obj.vin}")
    print(f"   license_plate: {obj.license_plate}")
    print(f"   vehicle_model: {obj.vehicle_model}")
    print(f"   vehicle_type: {obj.vehicle_type}")
    print(f"   test_type: {obj.test_type}")
    print(f"   test_area: {obj.test_area}")
    print(f"   manufacture_date: {obj.manufacture_date}")
    print(f"   registration_date: {obj.registration_date}")
    print(f"   test_expiry_date: {obj.test_expiry_date}")
    print(f"   insurance_expiry_date: {obj.insurance_expiry_date}")
except Exception as e:
    print(f"   ❌ 创建失败: {e}")

print()

# 测试只传部分字段
print("2. 测试只传 vin 和 license_plate:")
data2 = {'vin': '123456789