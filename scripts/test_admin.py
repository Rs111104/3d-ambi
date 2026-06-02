#!/usr/bin/env python3
import json
import urllib.request

BASE = 'http://127.0.0.1:8080'

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode('utf-8'))


def get(path, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode('utf-8'))


def main():
    print('Logging in as admin...')
    try:
        data = post('/api/admin/login', {'username': 'admin', 'password': 'admin123!'})
    except Exception as e:
        print('Login failed:', e)
        return
    token = data.get('token')
    print('Token:', token)
    if not token:
        print('No token returned')
        return
    print('Fetching questions...')
    try:
        qs = get('/api/admin/questions', token)
        print('Questions count:', len(qs))
    except Exception as e:
        print('Failed to fetch questions:', e)

if __name__ == '__main__':
    main()
