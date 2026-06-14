import requests, json
BASE = "http://localhost:8000"
resp = requests.post(f"{BASE}/api/auth/login", data={"username": "testuser", "password": "Test123456"})
token = resp.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

print("=== 报表导出 ===")
r = requests.get(f"{BASE}/api/reports/export", headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误: {r.text[:800]}")
else:
    print(f"成功! 内容长度: {len(r.content)}")

print("\n=== 报表导出(带参数) ===")
r = requests.get(f"{BASE}/api/reports/export?start_date=2026-06-14&end_date=2026-06-14&format=csv", headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误: {r.text[:800]}")
else:
    print(f"成功! 内容长度: {len(r.content)}")

print("\n=== JSON导出 ===")
r = requests.get(f"{BASE}/api/reports/export?start_date=2026-06-14&end_date=2026-06-14&format=json", headers=h)
print(f"状态: {r.status_code}")
if r.status_code != 200:
    print(f"错误: {r.text[:800]}")
else:
    print(f"成功! 内容: {r.text[:300]}")
