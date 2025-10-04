from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)


def safe_trim_messages(messages, max_tokens=1024):
    """
    Trim messages for LLM input, but ensure at least one human message survives.
    """
    trimmed = trim_messages(
        messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=max_tokens,
        start_on="human",
        end_on=("human","ai"),
    )

    # If trim removed all human messages, keep the last one
    if not any(isinstance(m, HumanMessage) for m in trimmed):
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                trimmed.append(msg)
                break

    return trimmed
