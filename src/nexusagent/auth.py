from nexusagent.keystore import Keystore

class AuthManager:
    def __init__(self):
        self.keystore = Keystore()

    def get_api_key(self, service_name: str) -> str:
        key = self.keystore.get_secret(service_name)
        if not key:
            raise ValueError(f"No secret found for {service_name}")
        return key

    def register_service(self, service_name: str, api_key: str):
        self.keystore.save_secret(service_name, api_key)
