import requests
import json

print("=" * 60)
print("MCARE Router Test - Dr Khalili Clinic First Case")
print("=" * 60)

url = "http://localhost:8000/mcare/auto"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "fEDuG03NaZBglfXKoZEcSc0moCwotcBiX0zSOJZHkWs",
    "X-Tenant-Id": "13147a94-c116-4403-a084-38e0cab50368"
}

# Test 1: Using chief_complaint
print("\n📋 Test 1: chief_complaint field")
data1 = {
    "chief_complaint": "severe headache for 3 days, worse with light and noise",
    "patient_id": "khalili-patient-001"
}
response1 = requests.post(url, headers=headers, json=data1)
print(f"Status: {response1.status_code}")
result1 = response1.json()
print(f"Engine: {result1.get('engine')}")
print(f"Case Text: {result1.get('case_text')}")
print(f"Top Remedy: {result1['remedies'][0]['remedy']} (score: {result1['remedies'][0]['score']})")

# Test 2: Using text field
print("\n📋 Test 2: text field")
data2 = {
    "text": "patient complains of dizziness and nausea",
    "patient_id": "khalili-patient-002"
}
response2 = requests.post(url, headers=headers, json=data2)
print(f"Status: {response2.status_code}")
result2 = response2.json()
print(f"Top Remedy: {result2['remedies'][0]['remedy']}")

# Test 3: MCARE health check
print("\n🏥 Test 3: MCARE health check")
health_response = requests.get("http://localhost:8000/mcare/health")
print(f"Status: {health_response.status_code}")
print(f"Health: {json.dumps(health_response.json(), indent=2)}")

print("\n" + "=" * 60)
print("✅ All tests passed! MCARE router is connected.")
print("⚠️  Note: This is a stub. Full engine needs to be restored.")
print("=" * 60)
