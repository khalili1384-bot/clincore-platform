#!/usr/bin/env python3
"""
STEP 1 - Smoke Test Rate Limiting
Insert 100 usage_events then call /mcare/auto (expect 429)
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
print("STEP 1: Smoke Test Rate Limiting (Expect 429)")
print("=" * 60)

# Step 1: Insert 100 usage_events
print("\n[1] Inserting 100 usage_events into database...")
try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # First, clean up existing events for this tenant/endpoint
            cur.execute(
                "DELETE FROM usage_events WHERE tenant_id = %s AND endpoint_path = '/mcare/auto'",
                (TENANT_ID,)
            )
            
            # Insert 100 events
            for i in range(100):
                cur.execute(
                    """
                    INSERT INTO usage_events (tenant_id, endpoint_path, created_at)
                    VALUES (%s, '/mcare/auto', now() AT TIME ZONE 'UTC')
                    """,
                    (TENANT_ID,)
                )
            conn.commit()
    print(f"    ✅ Inserted 100 usage_events for tenant={TENANT_ID}")
except Exception as e:
    print(f"    ❌ Error: {e}")
    sys.exit(1)

# Step 2: Call /mcare/auto (expect 429)
print("\n[2] Calling /mcare/auto with existing API key...")
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
        body = response.read().decode()
        print(f"    ⚠️  Unexpected success: HTTP {status}")
        print(f"    Response: {body[:200]}")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode()
        print(f"    ✅ Got HTTP {status} (expected 429)")
        print(f"    Response: {body}")
        
        if status == 429:
            print("\n" + "=" * 60)
            print("✅ TEST PASSED: Rate limiting is working correctly!")
            print("   Received 429 Too Many Requests as expected.")
            print("=" * 60)
        else:
            print(f"\n❌ TEST FAILED: Expected 429, got {status}")
            sys.exit(1)
            
except Exception as e:
    print(f"    ❌ Error: {e}")
    sys.exit(1)
