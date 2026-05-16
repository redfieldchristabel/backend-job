import unittest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from src.app import app

class TestLeaveAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Assuming Bob's seed ID is 2 and Alice's seed ID is 1
        self.bob_headers = {"X-Current-User": "2"}
        self.alice_headers = {"X-Current-User": "1"}

    def test_list_employees(self):
        resp = self.client.get("/employees")
        self.assertEqual(resp.status_code, 200)

    def test_create_leave_request_api(self):
        """Test endpoint handles headers and body validation cleanly."""
        payload = {
            "leave_type": "annual",
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=7)),
            "reason": "Api test leave"
        }
        # Post request with mock user header applied
        resp = self.client.post("/leave-requests", json=payload, headers=self.bob_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["status"], "pending")

    def test_missing_auth_header_returns_401(self):
        """Ensures your custom get_current_user logic rejects anonymous traffic."""
        payload = {
            "leave_type": "sick",
            "start_date": str(date.today() + timedelta(days=1)),
            "end_date": str(date.today() + timedelta(days=1))
        }
        resp = self.client.post("/leave-requests", json=payload) # No headers
        self.assertEqual(resp.status_code, 401)

    def test_cancel_leave_via_subresource_status(self):
        """Test your custom PUT /leave-requests/{id}/status endpoint layout."""
        # 1. Create a request first
        create_payload = {
            "leave_type": "annual",
            "start_date": str(date.today() + timedelta(days=10)),
            "end_date": str(date.today() + timedelta(days=11))
        }
        req_id = self.client.post("/leave-requests", json=create_payload, headers=self.bob_headers).json()["id"]

        # 2. Update status to 'cancelled' via PUT subresource
        status_payload = {"status": "cancelled"}
        resp = self.client.put(f"/leave-requests/{req_id}/status", json=status_payload, headers=self.bob_headers)
        
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "cancelled")

    def test_invalid_status_transition_returns_422(self):
        """Validates Pydantic intercepts incorrect enum strings automatically."""
        status_payload = {"status": "not-a-real-status"}
        resp = self.client.put("/leave-requests/1/status", json=status_payload, headers=self.bob_headers)
        
        # Pydantic validation intercept triggers custom validation handler automatically
        self.assertEqual(resp.status_code, 422)
        self.assertIn("errors", resp.json())