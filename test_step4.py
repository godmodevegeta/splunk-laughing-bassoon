# test_step4.py
from auth.splunk_client import SplunkRestClient
from auth.mcp_validator import SplunkMCPValidator

if __name__ == "__main__":

    client = SplunkRestClient("localhost", 8089, "admin", "YourNewSecurePassword123!")
    
    # PASTE YOUR TOKEN HERE
    mcp_token = "OD+7w8OusvGtjARQQwuSswnPoLl95AbusGA2IIqCBdne4+hYx2dQU4iEGYzFu+C9BEvd9VAHiMd5tMUi9W8bJ3GxsEeUM2Tw7Mcflj4hCAGbTqh32QIf8X1vm6g3TyEv5D/7gFBlQSZ5jehMHu4sxjpG76IATRhwJorswnZnJEd5E3rLEELyPhgysF3rJ4UkXqvyB6zuHjpwrh5voLO3EHQoxXbOJUfAnxihmM2uirGwKfCZ62lZi2ygMxwbogfzwPQzdgaLW8ZA0LjBgAVFPi7oTlMYyOwePWMgPByGOA/pgggKz5weNLN467Qv715L4u/zlzWIg2Qs753C8q8VAA==.KbLtx5KsrCcow4aSzS3Y8RklQqot2Bs6F+t+JAmYN07v6TL2SOn2v8LukdbdRdFO0hIzXda5jhBNcZexHPRp8PPwzOmuJO7TsOiVTaD374c/bQR/JjuqRc+SuCGqGT+dnSeQBL/kadnIsSoEfync+jCsEKNIUIEILBIDHYhrMVA1+Ubs/hRll3A5I7N+WC9tcok4suQIOHd3cJHextTKHLGQdbHrmf39Yhq3O23OChqN+9Xw5WOFeWWcCiL3Jr73FuH7Ls4SF8JudjkScKu4j46MELG19xOTkzjta8dKdGACHTouqhy4qY3igc3AYl+ruXtgSgl9Ded66IpqqRnSGw==" 
    
    validator = SplunkMCPValidator("localhost", 8089, mcp_token)
    
    stanza_name = "schemaops_test_sourcetype"
    iteration_source = "schemaops_test/iteration_6.log" # Iteration 4!
    
    raw_log_data = """2026-05-30 11:50:00 [INFO] User login successful client_address=192.168.1.5 status=success"""
    
    print(f"1. Ingesting test logs with source={iteration_source}...")
    client.ingest_logs(raw_log_data, stanza_name, iteration_source, index="main")
    
    expected_fields = ["client_address", "status"]
    
    print("\n2. Validating via Real Splunk MCP Server...")
    success, message = validator.validate_extraction(
        index="main", 
        source=iteration_source, 
        expected_fields=expected_fields
    )
    
    if success:
        print(f"  ✅ {message}")
        print("\n🎉 PHASE 1 COMPLETE: Real MCP Loop is closed!")
    else:
        print(f"  ❌ Validation Failed: {message}")