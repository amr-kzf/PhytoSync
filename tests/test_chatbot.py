import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from openai import APIError

from chatbot import DEFAULT_GROQ_MODEL, GROQ_BASE_URL
from app import app


class TestGroqChatbot(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "test-model"})
    @patch("chatbot.OpenAI")
    def test_uses_configured_groq_model(self, openai_client):
        completion = openai_client.return_value.chat.completions.create.return_value
        completion.choices = [
            SimpleNamespace(message=SimpleNamespace(content="Rotate crops to reduce disease pressure."))
        ]

        response = self.client.post("/chatbot", json={"question": "How do I reduce crop disease?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["response"], "Rotate crops to reduce disease pressure.")
        self.assertEqual(response.get_json()["mode"], "groq")
        openai_client.assert_called_once_with(api_key="test-key", base_url=GROQ_BASE_URL)
        openai_client.return_value.chat.completions.create.assert_called_once()
        self.assertEqual(
            openai_client.return_value.chat.completions.create.call_args.kwargs["model"],
            "test-model"
        )

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "test-model"})
    @patch("chatbot.OpenAI")
    def test_groq_connection_error_returns_service_error(self, openai_client):
        openai_client.return_value.chat.completions.create.side_effect = APIError(
            "Groq connection failed",
            request=None,
            body=None
        )

        response = self.client.post("/chatbot", json={"question": "How do I care for wheat?"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("temporarily unavailable", response.get_json()["error"])
        self.assertNotIn("test-key", response.get_data(as_text=True))

    @patch.dict(os.environ, {
        "GROQ_API_KEY": "test-key",
        "GROQ_MODEL": "llama-3.3-70b-versatile"
    })
    @patch("chatbot.OpenAI")
    def test_expired_model_returns_actionable_error(self, openai_client):
        error = APIError("Model is no longer available", request=None, body=None)
        error.status_code = 404
        openai_client.return_value.chat.completions.create.side_effect = error

        response = self.client.post("/chatbot", json={"question": "What is nitrogen?"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("GROQ_MODEL", response.get_json()["error"])
        self.assertIn("llama-3.3-70b-versatile", response.get_json()["error"])

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    @patch("chatbot.OpenAI")
    def test_rejected_key_returns_actionable_error(self, openai_client):
        error = APIError("Invalid API key", request=None, body=None)
        error.status_code = 401
        openai_client.return_value.chat.completions.create.side_effect = error

        response = self.client.post("/chatbot", json={"question": "What is nitrogen?"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("new GROQ_API_KEY", response.get_json()["error"])

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": ""})
    @patch("chatbot.OpenAI")
    def test_uses_default_groq_model(self, openai_client):
        completion = openai_client.return_value.chat.completions.create.return_value
        completion.choices = [
            SimpleNamespace(message=SimpleNamespace(content="Use a soil test to guide fertilizer."))
        ]

        response = self.client.post("/chatbot", json={"question": "How do I choose fertilizer?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            openai_client.return_value.chat.completions.create.call_args.kwargs["model"],
            DEFAULT_GROQ_MODEL
        )

    @patch.dict(os.environ, {"GROQ_API_KEY": ""})
    @patch("chatbot.OpenAI")
    def test_uses_offline_advisory_when_key_is_missing(self, openai_client):
        response = self.client.post("/chatbot", json={"question": "How do I care for wheat?"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Wheat thrives", response.get_json()["response"])
        self.assertEqual(response.get_json()["mode"], "offline")
        openai_client.assert_not_called()

    @patch.dict(os.environ, {"GROQ_API_KEY": ""})
    def test_greeting_gets_a_conversational_response(self):
        response = self.client.post("/chatbot", json={"question": "hi"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Hi!", response.get_json()["response"])

    @patch.dict(os.environ, {"GROQ_API_KEY": ""})
    def test_nitrogen_question_explains_n(self):
        response = self.client.post("/chatbot", json={"question": "what is N"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("nitrogen", response.get_json()["response"].lower())
        self.assertIn("leafy", response.get_json()["response"].lower())

    @patch.dict(os.environ, {"GROQ_API_KEY": ""})
    def test_unknown_question_explains_offline_limit(self):
        response = self.client.post("/chatbot", json={"question": "Explain quantum mechanics"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("offline guide", response.get_json()["response"])
        self.assertIn("GROQ_API_KEY", response.get_json()["response"])


if __name__ == "__main__":
    unittest.main()
