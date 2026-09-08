"""
chatbot.py

RAG chatbot with:
  - Routing between the local Chroma vector DB and your existing
    fetch_papers.py (arXiv search + download), via OpenAI tool calling.
  - Explicit clarification when routing is ambiguous.
  - A "summarize this chat" tool (200-700 words, scaled to chat length).
  - Rolling-summary memory management for long conversations.
  - Persistence: every message in every session is saved to SQLite
    (chat_store.py) so past chats can be listed and resumed later.
  - fetch_new_papers only surfaces title/URL for the user to review;
    download_paper downloads a chosen one and ingests it into Chroma.
"""

import os
import json

import requests
import tiktoken
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions

import chat_store
from fetch_papers import fetch_papers          # your arXiv search function
from vectorisation import vectorising_pdf       # chunk + embed + store in Chroma

from dotenv import load_dotenv
load_dotenv()

# --- config ---------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "chroma_db")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "data", "downloaded")
COLLECTION_NAME = "papers"
EMBEDDING_MODEL_NAME = "multi-qa-MiniLM-L6-cos-v1"
CHAT_MODEL = "gpt-4o-mini"

MAX_HISTORY_TOKENS = 3000
KEEP_RECENT_TURNS = 4

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- setup ------------------------------------------------------------------

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL_NAME
)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_collection(
    name=COLLECTION_NAME, embedding_function=embedding_fn
)

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

try:
    ENCODER = tiktoken.encoding_for_model(CHAT_MODEL)
except KeyError:
    ENCODER = tiktoken.get_encoding("cl100k_base")

