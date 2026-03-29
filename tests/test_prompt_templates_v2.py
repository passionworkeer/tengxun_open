from __future__ import annotations

import unittest

from pe.prompt_templates_v2 import (
    FEW_SHOT_LIBRARY,
    build_messages,
    build_user_prompt,
)


class PromptTemplatesV2Test(unittest.TestCase):
    def test_build_user_prompt_can_skip_empty_context_block(self) -> None:
        prompt = build_user_prompt(
            question="What is the final worker symbol?",
            context="",
            entry_symbol="celery.bin.worker.worker",
            include_empty_context=False,
        )

        self.assertNotIn("Context:\n", prompt)
        self.assertIn("Entry Symbol:\ncelery.bin.worker.worker", prompt)

    def test_build_messages_supports_assistant_fewshot_pairs(self) -> None:
        self.assertGreater(len(FEW_SHOT_LIBRARY), 0)

        messages = build_messages(
            question="What is the final worker symbol?",
            context="",
            entry_symbol="celery.bin.worker.worker",
            max_examples=1,
            include_empty_context=False,
            assistant_fewshot=True,
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "system")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[3]["role"], "assistant")
        self.assertIn('"ground_truth"', messages[3]["content"])
        self.assertEqual(messages[-1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
