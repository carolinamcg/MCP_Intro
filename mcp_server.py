from pydantic import Field
from mcp.server.fastmcp.prompts import base
from mcp.server.fastmcp import FastMCP  # MCP SDK

# Setting up MCP server
mcp = FastMCP(
    "DocumentMCP", log_level="ERROR"
)  # for tool use, but without me having to author the schema or function code. Connects to tools, GitHub,...

# TO DEBUG MY CREATED TOOLS --> python SDK comes with an inspector
# ```uv run mcp dev mcp_server.py``
# npx @modelcontextprotocol/inspector python3.14 mcp_server.py` (without uv)

docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}


# TODO: Write a prompt to rewrite a doc in markdown format
# TODO: Write a prompt to summarize a doc


# The SDK uses decorators to define tools. Instead of writing JSON schemas manually, you can use Python type hints and field descriptions. The SDK automatically generates the proper schema that Claude can understand:


# TODO: Write a tool to read a doc
@mcp.tool(  # MCP SDK syntax to build a tool automatically
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    doc_id: str = Field(description="Id of the document to read"),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    return docs[doc_id]


# TODO: Write a tool to edit a doc
@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string",
)
def edit_document(
    doc_id: str = Field(description="Id of the document that will be edited"),
    old_str: str = Field(
        description="The text to replace. Must match exactly, including whitespace"
    ),
    new_str: str = Field(description="The new text to insert in place of the old text"),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    docs[doc_id] = docs[doc_id].replace(old_str, new_str)


# RESOURCES
# Resource allows MCP Server to expose data to the Client (then you can put it imediately in the prompt without needing to call a tool and wait for the response)
# 1 resource per distinct reading task

# TODO: Write a resource to return all doc id's
# This is a static/direct resource, because the URI is fixed
@mcp.resource(
    "docs://documents",  # URI --> where the data is
    mime_type="application/json",  # the kind of data the resource will return (to hint our client about it)
)  #
def list_docs() -> list[str]:
    return list(
        docs.keys()
    )  # MCP Python SDK will automatically convert this list to JSON format because of the mime type specified in the decorator


# TODO: Write a resource to return the contents of a particular doc
# This is a templated resource, cause the URI has a variable component ({doc_id}) that will be given as an argument to the function when the resource is requested
@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")
    return docs[doc_id]

# PROMPTS
# Add prompts pre-defined by MCP server authors, tailored to the specific tasks of our server
# Well tested prompts for a specific use case (to take that burden from the user)


@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format.",
)
def format_document(
    doc_id: str = Field(description="Id of the document to format"),
) -> list[base.Message]: # returns a list of objects of type Message
    prompt = f"""
    Your goal is to reformat a document to be written with markdown syntax.

    The id of the document you need to reformat is:
    <document_id>
    {doc_id}
    </document_id>

    Add in headers, bullet points, tables, etc as necessary. Feel free to add in extra text, but don't change the meaning of the report.
    Use the 'edit_document' tool to edit the document. After the document has been edited, respond with the final version of the doc. Don't explain your changes.
    """

    return [base.UserMessage(prompt)] # outtput format: {
                                                        # messages:
                                                        # [
                                                        # 0:
                                                        # {
                                                        # role:
                                                        # "user"

                                                        # content:
                                                        # {
                                                        # type:
                                                        # "text"

                                                        # text:
                                                        # "
                                                        #     Your goal is to reformat a document to be written with markdown syntax.

                                                        #     The id of the docu..."

                                                        # }
                                                        # }
                                                        # ]
                                                        # }


if __name__ == "__main__":
    mcp.run(transport="stdio")
