import requests
import json

r = requests.get('http://localhost:8000/openapi.json')
spec = r.json()

api_keys_path = spec['paths'].get('/super-admin/api-keys', {})
print("Available methods for /super-admin/api-keys:")
print(list(api_keys_path.keys()))

print("\nFull spec:")
print(json.dumps(api_keys_path, indent=2))

# Check if POST exists
if 'post' in api_keys_path:
    print("\n✓ POST method is registered!")
    print(json.dumps(api_keys_path['post'], indent=2))
else:
    print("\n✗ POST method is NOT registered!")
    print("\nThis means the server hasn't loaded the updated code.")
    print("The file super_admin.py has POST before GET, but server shows only GET.")
