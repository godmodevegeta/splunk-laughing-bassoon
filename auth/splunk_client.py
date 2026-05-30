# auth/splunk_client.py
import requests
import urllib3

# Suppress insecure request warnings for local Splunk Docker instances
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SplunkRestClient:
    """A thin HTTP client for Splunk administrative tasks (Configs & Ingestion)."""
    
    def __init__(self, host, port, username, password):
        self.base_url = f"https://{host}:{port}"
        self.session = requests.Session()
        self.session.verify = False  # Required for self-signed Splunk certs

        # 1. Exchange credentials for a Session Key
        auth_url = f"{self.base_url}/services/auth/login?output_mode=json"
        auth_payload = {'username': username, 'password': password}
        auth_response = self.session.post(auth_url, data=auth_payload)
        auth_response.raise_for_status()
        
        session_key = auth_response.json().get('sessionKey')
        
        # 2. Inject the Session Key into the headers for all future requests
        self.session.headers.update({
            'Authorization': f'Splunk {session_key}'
        })

    def ping(self):
        """
        Verify connection to Splunk REST API.
        Expected verify: Returns True and HTTP 200 OK status.
        """
        url = f"{self.base_url}/services/server/info?output_mode=json"
        
        # We explicitly request JSON output, as Splunk defaults to XML
        response = self.session.get(url)
        response.raise_for_status()  # Fails fast if auth/connection fails
        
        data = response.json()
        print(f"✅ Successfully connected to Splunk Enterprise (Version {data['generator']['version']})")
        return True
    def set_props_config(self, stanza, properties, app_context="search"):
        """
        Creates or updates a props.conf stanza.
        """
        # 1. Check if the stanza already exists
        check_url = f"{self.base_url}/servicesNS/nobody/{app_context}/configs/conf-props/{stanza}?output_mode=json"
        check_resp = self.session.get(check_url)
        
        payload = properties.copy()
        
        if check_resp.status_code == 200:
            # Update existing stanza
            url = f"{self.base_url}/servicesNS/nobody/{app_context}/configs/conf-props/{stanza}?output_mode=json"
            response = self.session.post(url, data=payload)
        else:
            # Create new stanza
            url = f"{self.base_url}/servicesNS/nobody/{app_context}/configs/conf-props?output_mode=json"
            payload['name'] = stanza
            response = self.session.post(url, data=payload)
            
        response.raise_for_status()
        return True

    def reload_parsing_configs(self):
        """
        Forces Splunk to reload props.conf and transforms.conf without restarting.
        Essential for the rapid TDD loop.
        """
        # 1. Reload props.conf
        props_url = f"{self.base_url}/services/configs/conf-props/_reload?output_mode=json"
        props_response = self.session.post(props_url)
        props_response.raise_for_status()

        # 2. Reload transforms.conf
        transforms_url = f"{self.base_url}/services/configs/conf-transforms/_reload?output_mode=json"
        transforms_response = self.session.post(transforms_url)
        transforms_response.raise_for_status()

        return True

    def get_props_config(self, stanza, app_context="search"):
        """
        Fetches the stanza to verify the settings were applied.
        """
        url = f"{self.base_url}/servicesNS/nobody/{app_context}/configs/conf-props/{stanza}?output_mode=json"
        response = self.session.get(url)
        response.raise_for_status()
        
        # Splunk returns a nested JSON structure; we extract the actual key-value contents
        return response.json()['entry'][0]['content']
    
    def ingest_logs(self, raw_text, sourcetype, source, index="main"):
        """
        Pushes raw log text into Splunk using the REST API receivers/simple endpoint.
        """
        # Splunk requires ingestion metadata to be passed as URL query parameters for this endpoint
        url = f"{self.base_url}/services/receivers/simple?index={index}&sourcetype={sourcetype}&source={source}&output_mode=json"
        
        # We explicitly set text/plain so Splunk parses it as a raw byte stream
        headers = {'Content-Type': 'text/plain'}
        
        # self.session already has our 'Authorization: Splunk <sessionKey>' header injected
        response = self.session.post(url, headers=headers, data=raw_text.encode('utf-8'))
        response.raise_for_status()
        
        return response.json()