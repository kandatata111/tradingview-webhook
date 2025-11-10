import requests
import json

try:
    r = requests.get('http://localhost:5000/current_states')
    data = r.json()
    
    print('Keys in response:', data.keys())
    
    if 'states' in data and len(data['states']) > 0:
        state = data['states'][0]
        print('\nKeys in first state:', state.keys())
        print('\nFirst state clouds:')
        for label, cloud in state['clouds'].items():
            print(f'\n{label} cloud:')
            print(f'  Keys: {cloud.keys()}')
            if 'topPrice' in cloud:
                print(f'  topPrice: {cloud["topPrice"]}')
            if 'bottomPrice' in cloud:
                print(f'  bottomPrice: {cloud["bottomPrice"]}')
        
        print('\n\nFull response (first state):')
        print(json.dumps(state, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
