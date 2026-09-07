from llm.lmstudio import LMStudioClient


def test_qwen_messages_receive_no_think():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Explain the scoring system."},
    ]
    prepared = LMStudioClient._prepare_messages("qwen3.5-4b", messages)
    assert "/no_think" in prepared[-1]["content"]
    assert "/no_think" not in messages[-1]["content"]


def test_non_qwen_messages_are_not_modified_with_no_think():
    messages = [{"role": "user", "content": "Hello"}]
    prepared = LMStudioClient._prepare_messages("some-other-model", messages)
    assert "/no_think" not in prepared[-1]["content"]


def test_content_normalizer_handles_string_and_parts():
    assert LMStudioClient._text_from_content("  final answer  ") == "final answer"
    assert LMStudioClient._text_from_content([{"text": "A"}, {"text": "B"}]) == "A\nB"


def test_visible_final_text_removes_thinking_block():
    text = "<think>private reasoning here</think>Final answer [S1]"
    assert LMStudioClient._visible_final_text(text) == "Final answer [S1]"


def test_visible_final_text_rejects_unclosed_thinking():
    assert LMStudioClient._visible_final_text("<think>still thinking") == ""


def test_responses_json_extractor_reads_output_text():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Answer from responses [S1]"}],
            }
        ]
    }
    assert LMStudioClient._text_from_responses_json(payload) == "Answer from responses [S1]"


def test_compact_messages_keeps_tail_question():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "A" * 5000 + "\nUSER QUESTION\nWhat is M4A1?"},
    ]
    compact = LMStudioClient._compact_messages(messages, 1000)
    assert len(compact[-1]["content"]) < 1200
    assert "What is M4A1?" in compact[-1]["content"]
