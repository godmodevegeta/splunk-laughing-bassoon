# agent/schemaops_agent.py
import os
import json
from openai import OpenAI

class SchemaOpsAgent:
    def __init__(self):
        # Strictly using the Splunk Hosted Models proxy configuration
        self.providers = {
            "primary": {
                "name": "Primary (Splunk Hosted Mock / OpenRouter)",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_KEY"),
                "model": "openai/gpt-oss-120b:free"
            },
            "fallback": {
                "name": "Fallback (NVIDIA)",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY", "YOUR_NVIDIA_KEY"),
                "model": "openai/gpt-oss-120b"
            },
            "emergency": {
                "name": "Emergency (NVIDIA Fast)",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY", "YOUR_NVIDIA_KEY"),
                "model": "openai/gpt-oss-20b"  # Faster, still capable
            }
        }
        
    def generate_config(self, raw_log, attempt=1, previous_feedback=None):
        """
        Calls the LLM to generate props.conf properties based on the raw log.
        """
        system_prompt = """You are 'SchemaOps', an expert Splunk Data Engineer.
Your job is to analyze raw log data and generate the exact props.conf key-value pairs required to parse it into Splunk.

CRITICAL RULES:
1. ONLY return a valid JSON object. No markdown, no explanations, no code blocks.
2. ALWAYS include SHOULD_LINEMERGE (usually false unless it's a stack trace).
3. ALWAYS include TIME_FORMAT (using standard strptime format).
4. If a field uses a non-standard delimiter (like 'IP:' or 'client_address:'), you MUST write a custom regex using the EXTRACT-<fieldname> syntax.
Example: {"SHOULD_LINEMERGE": "false", "TIME_FORMAT": "%Y-%m-%d %H:%M:%S", "EXTRACT-src_ip": "IP:(?<src_ip>\\d+\\.\\d+\\.\\d+\\.\\d+)"}
"""

        user_prompt = f"Target Log to Parse:\n{raw_log}\n\n"
        
        if attempt > 1 and previous_feedback:
            user_prompt += f"WARNING! Your previous attempt failed in the Splunk MCP Validation Sandbox.\n"
            user_prompt += f"Splunk MCP Feedback: {previous_feedback}\n"
            user_prompt += "Rewrite your regex and config to fix the missing fields. Do not use the exact same regex as before."
        else:
            user_prompt += "Generate the Splunk props.conf JSON for this log."

        # The Failover Loop (Iterating through primary -> fallback -> emergency)
        for level, endpoint in self.providers.items():
            try:
                print(f"🤖 [Agent] Routing prompt to {endpoint['name']} using {endpoint['model']}...")
                client = OpenAI(
                    base_url=endpoint["base_url"],
                    api_key=endpoint["api_key"]
                )
                
                response = client.chat.completions.create(
                    model=endpoint["model"],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1, # Low temp for code generation
                    response_format={"type": "json_object"} # Forces JSON output
                )
                
                raw_json = response.choices[0].message.content
                return json.loads(raw_json)
                
            except Exception as e:
                print(f"⚠️ [Agent] {endpoint['name']} failed: {e}. Trying next provider...")
                continue
                
        raise Exception("❌ All LLM endpoints (Primary, Fallback, Emergency) failed. Cannot generate config.")