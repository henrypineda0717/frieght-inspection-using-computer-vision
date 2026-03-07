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
    

curl -X POST -F "video=@/home/haile/ai/projects/upwork/Code-20260216T171605Z-1-001/Code/backend/analyzed.mp4" "http://localhost:8001/video-session/start?detection_interval=3&use_fp16=true&initial_view_type=exterior&inspection_stage=pre"