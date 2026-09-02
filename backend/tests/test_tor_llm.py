import unittest
from unittest.mock import Mock, patch

from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_llm import LlmSchemaError, analyze_with_llm, parse_llm_content


class TorLlmTests(unittest.TestCase):
    def test_requests_thai_summary_and_explanations_from_llm(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": '{"summary":"สรุปภาษาไทย","findings":[]}'}}]
        }
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test", "LLM_BASE_URL": "https://example.test"}),
            patch("ai_gov_transparency.tor_llm.httpx.post", return_value=response) as post,
        ):
            analyze_with_llm([PageText(1, "ข้อกำหนด", False, 1.0)])

        system_prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("summary and reason must be written in Thai", system_prompt)
        self.assertIn("evidence must remain an exact quote", system_prompt)
        self.assertIn("concise, natural Thai", system_prompt)
        self.assertIn("one sentence", system_prompt)

    def test_preserves_long_llm_evidence_and_reason_without_character_slicing(self):
        evidence = "หลักฐาน" * 80
        reason = "คำอธิบาย" * 80
        payload = (
            '{"summary":"สรุป","findings":[{"category":"brand_specific","severity":"high",'
            f'"evidence":"{evidence}","page":2,"reason":"{reason}","confidence":0.9}}]}}'
        )

        finding = parse_llm_content(payload).findings[0]

        self.assertEqual(finding.evidence, evidence)
        self.assertEqual(finding.reason, reason)

    def test_validates_and_preserves_evidence_separately(self):
        result = parse_llm_content('{"summary":"สรุป","findings":[{"category":"brand_specific","severity":"high","evidence":"ยี่ห้อ ACME เท่านั้น","page":2,"reason":"ไม่เปิดให้เทียบเท่า","confidence":0.9}]}')
        self.assertEqual(result.findings[0].evidence, "ยี่ห้อ ACME เท่านั้น")
        self.assertEqual(result.findings[0].reason, "ไม่เปิดให้เทียบเท่า")

    def test_rejects_unknown_category(self):
        with self.assertRaises(LlmSchemaError):
            parse_llm_content('{"summary":"x","findings":[{"category":"corruption","severity":"high","evidence":"x","page":1,"reason":"x","confidence":1}]}')

    def test_rejects_english_summary_and_reason_instead_of_showing_them(self):
        with self.assertRaisesRegex(LlmSchemaError, "ภาษาไทย"):
            parse_llm_content('{"summary":"Competition is restricted","findings":[{"category":"brand_specific","severity":"high","evidence":"ACME only","page":1,"reason":"No equivalent product is allowed","confidence":0.9}]}')


if __name__ == "__main__":
    unittest.main()
