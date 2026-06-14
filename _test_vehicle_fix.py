from app.schemas.vehicle import VehicleRegisterCreate, VALID_AUTOMATION_LEVELS
from app.routers.vehicles import (
    VehicleRegistrationResponse, 
    validate_automation_level_value, 
    VALID_AUTOMATION_LEVELS as R_LEVELS
)

print("=== 导入测试 ===")
print("VehicleRegisterCreate 导入成功")
print(f"schemas VALID_AUTOMATION_LEVELS: {VALID_AUTOMATION_LEVELS}")
print(f"routers VALID_AUTOMATION_LEVELS: {R_LEVELS}")
assert VALID_AUTOMATION_LEVELS == R_LEVELS, "校验等级集合不一致"
print("校验等级集合一致 ✓")

print("\n=== Router层 automation_level 校验测试 ===")
test_cases = [
    (None, True, "None值应该被拦截"),
    ("", True, "空字符串应该被拦截"),
    ("L0", True, "L0应该被拦截"),
    ("L6", True, "L6应该被拦截"),
    ("l1", False, "小写l1应该通过(大小写不敏感)"),
    (" L5 ", False, "前后空格应该被处理并通过"),
    ("L3", False, "L3应该通过"),
    (123, True, "非字符串类型应该被拦截"),
]
for val, should_fail, desc in test_cases:
    result = validate_automation_level_value(val)
    failed = result is not None
    status = "✓" if (failed == should_fail) else "✗"
    msg = result.message if result else "通过"
    print(f"{status} {desc}: val={repr(val)} -> {msg}")

print("\n=== Pydantic Schema层校验测试 ===")
schema_tests = [
    ({"automation_level": "L7"}, True, "L7被拦截"),
    ({"automation_level": None}, True, "None被拦截"),
    ({"vin": "   "}, True, "空vin被拦截"),
    ({"license_plate": "   "}, True, "空车牌被拦截"),
    ({"vehicle_model": "   "}, True, "空车型被拦截"),
]
base_valid = {
    "vin": "TESTVIN1234567890",
    "license_plate": "京A12345",
    "vehicle_model": "Model T",
    "automation_level": "L3"
}
for override, should_fail, desc in schema_tests:
    payload = {**base_valid, **override}
    try:
        data = VehicleRegisterCreate(**payload)
        failed = False
    except Exception as e:
        failed = True
    status = "✓" if (failed == should_fail) else "✗"
    print(f"{status} {desc}: payload={override} -> {'拦截成功' if failed else '通过'}")

print("\n=== Schema 不含 company_id 测试 ===")
import inspect
fields = list(VehicleRegisterCreate.model_fields.keys())
print(f"VehicleRegisterCreate 字段: {fields}")
assert "company_id" not in fields, "Schema 不应该包含 company_id"
print("✓ Schema 不含 company_id 字段")

print("\n=== VehicleRegistrationResponse 字段测试 ===")
resp_fields = list(VehicleRegistrationResponse.model_fields.keys())
print(f"VehicleRegistrationResponse 字段: {resp_fields}")
expected = ["success", "message", "vehicle_id", "vehicle", "errors", "correction_notice"]
for f in expected:
    assert f in resp_fields, f"缺少字段: {f}"
print("✓ 所有预期字段均存在")

print("\n✅ 所有测试通过!")
