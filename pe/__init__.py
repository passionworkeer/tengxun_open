"""Prompt engineering core module for Python cross-file dependency analysis.

This package provides the end-to-end prompt construction and output parsing
pipeline used by the PE (Prompt Engineering) system to resolve fully qualified
names (FQNs) in Celery source code via large language models.

Exported API (public surface):
    from pe import (
        FewShotExample,          # Dataclass: one curated few-shot case
        PromptBundle,            # Dataclass: assembled prompt components
        FEW_SHOT_LIBRARY,         # List[FewShotExample]: curated case library
        SYSTEM_PROMPT,            # str: fixed system-level instructions
        COT_TEMPLATE,             # str: chain-of-thought checklist scaffold
        OUTPUT_INSTRUCTIONS,      # str: short output format reminder
        REQUIRED_FEW_SHOT_TARGET, # int: minimum recommended library size
        # Construction helpers
        select_few_shot_examples, # Select top-k relevant examples by scoring
        build_user_prompt,        # Assemble the user-facing question block
        build_prompt_bundle,      # Assemble all components into a PromptBundle
        build_messages,           # Build chat-style message list for inference
        few_shot_gap,             # Compute how many more examples are needed
        # Output parsing
        parse_model_output,       # Parse flat model output → list[FQN]
        parse_model_output_layers,# Parse layered output → {layer: [FQN]}
        normalize_fqn,            # Normalise a string to canonical FQN form
        is_valid_fqn,              # Check whether a string is a valid FQN
        dedupe_preserve_order,     # Deduplicate a sequence while keeping order
    )

Internal helpers (_extract_candidates, _try_parse_json, _flatten_json,
_TOKEN_PATTERN, FQN_PATTERN, etc.) are not exported and may change without
notice.
"""

