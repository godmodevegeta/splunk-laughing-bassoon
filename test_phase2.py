# test_phase2.py
from rag.cim_oracle import CIMOracle

if __name__ == "__main__":
    oracle = CIMOracle()
    
    # Let's test messy, non-standard fields that our LLM might extract from a raw log
    test_fields = [
        {"name": "client_address", "context": "IP address of the user logging in"},
        {"name": "login_status", "context": "whether the login succeeded or failed"},
        {"name": "target_port", "context": "the port on the server receiving traffic"}
    ]
    
    print("\n🔮 Testing CIM Oracle Mapping...")
    for field in test_fields:
        match = oracle.get_cim_mapping(field["name"], field["context"])
        print(f"  Extracted Field: '{field['name']}'")
        print(f"  ↳ Mapped to CIM: '{match['cim_field']}' (Model: {match['data_model']})\n")
        
    print("🎉 PHASE 2 COMPLETE: RAG Pipeline is operational!")