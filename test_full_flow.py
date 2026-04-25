import requests
import uuid
import json

print("=== FULL E2E TEST: Create Tenant → API Key → Patient → Encounter → MCARE ===\n")

SUPER_ADMIN_KEY = "Bkfjb1-Yr3NGqYMMGHBiZkuDobvy1H68hBP7XFkFVNQ"
BASE_URL = "http://127.0.0.1:8000"

# Step 1: Create Tenant (via database - we need a tenant first)
tenant_id = str(uuid.uuid4())
print(f"Step 1: Generated Tenant ID: {tenant_id}")

# We need to insert tenant into database first
import psycopg
conn = psycopg.connect("postgresql://clincore_user:805283631@127.0.0.1:5432/clincore")
cur = conn.cursor()
cur.execute("INSERT INTO tenants (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING", (tenant_id, f"Test Tenant {tenant_id[:8]}"))
conn.commit()
conn.close()
print(f"✓ Tenant created in database\n")

# Step 2: Create API Key
print(f"Step 2: Creating API Key for tenant {tenant_id}")
r = requests.post(
    f"{BASE_URL}/super-admin/api-keys/new",
    headers={'X-Super-Admin-Key': SUPER_ADMIN_KEY},
    json={'tenant_id': tenant_id, 'role': 'doctor'}
)
print(f"Status: {r.status_code}")
result = r.json()
print(json.dumps(result, indent=2))

if r.status_code != 200:
    print("\n✗ Failed to create API key")
    exit(1)

api_key = result['api_key']
print(f"\n✓ API Key created: {api_key[:20]}...\n")

# Step 3: Create Patient
print("Step 3: Creating Patient")
r = requests.post(
    f"{BASE_URL}/patients",
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json={
        'full_name': 'علی احمدی',
        'date_of_birth': '1990-01-15',
        'gender': 'male'
    }
)
print(f"Status: {r.status_code}")
patient_result = r.json()
print(json.dumps(patient_result, indent=2, ensure_ascii=False))

if r.status_code != 200:
    print("\n✗ Failed to create patient")
    exit(1)

patient_id = patient_result['id']
print(f"\n✓ Patient created: {patient_id}\n")

# Step 4: Create Encounter
print("Step 4: Creating Encounter")
r = requests.post(
    f"{BASE_URL}/encounters/",
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json={
        'patient_id': patient_id,
        'encounter_type': 'outpatient',
        'chief_complaint': 'سردرد شدید، اضطراب، بی‌خوابی'
    }
)
print(f"Status: {r.status_code}")
encounter_result = r.json()
print(json.dumps(encounter_result, indent=2, ensure_ascii=False))

if r.status_code != 200:
    print("\n✗ Failed to create encounter")
    exit(1)

encounter_id = encounter_result['id']
print(f"\n✓ Encounter created: {encounter_id}\n")

# Step 5: MCARE Auto Analysis
print("Step 5: Running MCARE Auto Analysis")
r = requests.post(
    f"{BASE_URL}/mcare/auto",
    headers={'X-API-Key': api_key, 'X-Tenant-Id': tenant_id},
    json={'text': 'سردرد شدید، اضطراب، بی‌خوابی'}
)
print(f"Status: {r.status_code}")
mcare_result = r.json()
print("\n=== MCARE ANALYSIS RESULT ===")
print(json.dumps(mcare_result, indent=2, ensure_ascii=False))

print("\n\n=== ✓ FULL E2E TEST COMPLETED SUCCESSFULLY ===")
print(f"Tenant ID: {tenant_id}")
print(f"API Key: {api_key}")
print(f"Patient ID: {patient_id}")
print(f"Encounter ID: {encounter_id}")
