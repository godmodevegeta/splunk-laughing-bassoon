# agent/schemaops_agent.py
import os
import json
import re
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class SchemaOpsAgent:
    def __init__(self):
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
                "model": "openai/gpt-oss-20b"
            }
        }
        
    def validate_regex_safety(self, config_dict):
        """Catches catastrophic backtracking patterns in LLM-generated regex."""
        dangerous_patterns = [r"(.*?)", r".*+", r"(.+)*", r"(a|a)*"]
        
        for key, value in config_dict.items():
            if key.startswith("EXTRACT-"):
                for bad_pattern in dangerous_patterns:
                    # Basic string matching for standard bad patterns
                    if bad_pattern in value:
                        raise ValueError(f"🛑 CATASTROPHIC BACKTRACKING DETECTED in {key}: The pattern '{bad_pattern}' is blocked by the safety linter.")
        return True

    def _clean_json_response(self, raw_text):
        """Strips markdown code blocks if the LLM ignores response_format."""
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        return json.loads(clean_text.strip())

    def generate_config(self, raw_log, attempt=1, previous_feedback=None):
        system_prompt = """You are 'SchemaOps', an expert Splunk Data Engineer.
Your job is to analyze raw log data and generate the exact props.conf key-value pairs required to parse it into Splunk.

CRITICAL RULES:
1. ONLY return a valid JSON object with "intended_fields" and "config".
2. FORMAT DETECTION FIRST: Determine if the log is JSON, CSV, Key-Value, or Unstructured/Syslog.
3. USE NATIVE SPLUNK: If it is JSON, do NOT write regex. Output {"KV_MODE": "none", "INDEXED_EXTRACTIONS": "json"}. 
4. FOR UNSTRUCTURED/SYSLOG: Write regex to extract the standard headers (timestamp, host, process, pid) and capture the rest as a 'message' field.
5. ONLY write custom EXTRACT-<fieldname> regexes if native KV extraction will fail (e.g., custom delimiters like '|~|').
Example: 
{
  "intended_fields": ["src_ip", "action"],
  "config": {
    "SHOULD_LINEMERGE": "false", 
    "TIME_FORMAT": "%Y-%m-%d %H:%M:%S", 
    "EXTRACT-src_ip": "IP:(?<src_ip>\\d+\\.\\d+\\.\\d+\\.\\d+)"
  }
}
"""

        user_prompt = f"Target Log to Parse:\n{raw_log}\n\n"
        
        if attempt > 1 and previous_feedback:
            user_prompt += f"WARNING! Your previous attempt failed.\nFeedback: {previous_feedback}\nRewrite your regex and config to fix this. Do not use the exact same regex."
        else:
            user_prompt += "Generate the Splunk props.conf JSON for this log."

        for level, endpoint in self.providers.items():
            try:
                logger.info(f"🤖 [Agent] Routing prompt to {endpoint['name']} using {endpoint['model']}...")
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
                    temperature=0.1, 
                    response_format={"type": "json_object"}
                )
                
                raw_json = self._clean_json_response(response.choices[0].message.content)
                self.validate_regex_safety(raw_json.get("config", {}))
                
                logger.info(f"✅ Successfully generated config via {endpoint['name']}.")
                return raw_json.get("intended_fields", []), raw_json.get("config", {})
                
            except Exception as e:
                logger.warning(f"⚠️ [Agent] {endpoint['name']} failed: {e}. Trying next provider...")
                continue
                
        # Point 10 Fix: Graceful Degradation
        logger.error("❌ All LLM endpoints failed. Reverting to Offline Graceful Degradation.")
        return {
            "SHOULD_LINEMERGE": "false",
            "TIME_FORMAT": "%Y-%m-%d %H:%M:%S",
            "EXTRACT-offline_mode": "(?<error>LLM OFFLINE - PLEASE EDIT CONFIG MANUALLY)"
        }