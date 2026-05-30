# test_step1.py
from auth.splunk_client import SplunkRestClient

if __name__ == "__main__":
    # Replace with your Docker Splunk credentials
    client = SplunkRestClient(
        host="localhost", 
        port=8089, 
        username="admin", 
        password="YourNewSecurePassword123!"
    )
    
    # Step 1 -> verify: 200 OK
    client.ping()