SYSTEM_PROMPT = """You are a research assistant for a paper database and chatbot.

Tools:
- search_paper_database: for questions about paper content, methodologies, findings, comparisons among papers ALREADY in the database.
- fetch_new_papers: ONLY when the user explicitly asks to fetch/retrieve/find NEW papers from arXiv. This only shows titles and URLs - it does NOT download or add anything to the database.
- download_paper: downloads one specific paper that was just shown via fetch_new_papers, and adds it to the database. Only call this after the user has been shown paper options and clearly says which one(s) to download (by title or by the id shown). Never call this speculatively.
- summarize_conversation: when the user asks for a summary/recap of this chat.

IMPORTANT: If it is not clear whether the user wants to search the existing
database or fetch new papers from arXiv, do NOT guess and do NOT call either
tool. Instead, ask the user a short clarifying question.

After fetch_new_papers runs, present the titles and URLs to the user and ask
which (if any) they'd like downloaded and added to the database - do not
download anything automatically.

After a tool returns results, answer the user directly using those results.
Cite pdf_id sources when using search_paper_database results.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_paper_database",
            "description": (
                "Search the local database of already-ingested papers to answer "
                "a question, explain a methodology, or find relevant excerpts."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_new_papers",
            "description": (
                "Search arXiv for NEW papers on a topic and return their titles "
                "and URLs for the user to review. Does NOT download anything. "
                "Use when the user explicitly asks to fetch/retrieve/find new "
                "or additional papers."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_paper",
            "description": (
                "Download a specific paper that was previously shown via "
                "fetch_new_papers, and add it to the local paper database. "
                "Requires the paper's id as shown in the fetch results. Only "
                "call this after the user explicitly confirms which paper(s) "
                "to download."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "The arXiv id of the paper to download, exactly as shown in the fetch_new_papers results.",
                    }
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_conversation",
            "description": (
                "Produce a summary of THIS chat session so far: what the user "
                "asked, and how the assistant answered/clarified."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# --- chat session -------------------------------------------------------

class ChatSession:
    def __init__(self, session_id: str | None = None):
        """
        session_id=None  -> starts a brand-new persisted session.
        session_id=<id>  -> resumes a previous session, reloading its
                             message history and rolling summary from disk.
        """
        if session_id:
            self.session_id = session_id
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_store.load_messages(session_id)
            self.rolling_summary = chat_store.get_rolling_summary(session_id)
        else:
            self.session_id = chat_store.create_session()
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            self.rolling_summary = None

        # paper_id -> full metadata dict, from the most recent fetch_new_papers
        # call, so download_paper can look up a pdf_url by id alone
        self.last_fetched_papers: dict = {}

        self.tool_impls = {
            "search_paper_database": self._search_paper_database,
            "fetch_new_papers": self._fetch_new_papers,
            "download_paper": self._download_paper,
            "summarize_conversation": self._summarize_conversation,
        }

    # --- persistence helper: append to memory AND disk together -----------

    def _append(self, entry: dict) -> None:
        self.messages.append(entry)
        chat_store.save_message(
            self.session_id,
            role=entry["role"],
            content=entry.get("content"),
            tool_call_id=entry.get("tool_call_id"),
            tool_calls=entry.get("tool_calls"),
        )

    # --- tool implementations ---------------------------------------------

    def _search_paper_database(self, query: str, top_k: int = 5) -> str:
        results = collection.query(query_texts=[query], n_results=top_k)
        if not results["documents"][0]:
            return "No relevant content found in the database."
        blocks = [
            f"[Source: {meta['pdf_id']}]\n{doc}"
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]
        return "\n\n---\n\n".join(blocks)

    def _fetch_new_papers(self, query: str) -> str:
        results = fetch_papers(query)
        if not results:
            return f"No new papers found on arXiv for '{query}'."

        # remember these so download_paper(paper_id) can find them later
        self.last_fetched_papers = {p["id"]: p for p in results}

        return "Found papers (not downloaded yet):\n" + "\n".join(
            f"- [{p['id']}] {p['title']} ({p['pdf_url']})" for p in results
        )

    def _download_paper(self, paper_id: str) -> str:
        paper = self.last_fetched_papers.get(paper_id)
        if not paper:
            return (
                f"'{paper_id}' doesn't match any paper from the last search. "
                "Ask the user to confirm the exact id from the list shown."
            )

        pdf_path = os.path.join(DOWNLOAD_DIR, f"{paper_id}.pdf")
        try:
            response = requests.get(paper["pdf_url"], timeout=30)
            response.raise_for_status()
            with open(pdf_path, "wb") as f:
                f.write(response.content)
        except requests.RequestException as e:
            return f"Failed to download '{paper['title']}': {e}"

        # ingest into the vector DB immediately, carrying arXiv metadata along
        num_chunks = vectorising_pdf(
            pdf_path,
            extra_metadata={
                "title": paper["title"],
                "authors": ", ".join(paper["authors"]),
                "published": paper["published"],
                "categories": ", ".join(paper["categories"]),
            },
        )
        return (
            f"Downloaded and added '{paper['title']}' to the database "
            f"({num_chunks} chunks indexed)."
        )

    def _summarize_conversation(self) -> str:
        return self._generate_summary()

    # --- summary generation -------------------------------------------------

    def _generate_summary(self) -> str:
        user_turns = [m for m in self.messages if m["role"] == "user"]
        num_turns = len(user_turns) + (1 if self.rolling_summary else 0)
        target_words = min(700, max(200, 150 + num_turns * 60))

        transcript_parts = []
        if self.rolling_summary:
            transcript_parts.append(f"[Earlier conversation summary]\n{self.rolling_summary}")
        for m in self.messages:
            if m["role"] == "user":
                transcript_parts.append(f"User: {m['content']}")
            elif m["role"] == "assistant" and isinstance(m.get("content"), str) and m["content"]:
                transcript_parts.append(f"Assistant: {m['content']}")
        transcript = "\n".join(transcript_parts)

        prompt = f"""Summarize the following conversation between a user and a
research-paper assistant. Focus on: what the user asked about, and how the
assistant answered or clarified things. Describe the flow of the
conversation, not just a topic list. Write approximately {target_words}
words (must be between 200 and 700 words).

Conversation:
{transcript}

