import uuid


def answer(paper_ids: list[uuid.UUID], message: str, history: list[dict]) -> str:
    """
    STUB — replace with real RAG implementation.

    Expected real behavior:
      - retrieve relevant chunks from the vector store for the given paper_ids
      - pass retrieved context + message + history to the LLM
      - return the generated answer as a plain string

    Args:
        paper_ids: papers this chat is scoped to (already validated as indexed/ready
                    by the caller before this function is invoked)
        message: the user's latest message
        history: prior turns in this conversation, as [{"role": "user"|"assistant", "content": str}, ...]

    Returns:
        The assistant's reply text.
    """
    paper_list = ", ".join(str(pid) for pid in paper_ids) if paper_ids else "no papers selected"
    return f"[stub response] You asked: '{message}' (scoped to: {paper_list})"