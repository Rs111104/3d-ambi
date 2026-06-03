import urllib.request, json

url = 'http://127.0.0.1:8080/api/session/start'
payload = {'name': 'CLI Test', 'setId': '', 'inviteToken': ''}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=10) as res:
        print('status', res.status)
        print(res.read().decode())
except Exception as e:
    print('error', e)
