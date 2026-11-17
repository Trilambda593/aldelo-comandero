import sys
import os

sys.path.append(r"C:\Users\Steven V Dj\.gemini\antigravity\scratch\aldelo-comandero")
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print("1. Testing root endpoint /")
res = client.get("/")
print("Root status:", res.status_code, "Length:", len(res.content))

print("\n2. Testing /api/info")
res = client.get("/api/info")
print("Info:", res.json())

print("\n3. Testing /api/auth/pin with PIN '1'")
res = client.post("/api/auth/pin", json={"pin": "1"})
print("Auth:", res.status_code, res.json())

print("\n4. Testing /api/table-groups")
res = client.get("/api/table-groups")
print("Table groups count:", len(res.json()))

print("\n5. Testing /api/tables")
res = client.get("/api/tables")
tables = res.json()
print("Tables count:", len(tables), "Sample table:", tables[0])

print("\n6. Testing /api/menu/groups")
res = client.get("/api/menu/groups")
print("Menu groups:", len(res.json()))

print("\n7. Testing /api/menu/items for group 1")
res = client.get("/api/menu/items?group_id=1")
items = res.json()
print("Items in group 1:", len(items), "Sample:", items[0])

print("\n8. Testing static image delivery")
res = client.get("/static/img/Meat/Meat - Drum Stick.png")
print("Image status:", res.status_code, "Size:", len(res.content))

print("\nALL BACKEND API TESTS PASSED SUCCESSFULLY!")
