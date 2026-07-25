import requests, json
client_id = '1000.D5IIHDXSPN2MII26AD0V61I6RMVSNM'
client_secret = '02ee875ecfc50573e5cc8d62916ad3077be20d0f42'
refresh_token = '1000.b33eae44d0bddb9fdc914bdfc96871b9.6f4a777c0e20ee1756cbe7cbee3cefe0'
res = requests.post('https://accounts.zoho.in/oauth/v2/token', data={
    'grant_type': 'refresh_token',
    'client_id': client_id,
    'client_secret': client_secret,
    'refresh_token': refresh_token
})
token = res.json().get('access_token')
url = 'https://sentinel-migration-bucket-development.zohostratus.in/fir_cases.csv'
file_res = requests.get(url, headers={'Authorization': f'Zoho-oauthtoken {token}'})
with open('fir_cases.csv', 'wb') as f:
    f.write(file_res.content)
