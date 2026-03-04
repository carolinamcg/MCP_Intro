from core.claude import Claude
from mcp_client import MCPClient
from core.tools import ToolManager
from anthropic.types import MessageParam

'''
Parent class of CliChat. Here is where the main loop that initializes the messages from user input (calling prompts and resources, if needed), calls Claude and tools is implemented (run function). The functions in CliChat are called inside the run function to get the info from the MCP server and include it in the prompt for Claude.
'''

class Chat:
    def __init__(self, claude_service: Claude, clients: dict[str, MCPClient]):
        self.claude_service: Claude = claude_service
        self.clients: dict[str, MCPClient] = clients
        self.messages: list[MessageParam] = []

    async def _process_query(self, query: str):
        self.messages.append({"role": "user", "content": query})

    async def run(
        self,
        query: str,
    ) -> str:
        final_text_response = ""

        await self._process_query(query) # This is the function that calls any prompt (if "/"") or resource (if "@" in user input) requested by the user first and uses their outputs to complete the prompt. This is appended to the self.messages in the right format and sent to Claude

        # Loop to send user input to Claude, execute tools if Claude requests it (connet to Client --> MCP server to execute tool and get results), send tool results back to Claude, until Claude responds with a final response that doesn't require tool use. Then return that final response.
        while True:
            response = self.claude_service.chat(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
            )

            self.claude_service.add_assistant_message(self.messages, response)

            if response.stop_reason == "tool_use":
                print(self.claude_service.text_from_message(response))
                tool_result_parts = await ToolManager.execute_tool_requests(
                    self.clients, response
                )

                self.claude_service.add_user_message( # adds tool output to messages to give to Claude in the next iteration of the loop
                    self.messages, tool_result_parts
                )
            else:
                final_text_response = self.claude_service.text_from_message(
                    response
                )
                break

        return final_text_response
