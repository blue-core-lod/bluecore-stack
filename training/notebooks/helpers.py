import httpx

def get_token(url="http://localhost:8000", username="developer", password="123456"):
    keycloak_token = httpx.post(f"{url}/keycloak/realms/bluecore/protocol/openid-connect/token",
                      data={
                          "client_id": "bluecore_api",
                          "username": username,
                          "password": password,
                          "grant_type": "password",
                      })
    
    keycloak_token.raise_for_status()
    return keycloak_token.json().get('access_token')
