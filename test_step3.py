# test_step3.py
from auth.splunk_client import SplunkRestClient

if __name__ == "__main__":
    client = SplunkRestClient(
        host="localhost", 
        port=8089, 
        username="admin", 
        password="YourNewSecurePassword123!" # Use your actual password
    )
    
    stanza_name = "schemaops_test_sourcetype"
    iteration_source = "schemaops_test/iteration_1.log"
    
    # A sample multiline log to test our parsing rules later
    raw_log_data = """2026-05-30 11:50:00 [INFO] User login successful client_address=192.168.1.5 status=success
2026-05-30 11:51:00 [ERROR] Connection timeout client_address=10.0.0.2 status=failed"""

    print(f"1. Ingesting test logs with source={iteration_source}...")
    
    result = client.ingest_logs(
        raw_text=raw_log_data,
        sourcetype=stanza_name,
        source=iteration_source,
        index="main"
    )
    
    print(f"  ✅ Ingestion successful: {result}")
    print("\n🎉 Step 3 Complete: Data Ingestion verified!")
    print("Note: In Splunk, it might take ~2-3 seconds for this data to be searchable.")