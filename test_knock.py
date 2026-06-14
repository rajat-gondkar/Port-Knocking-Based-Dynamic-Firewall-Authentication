import requests

res1 = requests.get('http://localhost:8082/api/status')
seq = res1.json()['sequence']
print(f"Got sequence: {seq}")

res2 = requests.post('http://localhost:8082/api/knock', json={"host": "127.0.0.1", "sequence": seq})
print(f"Response: {res2.json()}")
