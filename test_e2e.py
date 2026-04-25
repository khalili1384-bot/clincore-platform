import requests
import uuid
import json

# Step 1: Create API Key
tenant_id = str(uuid.uuid4())
print("=== STEP 1: Create API Key ===")
print(f"Tenant ID: {tenant_id}")

r = requests.post(
    'http://localhost:8000/super-admin/api-keys/create',
    headers={'X-Super-Admin-Key': 'Bkfjb1-Yr3NGqYMMGHBiZkuDobvy1H68hBP7XFkFVNQ'},
    json={'tenant_id': tenant_id, 'role': 'doctor'}
)

print(f"Status: {r.status_code}")
result = r.json()
print(json.dumps(result, indent=2, ensure_ascii=False))

if r.status_code != 200:
    print(f"\nERROR: Failed to create API key")
    exit(1)

api_key = result.get('api_key')
print(f"\nAPI Key: {api_key}")
print(f"Tenant ID: {tenant_id}")

# Save credentials
with open('test_credentials.txt', 'w') as f:
    f.write(f"API_KEY={api_key}\nTENANT_ID={tenant_id}")

print("\n=== STEP 2: Create Patient ===")
patient_data = {
    "full_name": "علی احمدی",
    "date_of_birth": "1990-01-15",
    "gender": "male"
}

r = requests.post(
    'http://localhost:8000/patients',
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json=patient_data
)

print(f"Status: {r.status_code}")
patient_result = r.json()
print(json.dumps(patient_result, indent=2, ensure_ascii=False))

if r.status_code != 200:
    print(f"\nERROR: Failed to create patient")
    exit(1)

patient_id = patient_result.get('id')
print(f"\nPatient ID: {patient_id}")

# Step 3: Create Encounter
print("\n=== STEP 3: Create Encounter ===")
encounter_data = {
    "patient_id": patient_id,
    "encounter_type": "outpatient",
    "chief_complaint": "سردرد شدید، اضطراب، بی‌خوابی"
}

r = requests.post(
    'http://localhost:8000/encounters/',
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json=encounter_data
)

print(f"Status: {r.status_code}")
encounter_result = r.json()
print(json.dumps(encounter_result, indent=2, ensure_ascii=False))

if r.status_code != 200:
    print(f"\nERROR: Failed to create encounter")
    exit(1)

encounter_id = encounter_result.get('id')
print(f"\nEncounter ID: {encounter_id}")

# Step 4: MCARE Auto
print("\n=== STEP 4: MCARE Auto Analysis ===")
mcare_data = {
    "text": "سردرد شدید، اضطراب، بی‌خوابی"
}

r = requests.post(
    'http://localhost:8000/mcare/auto',
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json=mcare_data
)

print(f"Status: {r.status_code}")
mcare_result = r.json()
print("\n=== MCARE RESULT ===")
print(json.dumps(mcare_result, indent=2, ensure_ascii=False))

print("\n=== END-TO-END TEST COMPLETE ===")
