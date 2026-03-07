import requests

# Set this to the port your backend is actually running on
BASE_URL = "http://localhost:8001"

def test_connection():
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    test_connection()