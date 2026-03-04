import sys
import asyncio
from typing import Optional, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, types
# ClientSession docs --> https://py.sdk.modelcontextprotocol.io/api/
from mcp.client.stdio import stdio_client

import json
from pydantic import AnyUrl



class MCPClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
    ):
        '''
        Custom class we are authoring to make using the session easier.
        It takes care of the clean up (e.g: resources) when we close the program or session.
        '''
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None # actual connection to the MCP server. It's a part of the MCP Python SDK
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        # starts an MCP server process via stdio and creates a client session.
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _stdio, _write = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_stdio, _write)
        )
        await self._session.initialize()

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized or cache not populated. Call connect_to_server first."
            )
        return self._session

    # Function to list availabel tools in MCP server to then pass the results to claude
    async def list_tools(self) -> list[types.Tool]:
        result = await self.session().list_tools() # self.session() --> connecting to the MCP server
        return result.tools

    # Function to call a tool that is implemented by the MCP server to then pass the result to claude
    async def call_tool(
        self, tool_name: str, tool_input
    ) -> types.CallToolResult | None:
        return await self.session().call_tool(tool_name, tool_input)

    # TODO: Return a list of prompts defined by the MCP server
    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.session().list_prompts()
        return result.prompts

    # TODO: Get a particular prompt defined by the MCP server
    async def get_prompt(self, prompt_name, args: dict[str, str]):
        result = await self.session().get_prompt(prompt_name, args)
        return result.messages

    # TODO: Read a resource, parse the contents and return it
    async def read_resource(self, uri: str) -> Any:
        result = await self.session().read_resource(AnyUrl(uri)) # Send a resources/read request.
        resource = result.contents[0]
        # output of a resource is a dict with {"contents": [ 0: {"uri": uri, "mimeType": "text/plain", "text": "the actual content of the resource"} ]}

        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json": # for the list_docs resource
                return json.loads(resource.text)

            return resource.text # for the fetch_doc resource
        
    async def cleanup(self):
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# For testing
async def main():
    async with MCPClient(
        # If using Python without UV, update command to 'python' and remove "run" from args.
        # command="uv",
        # args=["run", "mcp_server.py"],
        command="python",
        args=["mcp_server.py"], # our MCP server file to create the session to connnect to it
    ) as _client: # starts up a copy of our MCP server
        
        # await pauses the main() coroutine until the asynchronous list_tools() call completes, yielding control back to the event loop so other tasks can run concurrently

        result = await _client.list_tools() # get a list of all the tools that are defined by it
        print(result)
        #pass


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
