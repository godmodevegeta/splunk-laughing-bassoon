# test_step2.py
from auth.splunk_client import SplunkRestClient

if __name__ == "__main__":
    client = SplunkRestClient(
        host="localhost", 
        port=8089, 
        username="admin", 
        password="YourNewSecurePassword123!" # Native Splunk Enterprise admin password
    )
    
    stanza_name = "schemaops_test_sourcetype"
    test_properties = {
        "SHOULD_LINEMERGE": "false",
        "LINE_BREAKER": r"([\r\n]+)",  # <-- Added 'r' for raw string!
        "TIME_FORMAT": "%Y-%m-%d %H:%M:%S"
    }
    
    print("1. Pushing new props.conf configuration...")
    client.set_props_config(stanza_name, test_properties)
    
    print("2. Forcing Splunk extraction reload...")
    client.reload_parsing_configs()
    
    print("3. Verifying configuration saved to Splunk...")
    saved_config = client.get_props_config(stanza_name)
    
    # Verify the keys match
    for key, expected_val in test_properties.items():
        actual_val = str(saved_config.get(key)).lower()
        expected_str = str(expected_val).lower()
        
        # Splunk normalizes "false" to "0" and "true" to "1"
        if expected_str == "false" and actual_val == "0":
            actual_val = "false"
        elif expected_str == "true" and actual_val == "1":
            actual_val = "true"
            
        assert actual_val == expected_str, f"Mismatch on {key}: Expected {expected_str}, got {saved_config.get(key)}"
        print(f"  ✅ {key} == {saved_config.get(key)}")
        
    print("\n🎉 Step 2 Complete: Config Push & Reload verified!")