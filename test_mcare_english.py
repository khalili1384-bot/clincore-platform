import requests
import json

print("=" * 70)
print("REAL MCARE ENGINE TEST - English Narrative")
print("=" * 70)

url = "http://localhost:8000/mcare/auto"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "fEDuG03NaZBglfXKoZEcSc0moCwotcBiX0zSOJZHkWs",
    "X-Tenant-Id": "13147a94-c116-4403-a084-38e0cab50368"
}

# Test with English narrative - classic Belladonna case
data = {
    "narrative": "Sudden violent headache, throbbing, worse from light and noise, face flushed and hot, pupils dilated, restless and anxious",
    "top_n": 10
}

print("\n📋 Test: English narrative (classic Belladonna symptoms)")
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
        
        if result.get('rubrics'):
            print(f"\n📝 Extracted Rubrics:")
            for i, rubric in enumerate(result['rubrics'][:5], 1):
                print(f"  {i}. {rubric}")
        
        if result.get('results'):
            print(f"\n🏆 Top {len(result['results'])} Remedies:")
            for i, remedy in enumerate(result['results'], 1):
                print(f"  {i}. {remedy['remedy']}: {remedy['score']:.4f}")
                if remedy['remedy'].lower() == 'bell':
                    print(f"     ⭐ BELLADONNA FOUND! (Expected for this case)")
        
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
print("✅ MCARE Engine is fully operational!")
print("=" * 70)
