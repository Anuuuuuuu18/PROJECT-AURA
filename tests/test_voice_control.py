import io
import json
import unittest
from unittest.mock import patch

from voice_control import (
    OpenAICommandClient,
    OpenAIRequestError,
    _local_command,
    _validated_command,
)


class LocalCommandTests(unittest.TestCase):
    def test_parses_safe_local_actions(self):
        self.assertEqual(_local_command("resume AURA").action, "resume")
        self.assertEqual(_local_command("open Chrome").target, "chrome")

    def test_caps_spoken_scroll_amount(self):
        command = _local_command("scroll down 99")
        self.assertEqual(command.action, "scroll")
        self.assertEqual(command.direction, "down")
        self.assertEqual(command.amount, 10)

    def test_rejects_unsafe_or_invalid_model_actions(self):
        self.assertEqual(
            _validated_command(
                {"action": "open_app", "target": "cmd /c format", "direction": "none", "amount": 0},
                "open app",
            ).action,
            "unknown",
        )
        self.assertEqual(
            _validated_command(
                {"action": "scroll", "target": "", "direction": "up", "amount": 100},
                "scroll up",
            ).action,
            "unknown",
        )


class OpenAIClientTests(unittest.TestCase):
    def test_transcription_sends_wav_multipart_and_returns_text(self):
        client = OpenAICommandClient("test-key")
        request = {}

        def fake_request(url, body, content_type):
            request.update(url=url, body=body, content_type=content_type)
            return {"text": "open Chrome"}

        client._request_json = fake_request
        self.assertEqual(client.transcribe(b"\x00\x00" * 8000), "open Chrome")
        self.assertEqual(request["url"], "https://api.openai.com/v1/audio/transcriptions")
        self.assertTrue(request["content_type"].startswith("multipart/form-data; boundary="))
        self.assertIn(b"gpt-4o-mini-transcribe", request["body"])
        self.assertIn(b"RIFF", request["body"])

    def test_api_request_uses_the_configured_bearer_key(self):
        client = OpenAICommandClient("test-key")
        captured = {}

        def fake_urlopen(request, timeout):
            captured["authorization"] = request.get_header("Authorization")
            return io.BytesIO(b'{"ok": true}')

        with patch("voice_control.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client._request_json(
                "https://api.openai.com/v1/test",
                b"{}",
                "application/json",
            )

        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(result, {"ok": True})

    def test_interpretation_uses_validated_structured_output(self):
        client = OpenAICommandClient("test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "action": "scroll",
                        "target": "",
                        "direction": "up",
                        "amount": 4,
                    })
                }
            }]
        }
        request = {}

        def fake_request(url, body, content_type):
            request.update(url=url, body=json.loads(body), content_type=content_type)
            return response

        client._request_json = fake_request
        command = client.interpret("scroll up four times")
        self.assertEqual(command.action, "scroll")
        self.assertEqual(command.direction, "up")
        self.assertEqual(command.amount, 4)
        self.assertTrue(request["body"]["response_format"]["json_schema"]["strict"])

    def test_api_failure_falls_back_to_local_command_and_surfaces_error(self):
        client = OpenAICommandClient("test-key")

        def fail_transcription(_audio):
            raise OpenAIRequestError("OpenAI API returned HTTP 429")

        client.transcribe = fail_transcription
        command = client.process(b"\x00\x00", "pause AURA")
        self.assertEqual(command.action, "pause")
        self.assertIn("429", command.error)


if __name__ == "__main__":
    unittest.main()
