import requests
import json

BASE_URL = 'http://127.0.0.1:8000'
TENANT_ID = '5c091694-0e5a-46a0-b1d5-01fb7655f0ab'
API_KEY = 'AjT03TWidJwlMeUnaeH4GfP3WNQpEUvWVlN434kv0_w'

headers = {
    'X-Tenant-Id': TENANT_ID,
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

print('=' * 60)
print('ClinCore API Test Suite - Full Integration Test')
print('=' * 60)

# Test 1: Health check
print('\n1. GET /health')
r = requests.get(f'{BASE_URL}/health')
if r.status_code == 200:
    print(f'✅ PASS - Status: {r.status_code}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

# Test 2: List patients (before)
print('\n2. GET /patients (before)')
r = requests.get(f'{BASE_URL}/patients', headers=headers)
if r.status_code == 200:
    data = r.json()
    count = data.get('total', len(data.get('patients', [])))
    print(f'✅ PASS - Status: {r.status_code}, Count: {count}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

# Test 3: Create patient
print('\n3. POST /patients')
patient_id = None
payload = {'full_name': 'تست بیمار'}
r = requests.post(f'{BASE_URL}/patients', headers=headers, json=payload)
if r.status_code == 200:
    data = r.json()
    patient_id = data.get('id')
    print(f'✅ PASS - Status: {r.status_code}')
    print(f'   Patient ID: {patient_id}')
    print(f'   Full Name: {data.get("full_name")}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

# Test 4: List patients (after)
print('\n4. GET /patients (after)')
r = requests.get(f'{BASE_URL}/patients', headers=headers)
if r.status_code == 200:
    data = r.json()
    count = data.get('total', len(data.get('patients', [])))
    found = any(p.get('id') == patient_id for p in data.get('patients', []))
    print(f'✅ PASS - Status: {r.status_code}, Count: {count}')
    print(f'   New patient found: {found}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

# Test 5: MCARE auto
print('\n5. POST /mcare/auto')
if patient_id:
    payload = {
        'patient_id': patient_id,
        'text': 'سردرد شدید، ترس از تاریکی، بی‌خوابی شبانه، بهتر در هوای تازه'
    }
    r = requests.post(f'{BASE_URL}/mcare/auto', headers=headers, json=payload)
    if r.status_code == 200:
        data = r.json()
        remedies = data.get('remedies', [])
        if remedies:
            top_remedy = remedies[0].get('name', 'N/A')
            score = remedies[0].get('score', 'N/A')
            print(f'✅ PASS - Status: {r.status_code}')
            print(f'   Top remedy: {top_remedy} (score: {score})')
        else:
            print(f'✅ PASS - Status: {r.status_code}, No remedies returned')
    else:
        print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')
else:
    print('⏭️  SKIP - No patient_id')

# Test 6: List clinical cases
print('\n6. GET /clinical-cases/')
r = requests.get(f'{BASE_URL}/clinical-cases/', headers=headers)
if r.status_code == 200:
    data = r.json()
    count = len(data.get('cases', []))
    print(f'✅ PASS - Status: {r.status_code}, Count: {count}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

# Test 7: Create appointment
print('\n7. POST /appointments/')
if patient_id:
    payload = {
        'patient_id': patient_id,
        'scheduled_for': '2026-04-20T10:00:00',
        'status': 'scheduled',
        'notes': 'تست نوبت'
    }
    r = requests.post(f'{BASE_URL}/appointments/', headers=headers, json=payload)
    if r.status_code == 200:
        data = r.json()
        appt_id = data.get('id')
        print(f'✅ PASS - Status: {r.status_code}')
        print(f'   Appointment ID: {appt_id}')
        print(f'   Scheduled for: {data.get("scheduled_for")}')
    else:
        print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')
else:
    print('⏭️  SKIP - No patient_id')

# Test 8: List appointments
print('\n8. GET /appointments/')
r = requests.get(f'{BASE_URL}/appointments/', headers=headers)
if r.status_code == 200:
    data = r.json()
    count = data.get('total', len(data.get('appointments', [])))
    print(f'✅ PASS - Status: {r.status_code}, Count: {count}')
else:
    print(f'❌ FAIL - Status: {r.status_code}, Response: {r.text}')

print('\n' + '=' * 60)
print('Test Suite Complete')
print('=' * 60)