Summary:"""

        response = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    # --- memory management ---------------------------------------------

    def _count_tokens(self, messages) -> int:
        total = 0
        for m in messages:
            content = m.get("content")
            if isinstance(content, str):
                total += len(ENCODER.encode(content))
        return total

    def _compress_history_if_needed(self) -> None:
        body = self.messages[1:]

        turns = []
        for m in body:
            if m["role"] == "user":
                turns.append([m])
            elif turns:
                turns[-1].append(m)

        if len(turns) <= KEEP_RECENT_TURNS:
            return

        old_turns = turns[:-KEEP_RECENT_TURNS]
        recent_turns = turns[-KEEP_RECENT_TURNS:]
        old_messages = [m for turn in old_turns for m in turn]

        if self._count_tokens(old_messages) < MAX_HISTORY_TOKENS:
            return

        text_lines = []
        if self.rolling_summary:
            text_lines.append(f"[Prior summary]\n{self.rolling_summary}")
        for m in old_messages:
            if m["role"] == "user":
                text_lines.append(f"User: {m['content']}")
            elif m["role"] == "assistant" and isinstance(m.get("content"), str) and m["content"]:
                text_lines.append(f"Assistant: {m['content']}")

        summary_prompt = (
            "Condense the following conversation excerpt into a compact summary "
            "preserving what the user asked and what was answered, for use as "
            "context in a continuing chat:\n\n" + "\n".join(text_lines)
        )
        response = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": summary_prompt}],
        )
        self.rolling_summary = response.choices[0].message.content
        chat_store.update_rolling_summary(self.session_id, self.rolling_summary)

        # NOTE: this only compresses the in-memory working set sent to the
        # model on future turns. The full transcript remains on disk in
        # chat_store regardless, so "recover old chats" is unaffected -
        # this trimming is purely a token-cost/context-window optimization.
        recent_messages = [m for turn in recent_turns for m in turn]
        self.messages = (
            [self.messages[0]]
            + [{"role": "system", "content": f"Summary of earlier conversation: {self.rolling_summary}"}]
            + recent_messages
        )

    # --- main entry point -------------------------------------------------

    def ask(self, user_message: str) -> str:
        self._append({"role": "user", "content": user_message})
        chat_store.set_session_title_if_unset(self.session_id, user_message)

        response = openai_client.chat.completions.create(
            model=CHAT_MODEL, messages=self.messages, tools=TOOLS
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            tool_calls_dicts = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
            self._append({"role": "assistant", "content": msg.content, "tool_calls": tool_calls_dicts})

            for tc in tool_calls_dicts:
                fn_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"] or "{}")
                result = self.tool_impls[fn_name](**args)
                self._append({"role": "tool", "tool_call_id": tc["id"], "content": result})

            follow_up = openai_client.chat.completions.create(
                model=CHAT_MODEL, messages=self.messages
            )
            final_msg = follow_up.choices[0].message
            self._append({"role": "assistant", "content": final_msg.content})
            reply = final_msg.content
        else:
            self._append({"role": "assistant", "content": msg.content})
            reply = msg.content

        self._compress_history_if_needed()
        return reply


# --- CLI: pick a session, resume or start new -------------------------------

def _choose_session() -> "ChatSession":
    sessions = chat_store.list_sessions()
    if sessions:
        print("Previous chats:")
        for i, s in enumerate(sessions, 1):
            print(f"  {i}. [{s['updated_at']}] {s['title'] or '(untitled)'}")
        print("  0. Start a new chat")
        choice = input("Resume which chat? (number, or Enter for new): ").strip()
        if choice and choice != "0":
            try:
                idx = int(choice) - 1
                return ChatSession(session_id=sessions[idx]["session_id"])
            except (ValueError, IndexError):
                print("Invalid choice, starting new chat.")
    return ChatSession()


if __name__ == "__main__":
    session = _choose_session()
    print(f"\nSession: {session.session_id}  (type 'exit' to quit)\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        print(f"\nAssistant: {session.ask(user_input)}\n")