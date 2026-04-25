import requests
import json

r = requests.get('http://localhost:8000/openapi.json')
spec = r.json()

create_route = spec['paths'].get('/super-admin/api-keys/create')
print('Route exists:', create_route is not None)

if create_route:
    print('\nRoute spec:')
    print(json.dumps(create_route, indent=2))
else:
    print('\nRoute NOT found!')
    print('\nAll super-admin api-keys routes:')
    for path in sorted(spec['paths'].keys()):
        if 'super-admin' in path and 'api-keys' in path:
            print(f"  {path}: {list(spec['paths'][path].keys())}")
