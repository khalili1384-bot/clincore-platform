#!/usr/bin/env python3
"""
STEP 2 - Smoke Test Rate Limiting (Cleanup)
Cleanup usage_events then call /mcare/auto (expect 200)
"""
import os
import sys
sys.path.insert(0, r'D:\clincore-platform\src')

import psycopg
import urllib.request
import json

# Read DB credentials from environment or .env
DB_PASSWORD = os.getenv('DB_PASSWORD', '805283631')
DB_USER = os.getenv('DB_USER', 'clincore_user')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'clincore')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
TENANT_ID = "5c091694-0e5a-46a0-b1d5-01fb7655f0ab"
API_KEY = "AjT03TWidJwlMeUnaeH4GfP3WNQpEUvWVlN434kv0_w"
BASE_URL = "http://127.0.0.1:8000"

print("=" * 60)
print("STEP 2: Smoke Test Rate Limiting - Cleanup (Expect 200)")
print("=" * 60)

# Step 1: Cleanup all usage_events for this tenant
print("\n[1] Cleaning up usage_events for tenant...")
try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM usage_events WHERE tenant_id = %s AND endpoint_path = '/mcare/auto'",
                (TENANT_ID,)
            )
            deleted = cur.rowcount
            conn.commit()
    print(f"    ✅ Deleted {deleted} usage_events for tenant={TENANT_ID}")
except Exception as e:
    print(f"    ❌ Error: {e}")
    sys.exit(1)

# Step 2: Call /mcare/auto (expect 200)
print("\n[2] Calling /mcare/auto after cleanup...")
print(f"    Tenant: {TENANT_ID}")
print(f"    API Key: {API_KEY[:20]}...")

try:
    req = urllib.request.Request(
        f"{BASE_URL}/mcare/auto",
        data=json.dumps({
            "chief_complaint": "headache",
            "patient_age_y": 30,
            "patient_gender": "M",
            "duration_hours": 24
        }).encode(),
        headers={
            'Content-Type': 'application/json',
            'X-Tenant-Id': TENANT_ID,
            'Authorization': f'Bearer {API_KEY}'
        }
    )
    
    try:
        response = urllib.request.urlopen(req)
        status = response.status
        body = json.loads(response.read().decode())
        print(f"    ✅ Got HTTP {status}")
        
        if status == 200:
            print(f"\n    Response preview:")
            print(f"    - mcare_rank: {body.get('mcare_rank', 'N/A')}")
            print(f"    - diagnoses: {len(body.get('diagnoses', []))} items")
            print(f"    - treatments: {len(body.get('treatments', []))} items")
            print("\n" + "=" * 60)
            print("✅ TEST PASSED: Request succeeded after cleanup!")
            print("   Rate limiting allows requests when under limit.")
            print("=" * 60)
        else:
            print(f"\n❌ TEST FAILED: Expected 200, got {status}")
            sys.exit(1)
            
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode()
        print(f"    ❌ Got HTTP {status} (expected 200)")
        print(f"    Response: {body}")
        print(f"\n❌ TEST FAILED: Expected 200, got {status}")
        sys.exit(1)
            
except Exception as e:
    print(f"    ❌ Error: {e}")
    sys.exit(1)
