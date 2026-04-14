import requests
import json

print("=" * 70)
print("REAL MCARE ENGINE TEST - Dr Khalili Clinic")
print("=" * 70)

url = "http://localhost:8000/mcare/auto"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "fEDuG03NaZBglfXKoZEcSc0moCwotcBiX0zSOJZHkWs",
    "X-Tenant-Id": "13147a94-c116-4403-a084-38e0cab50368"
}

# Test with Persian narrative
data = {
    "narrative": "سردرد شدید سه روزه، بدتر با نور و صدا، احساس تپش قلب",
    "top_n": 5
}

print("\n📋 Test: Persian narrative (headache + light sensitivity + palpitation)")
print(f"Narrative: {data['narrative']}")
print("\nSending request...")

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"OK: {result.get('ok')}")
        print(f"Rubrics extracted: {len(result.get('rubrics', []))}")
        print(f"Symptom IDs matched: {len(result.get('symptom_ids', []))}")
        
        if result.get('results'):
            print(f"\n🏆 Top {len(result['results'])} Remedies:")
            for i, remedy in enumerate(result['results'], 1):
                print(f"  {i}. {remedy['remedy']}: {remedy['score']:.4f}")
        
        if result.get('debug'):
            debug = result['debug']
            print(f"\n🔍 Debug Info:")
            print(f"  - Matched rubrics: {debug.get('matched_count')}")
            print(f"  - Mind rubrics: {debug.get('mind_count')}")
            print(f"  - Clusters active: {debug.get('clusters_active')}")
            
        if result.get('error'):
            print(f"\n⚠️ Error: {result['error']}")
    else:
        print(f"\n❌ FAILED: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"\n❌ Exception: {e}")

print("\n" + "=" * 70)
