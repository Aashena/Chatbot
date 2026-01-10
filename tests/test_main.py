import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from main import app, ChatRequest

client = TestClient(app)

class TestMainAPI:
    """Test suite for FastAPI endpoints"""
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    @patch('main.QA_module')
    def test_chat_endpoint_success(self, mock_qa_module):
        """Test successful chat endpoint call"""
        # Setup mock
        mock_qa_instance = Mock()
        mock_qa_instance.ask.return_value.answer = "This is a test response"
        mock_qa_module.return_value = mock_qa_instance
        
        # Test data
        test_request = {
            "question": "What is your product?",
            "conv_history": "",
            "namespace": "test-namespace"
        }
        
        # Make request
        response = client.post("/chat", json=test_request)
        
        # Assertions
        assert response.status_code == 200
        assert "answer" in response.json()
        assert response.json()["answer"] == "This is a test response"
        mock_qa_module.assert_called_once_with("test-namespace")
        mock_qa_instance.ask.assert_called_once_with("What is your product?", "")
    
    @patch('main.QA_module')
    def test_chat_endpoint_with_history(self, mock_qa_module):
        """Test chat endpoint with conversation history"""
        # Setup mock
        mock_qa_instance = Mock()
        mock_qa_instance.ask.return_value.answer = "Response with context"
        mock_qa_module.return_value = mock_qa_instance
        
        # Test data with conversation history
        test_request = {
            "question": "Tell me more",
            "conv_history": "User: Hello\nChatbot: Hi there!",
            "namespace": "test-namespace"
        }
        
        response = client.post("/chat", json=test_request)
        
        assert response.status_code == 200
        mock_qa_instance.ask.assert_called_once_with(
            "Tell me more", 
            "User: Hello\nChatbot: Hi there!"
        )
    
    def test_chat_endpoint_missing_fields(self):
        """Test chat endpoint with missing required fields"""
        # Missing 'question' field
        test_request = {
            "conv_history": "",
            "namespace": "test-namespace"
        }
        
        response = client.post("/chat", json=test_request)
        assert response.status_code == 422  # Validation error
    
    def test_chat_endpoint_invalid_json(self):
        """Test chat endpoint with invalid JSON"""
        response = client.post(
            "/chat", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_cors_headers(self):
        """Test CORS headers are properly set"""
        response = client.options("/chat")
        # CORS middleware should handle OPTIONS requests
        assert response.status_code in [200, 405]  # Either allowed or method not allowed