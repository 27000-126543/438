from app.schemas import (
    TestVehicleBase, TestVehicleCreate, TestVehicleRegister, TestVehicleUpdate,
    TestVehicleResponse, VehicleInsuranceStatus,
    TestRouteBase, TestRouteCreate, TestRouteUpdate, TestRouteResponse,
    RouteConflictDetection, RouteRecommendation, RouteRecommendationRequest,
    ScheduleConflict, RouteApplicationResponse
)

print("=== 所有类导入成功 ===")

# 验证 vehicle.py
fields_create = TestVehicleCreate.model_fields
print("\n--- TestVehicleCreate ---")
print("字段列表:", list(fields_create.keys()))
assert "company_id" in fields_create, "缺少 company_id 字段"
assert not fields_create["company_id"].is_required(), "company_id 应为 Optional"
print("company_id 字段: Optional ✓")

fields_register = TestVehicleRegister.model_fields
print("\n--- TestVehicleRegister ---")
print("字段列表:", list(fields_register.keys()))
assert "company_id" not in fields_register, "TestVehicleRegister 不应有 company_id"
print("无 company_id 字段 ✓")

# 验证 route.py
fields_req = RouteRecommendationRequest.model_fields
print("\n--- RouteRecommendationRequest ---")
print("字段列表:", list(fields_req.keys()))
optional_fields = ["start_point", "end_point", "scheduled_start", "scheduled_end",
                   "road_level", "traffic_condition", "weather_condition"]
for f in optional_fields:
    assert f in fields_req, f"缺少 {f} 字段"
    assert not fields_req[f].is_required(), f"{f} 应为 Optional"
print("所有指定字段均为 Optional ✓")

fields_rec = RouteRecommendation.model_fields
print("\n--- RouteRecommendation ---")
print("字段列表:", list(fields_rec.keys()))
assert "risk_factors" in fields_rec, "缺少 risk_factors 字段"
assert "safety_tips" in fields_rec, "缺少 safety_tips 字段"
print("包含 risk_factors 和 safety_tips ✓")

fields_conflict = ScheduleConflict.model_fields
print("\n--- ScheduleConflict ---")
print("字段列表:", list(fields_conflict.keys()))
print("ScheduleConflict 存在 ✓")

fields_resp = RouteApplicationResponse.model_fields
print("\n--- RouteApplicationResponse ---")
print("字段列表:", list(fields_resp.keys()))
assert "recommended_routes" in fields_resp, "缺少 recommended_routes 字段"
assert "conflicts" in fields_resp, "缺少 conflicts 字段"
assert "risk_score" in fields_resp, "缺少 risk_score 字段"
assert "suggested_speed_limit" in fields_resp, "缺少 suggested_speed_limit 字段"
print("包含所有必需字段 ✓")

print("\n=== 所有验证通过! ===")
