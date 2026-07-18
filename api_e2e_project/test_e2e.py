import time

import pytest
import requests

API_URL = "http://127.0.0.1:5000"

@pytest.fixture(scope="module", autouse=True)
def wait_for_api():
    # In a real scenario, you might want a more robust health check
    # For this example, we'll just wait a few seconds for the Flask app to start
    time.sleep(3)

def test_hello_endpoint():
    try:
        response = requests.get(f"{API_URL}/hello")
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        assert data["message"] == "Hello, World!"
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to the API at {API_URL}. Is the Flask app running?")
