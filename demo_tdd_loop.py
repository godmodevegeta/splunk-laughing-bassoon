# demo_tdd_loop.py
import time
import os
from auth.splunk_client import SplunkRestClient
from auth.mcp_validator import SplunkMCPValidator
from agent.schemaops_agent import SchemaOpsAgent
from rag.cim_oracle import CIMOracle

if __name__ == "__main__":
    print("🚀 INITIALIZING SCHEMAOPS TDD LOOP...\n" + "="*50)
    
    # 1. Setup Clients
    client = SplunkRestClient("localhost", 8089, "admin", "YourNewSecurePassword123!")
    mcp_token = "OD+7w8OusvGtjARQQwuSswnPoLl95AbusGA2IIqCBdne4+hYx2dQU4iEGYzFu+C9BEvd9VAHiMd5tMUi9W8bJ3GxsEeUM2Tw7Mcflj4hCAGbTqh32QIf8X1vm6g3TyEv5D/7gFBlQSZ5jehMHu4sxjpG76IATRhwJorswnZnJEd5E3rLEELyPhgysF3rJ4UkXqvyB6zuHjpwrh5voLO3EHQoxXbOJUfAnxihmM2uirGwKfCZ62lZi2ygMxwbogfzwPQzdgaLW8ZA0LjBgAVFPi7oTlMYyOwePWMgPByGOA/pgggKz5weNLN467Qv715L4u/zlzWIg2Qs753C8q8VAA==.KbLtx5KsrCcow4aSzS3Y8RklQqot2Bs6F+t+JAmYN07v6TL2SOn2v8LukdbdRdFO0hIzXda5jhBNcZexHPRp8PPwzOmuJO7TsOiVTaD374c/bQR/JjuqRc+SuCGqGT+dnSeQBL/kadnIsSoEfync+jCsEKNIUIEILBIDHYhrMVA1+Ubs/hRll3A5I7N+WC9tcok4suQIOHd3cJHextTKHLGQdbHrmf39Yhq3O23OChqN+9Xw5WOFeWWcCiL3Jr73FuH7Ls4SF8JudjkScKu4j46MELG19xOTkzjta8dKdGACHTouqhy4qY3igc3AYl+ruXtgSgl9Ded66IpqqRnSGw=="
    
    validator = SplunkMCPValidator("localhost", 8089, mcp_token)
    agent = SchemaOpsAgent()
    oracle = CIMOracle()
    
    stanza_name = "schemaops_demo_app"
    raw_log = "2026-05-30 11:50:00 user=jdoe action=login client_address:192.168.1.50"
    
    # We expect 'client_address', which Splunk won't parse natively because of the colon!
    expected_fields = ["user", "action", "client_address"] 
    
    print(f"📄 TARGET LOG: {raw_log}")
    print(f"🎯 EXPECTED FIELDS: {expected_fields}")
    
    # 2. The Agentic Loop
    max_attempts = 3
    feedback = None
    final_props = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n" + "-"*40)
        print(f"🔄 ITERATION {attempt}")
        print("-"*40)
                
        # Point 3 Fix: Mutate the stanza name per attempt to prevent Splunk from merging keys
        current_stanza = f"{stanza_name}_run_{attempt}"
        
        # A. Agent Generates Config via AI
        props_config = agent.generate_config(raw_log, attempt, feedback)
        print(f"🤖 [Agent] Proposed Config: {props_config}")
        
        # B. Push Config & Reload (using current_stanza)
        print(f"⚙️  [System] Pushing props.conf [{current_stanza}] to Splunk...")
        client.set_props_config(current_stanza, props_config)
        client.reload_parsing_configs()
        
        # C. Ingest Log (using current_stanza)
        iteration_source = f"schemaops_demo/run_{int(time.time())}.log"
        print(f"📥 [System] Ingesting test log as source={iteration_source}...")
        client.ingest_logs(raw_log, current_stanza, iteration_source, index="main")
        
        # D. Validate via MCP
        print("🔬 [System] Validating extraction via Splunk MCP Server...")
        success, message = validator.validate_extraction(
            index="main", 
            source=iteration_source, 
            expected_fields=expected_fields,
            max_retries=6,
            sleep_seconds=3
        )
        
        if success:
            print(f"\n🎉 [Validation SUCCESS] {message}")
            final_props = props_config
            break
        else:
            print(f"\n❌ [Validation FAILED] {message}")
            feedback = message 
            
    # 3. Phase 2 Integration: CIM Alignment
    if final_props:
        print("\n" + "="*50)
        print("🔮 INITIATING RAG CIM ALIGNMENT...")
        print("="*50)
        for field in expected_fields:
            match = oracle.get_cim_mapping(field)
            if match and match['cim_field'] != field:
                alias_key = f"FIELDALIAS-{field}_to_cim"
                alias_val = f"{field} AS {match['cim_field']}"
                final_props[alias_key] = alias_val
                print(f"  ✅ Mapped '{field}' -> '{match['cim_field']}' (Model: {match['data_model']})")
                
        print(f"\n✅ FINAL, CIM-COMPLIANT CONFIGURATION READY FOR PACKAGING:")
        for k, v in final_props.items():
            print(f"   {k} = {v}")