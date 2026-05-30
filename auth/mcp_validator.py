# auth/mcp_validator.py
import json
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SplunkMCPValidator:
    """
    Connects to the Splunk MCP Server App using direct JSON-RPC over HTTP POST.
    """
    def __init__(self, host, port, mcp_token):
        self.mcp_url = f"https://{host}:{port}/services/mcp"
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Authorization": f"Bearer {mcp_token}",
            "Content-Type": "application/json"
        })
        self.request_id = 1

    def _send_rpc(self, method, params=None):
        """Sends a JSON-RPC command to Splunk."""
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        
        response = self.session.post(self.mcp_url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            raise Exception(f"MCP Server Error: {data['error']}")
            
        return data.get("result")

    def execute_splunk_run_query(self, spl_query):
        """Executes a Splunk search via the MCP tools/call method."""
        if not spl_query.strip().startswith("search") and not spl_query.strip().startswith("|"):
            spl_query = f"search {spl_query}"

        # 1. The MCP Protocol requires an initialize handshake first
        self._send_rpc("initialize", {
            "protocolVersion": "2024-11-05", 
            "capabilities": {}, 
            "clientInfo": {"name": "schemaops", "version": "1.0.0"}
        })
        # Note: We technically should send 'initialized' notification here per spec, 
        # but stateless HTTP implementations usually ignore it.

        # 2. Call the tool
        result = self._send_rpc("tools/call", {
            "name": "splunk_run_query",
            "arguments": {"query": spl_query}
        })
        
        # 3. Parse the MCP tool output format
        raw_text = result["content"][0]["text"]
        parsed_json = json.loads(raw_text)
        
        # Extract the actual rows from the 'results' key!
        return parsed_json.get("results", [])

    def validate_extraction(self, index, source, expected_fields, max_retries=8, sleep_seconds=3):
        """Polls via MCP until the data is indexed and verified."""
        
        # FIX: Added earliest=0 latest=+1d to catch timezone-skewed logs!
        spl = f"index={index} source={source} earliest=0 latest=+1d | fieldsummary"
        
        print(f"⏳ Waiting for data to index (Polling up to {max_retries * sleep_seconds}s via JSON-RPC MCP)...")
        
        for attempt in range(1, max_retries + 1):
            time.sleep(sleep_seconds)
            
            try:
                results = self.execute_splunk_run_query(spl)
            except Exception as e:
                print(f"  [Attempt {attempt}/{max_retries}] MCP call failed: {e}")
                continue
                
            if not results:
                print(f"  [Attempt {attempt}/{max_retries}] No data found yet. Retrying...")
                continue
            
            extracted_fields = [r.get("field") for r in results if isinstance(r, dict)]
            
            # If we got results but not our custom fields, Splunk might just be showing default fields 
            # like _time, host, source, sourcetype.
            missing_fields = [f for f in expected_fields if f not in extracted_fields]
            
            if not missing_fields:
                return True, "All fields extracted successfully."
            elif attempt == max_retries:
                # Debug print on the very last attempt so we can see what Splunk ACTUALLY extracted
                return False, f"Missing fields: {missing_fields}. \n  Actually Found: {extracted_fields}"
                
        return False, f"Timeout. Data never appeared for source={source}."