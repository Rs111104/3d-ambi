#!/usr/bin/env python3
import json
import urllib.request

BASE = 'http://127.0.0.1:8080'

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode('utf-8'))


def main():
    print('Starting session...')
    start = post('/api/session/start', {'name': 'Automated Test'})
    token = start.get('sessionToken')
    print('sessionToken:', token)
    print('Requesting next question...')
    nxt = post('/api/session/next', {'sessionToken': token})
    print(json.dumps(nxt, indent=2))

if __name__ == '__main__':
    main()
