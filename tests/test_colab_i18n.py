"""Check the Gradio/i18n versions used by Colab without any ML dependencies."""

import importlib.util
import os
import unittest

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"


@unittest.skipUnless(importlib.util.find_spec("gradio"), "Gradio is not installed")
class ColabI18nTests(unittest.TestCase):
    def test_translated_text_outside_request(self):
        from gradio.context import LocalContext
        from gradio_i18n import gettext

        self.assertIsNone(LocalContext.request.get())
        text = gettext("Automatic Detection")
        self.assertEqual(text.unwrap(), "Automatic Detection")

    def test_translated_page_and_config_respond(self):
        import gradio as gr
        from gradio_i18n import Translate, gettext
        from fastapi.testclient import TestClient

        with gr.Blocks() as demo:
            with Translate({"en": {"Hello": "Hello"}, "zh": {"Hello": "你好"}}):
                gr.Markdown(gettext("Hello"))
        with TestClient(gr.routes.App.create_app(demo)) as client:
            self.assertEqual(client.get("/", headers={"Accept-Language": "zh-TW"}).status_code, 200)
            config = client.get("/config")
            self.assertEqual(config.status_code, 200)
            self.assertTrue(config.json()["components"])


if __name__ == "__main__":
    unittest.main()
