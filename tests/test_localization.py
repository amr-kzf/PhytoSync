import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from localization import localize_disease_result, translate_text


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def select_language(self, language):
        return self.client.post("/set-language", data={"language": language})

    def test_language_choice_persists_and_sets_rtl_document_direction(self):
        response = self.select_language("ar")
        self.assertEqual(response.status_code, 302)

        page = self.client.get("/")
        self.assertIn(b'<html lang="ar" dir="rtl">', page.data)
        self.assertIn(b'>EN</button>', page.data)
        self.assertIn(b'aria-pressed="true">AR</button>', page.data)

        self.select_language("en")
        page = self.client.get("/")
        self.assertIn(b'<html lang="en" dir="ltr">', page.data)

    def test_rejects_unsupported_language(self):
        response = self.select_language("fr")
        self.assertEqual(response.status_code, 400)

    def test_standalone_login_page_includes_language_switcher(self):
        self.select_language("ar")

        page = self.client.get("/login")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b'<html lang="ar" dir="rtl">', page.data)
        self.assertIn(b'>EN</button>', page.data)
        self.assertIn(b'aria-pressed="true">AR</button>', page.data)

    @patch.dict(os.environ, {"GROQ_API_KEY": ""})
    def test_offline_assistant_replies_in_selected_language(self):
        self.select_language("ar")

        response = self.client.post("/chatbot", json={"question": "السلام عليكم"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["mode"], "offline")
        self.assertIn("مرحبًا", data["response"])

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    @patch("chatbot.OpenAI")
    def test_hosted_assistant_prompt_uses_selected_language(self, openai_client):
        self.select_language("ar")
        completion = openai_client.return_value.chat.completions.create.return_value
        completion.choices = [
            SimpleNamespace(message=SimpleNamespace(content="إجابة تجريبية"))
        ]

        response = self.client.post("/chatbot", json={"question": "Recommend irrigation"})

        self.assertEqual(response.status_code, 200)
        system_prompt = openai_client.return_value.chat.completions.create.call_args.kwargs[
            "messages"
        ][0]["content"]
        self.assertIn("Respond in Arabic", system_prompt)
        self.assertEqual(response.get_json()["response"], "إجابة تجريبية")

    def test_disease_model_display_label_is_translated_without_changing_canonical_label(self):
        result = localize_disease_result(
            {"label": "Tomato___Late_blight", "precautions": []},
            "ar",
        )

        self.assertEqual(result["label"], "Tomato___Late_blight")
        self.assertEqual(result["display_label"], "اللفحة المتأخرة في الطماطم")

    def test_crop_and_irrigation_output_translations(self):
        self.assertEqual(translate_text("rice", "ar"), "أرز")
        self.assertEqual(translate_text("IRRIGATE_NOW", "ar"), "الري الآن")

    @patch("disease_detection.predict_leaf_disease")
    def test_disease_api_includes_arabic_display_label(self, predict):
        self.select_language("ar")
        predict.return_value = {
            "label": "Tomato___Late_blight",
            "confidence": 0.8,
            "precautions": [],
            "quality_warnings": [],
            "alternatives": [],
            "model_notice": "Demo leaf analysis mode active.",
            "crop_filter_applied": None,
            "crop_refinements": [],
        }

        response = self.client.post(
            "/api/disease/predict",
            data={"file": (io.BytesIO(b"leaf-image"), "leaf.jpg")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["label"], "Tomato___Late_blight")
        self.assertEqual(data["display_label"], "اللفحة المتأخرة في الطماطم")

    def test_irrigation_api_returns_arabic_explanation(self):
        self.select_language("ar")

        response = self.client.post(
            "/api/advisory",
            json={
                "crop": "Tomato",
                "stage": "growing",
                "soil_moisture_pct": 20,
                "temperature_c": 29,
                "humidity_pct": 65,
                "rain_probability_pct": 10,
                "forecast_rain_mm": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["irrigation_action"], "IRRIGATE_NOW")
        self.assertEqual(data["action_label"], "الري الآن")
        self.assertIn("رطوبة التربة", data["reason_display"])


if __name__ == "__main__":
    unittest.main()
