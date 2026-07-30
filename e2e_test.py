import requests
import unittest
import subprocess
import time
import os

class TestUserAPI(unittest.TestCase):
    BASE_URL = "http://127.0.0.1:5000"
    PROCESS = None

    @classmethod
    def setUpClass(cls):
        # Start the Flask API server
        cls.PROCESS = subprocess.Popen(["python3", "main.py"])
        time.sleep(2)  # Give the server time to start

    @classmethod
    def tearDownClass(cls):
        # Stop the Flask API server
        if cls.PROCESS:
            cls.PROCESS.terminate()
            cls.PROCESS.wait()

    def test_e2e_user_flow(self):
        # 1. Create a user
        print("\n--- Testing Create User ---")
        user_data = {"name": "John Doe", "email": "john.doe@example.com"}
        response = requests.post(f"{self.BASE_URL}/users", json=user_data)
        self.assertEqual(response.status_code, 201)
        created_user = response.json()
        self.assertIn("id", created_user)
        self.assertEqual(created_user["name"], "John Doe")
        user_id = created_user["id"]
        print(f"Created user: {created_user}")

        # 2. Get the created user
        print("\n--- Testing Get User ---")
        response = requests.get(f"{self.BASE_URL}/users/{user_id}")
        self.assertEqual(response.status_code, 200)
        fetched_user = response.json()
        self.assertEqual(fetched_user["id"], user_id)
        self.assertEqual(fetched_user["name"], "John Doe")
        print(f"Fetched user: {fetched_user}")

        # 3. Update the user
        print("\n--- Testing Update User ---")
        updated_data = {"name": "Jane Doe", "email": "jane.doe@example.com"}
        response = requests.put(f"{self.BASE_URL}/users/{user_id}", json=updated_data)
        self.assertEqual(response.status_code, 200)
        updated_user = response.json()
        self.assertEqual(updated_user["name"], "Jane Doe")
        print(f"Updated user: {updated_user}")

        # 4. Get the updated user to verify
        print("\n--- Testing Get Updated User ---")
        response = requests.get(f"{self.BASE_URL}/users/{user_id}")
        self.assertEqual(response.status_code, 200)
        verified_user = response.json()
        self.assertEqual(verified_user["name"], "Jane Doe")
        print(f"Verified updated user: {verified_user}")

        # 5. Delete the user
        print("\n--- Testing Delete User ---")
        response = requests.delete(f"{self.BASE_URL}/users/{user_id}")
        self.assertEqual(response.status_code, 204)
        print(f"Deleted user with ID: {user_id}")

        # 6. Try to get the deleted user (should return 404)
        print("\n--- Testing Get Deleted User (Expected 404) ---")
        response = requests.get(f"{self.BASE_URL}/users/{user_id}")
        self.assertEqual(response.status_code, 404)
        print(f"Attempted to fetch deleted user, got status: {response.status_code}")

if __name__ == '__main__':
    unittest.main()
