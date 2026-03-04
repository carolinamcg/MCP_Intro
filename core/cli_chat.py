from typing import List, Tuple
from mcp.types import Prompt, PromptMessage
from anthropic.types import MessageParam

from core.chat import Chat # Parent class that CliChat inherits from
from core.claude import Claude
from mcp_client import MCPClient

'''
CliChat extends the Chat class (the latter is where the run function is, with the loop that calls claude and tools)
CliChat is the interface between the MCP Client and Claude. Here, is where we call the read_resource() from the Client so then the CliChat can include this new info in the prompt for Claude.
'''

class CliChat(Chat):
    def __init__(
        self,
        doc_client: MCPClient,
        clients: dict[str, MCPClient],
        claude_service: Claude,
    ):
        super().__init__(clients=clients, claude_service=claude_service)

        self.doc_client: MCPClient = doc_client

    async def list_prompts(self) -> list[Prompt]:
        return await self.doc_client.list_prompts()

    # Function in our code that requests the client to read the static resource (fixed URI) from MCP sever
    async def list_docs_ids(self) -> list[str]:
        return await self.doc_client.read_resource("docs://documents")
    
    # Function in our code that requests the client to read the template resource from MCP sever
    async def get_doc_content(self, doc_id: str) -> str:
        return await self.doc_client.read_resource(f"docs://documents/{doc_id}")

    async def get_prompt(
        self, command: str, doc_id: str
    ) -> list[PromptMessage]:
        return await self.doc_client.get_prompt(command, {"doc_id": doc_id})

    async def _extract_resources(self, query: str) -> str:
        mentions = [word[1:] for word in query.split() if word.startswith("@")]

        doc_ids = await self.list_docs_ids() # calls our Client to run static resource
        mentioned_docs: list[Tuple[str, str]] = []

        for doc_id in doc_ids:
            if doc_id in mentions:
                content = await self.get_doc_content(doc_id) # calls our Client to run template resource
                mentioned_docs.append((doc_id, content))

        return "".join(
            f'\n<document id="{doc_id}">\n{content}\n</document>\n' # <document> markers for AI model to perform better
            for doc_id, content in mentioned_docs
        )

    # Parse user input when is calling a command/prompt name, e.g., "/format"
    async def _process_command(self, query: str) -> bool:
        if not query.startswith("/"):
            return False

        words = query.split()
        command = words[0].replace("/", "") # prompt name

        messages = await self.doc_client.get_prompt( # runs this function in the MCP Client to get the prompt from MCP server
            command, {"doc_id": words[1]} # dict with the arg name matching the MCP server prompt arg and the actual arg value
        )

        self.messages += convert_prompt_messages_to_message_params(messages)
        return True

    # Function that takes the selected doc_id from the user input (word after @), uses is to extract the docs' text throught the template resourse and then adds that text to the prompt that will be sent to Claude
    async def _process_query(self, query: str):
        if await self._process_command(query):
            return

        added_resources = await self._extract_resources(query) # get the text from the doc:id in the user query and format it to be added to the prompt

        prompt = f"""
        The user has a question:
        <query>
        {query}
        </query>

        The following context may be useful in answering their question:
        <context>
        {added_resources}
        </context>

        Note the user's query might contain references to documents like "@report.docx". The "@" is only
        included as a way of mentioning the doc. The actual name of the document would be "report.docx".
        If the document content is included in this prompt, you don't need to use an additional tool to read the document.
        Answer the user's question directly and concisely. Start with the exact information they need. 
        Don't refer to or mention the provided context in any way - just use it to inform your answer.
        """

        self.messages.append({"role": "user", "content": prompt})


# Converts MCP server prompt's message (dict with a list, each item with "role" and "content" fields, where content is a dict with "type" and "text" fields) to the MessageParam format that our Claude service expects
def convert_prompt_message_to_message_param(
    prompt_message: "PromptMessage",
) -> MessageParam:
    role = "user" if prompt_message.role == "user" else "assistant"

    content = prompt_message.content

    # Check if content is a dict-like object with a "type" field
    if isinstance(content, dict) or hasattr(content, "__dict__"):
        content_type = (
            content.get("type", None)
            if isinstance(content, dict)
            else getattr(content, "type", None)
        )
        if content_type == "text":
            content_text = (
                content.get("text", "")
                if isinstance(content, dict)
                else getattr(content, "text", "")
            )
            return {"role": role, "content": content_text}

    if isinstance(content, list):
        text_blocks = []
        for item in content:
            # Check if item is a dict-like object with a "type" field
            if isinstance(item, dict) or hasattr(item, "__dict__"):
                item_type = (
                    item.get("type", None)
                    if isinstance(item, dict)
                    else getattr(item, "type", None)
                )
                if item_type == "text":
                    item_text = (
                        item.get("text", "")
                        if isinstance(item, dict)
                        else getattr(item, "text", "")
                    )
                    text_blocks.append({"type": "text", "text": item_text})

        if text_blocks:
            return {"role": role, "content": text_blocks}

    return {"role": role, "content": ""}


def convert_prompt_messages_to_message_params(
    prompt_messages: List[PromptMessage],
) -> List[MessageParam]:
    return [
        convert_prompt_message_to_message_param(msg) for msg in prompt_messages
    ]
