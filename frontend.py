
import http.client
import time

HOST_NAME = "localhost"
SERVER_PORT = 8080

if __name__ == "__main__":
    print(f"Attempting to connect to http://%s:%s" % (HOST_NAME, SERVER_PORT))
    try:
        conn = http.client.HTTPConnection(HOST_NAME, SERVER_PORT)
        conn.request("GET", "/")
        response = conn.getresponse()
        print(f"Response status: {response.status}")
        print(f"Response reason: {response.reason}")
        print("E2E connectivity check successful!")
    except ConnectionRefusedError:
        print("Connection refused. Ensure the backend server is running.")
        print("E2E connectivity check failed.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("E2E connectivity check failed.")
