"""
Nexus AI MCP Server.
Exposes all tools to Claude Desktop,
Cursor IDE, or any MCP client.
"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
    Tool,
)

from core.logging import get_logger
from mcp.tools.file_tools import (
    read_file,
    write_file,
    list_files,
    search_codebase,
    explain_code,
)
from mcp.tools.git_tools import (
    get_status,
    create_branch,
    get_diff,
    stage_files,
    create_pr,
    get_commit_history,
    commit_changes,
)
from mcp.tools.test_tools import (
    run_tests,
    run_single_test,
    check_coverage,
    list_tests,
)
from mcp.tools.search_tools import (
    search_pattern,
    semantic_search,
    find_function,
    analyze_imports,
)

import json

logger = get_logger(__name__)
server = Server("nexus-ai")


# ─── Tool Definitions ───────────────────────────────────

@server.list_tools()
async def list_tools(
    request: ListToolsRequest
) -> ListToolsResult:
    """Register all Nexus AI tools with MCP."""
    return ListToolsResult(tools=[

        # File Tools
        Tool(
            name="read_file",
            description="Read contents of any file in the repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "Path to file relative to repo root"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file. Automatically backs up before writing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "Path to file relative to repo root"
                    },
                    "content": {
                        "type":        "string",
                        "description": "Content to write to the file"
                    },
                    "description": {
                        "type":        "string",
                        "description": "Why this file is being written"
                    }
                },
                "required": ["file_path", "content"]
            }
        ),
        Tool(
            name="list_files",
            description="List files in a directory matching a pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type":        "string",
                        "description": "Directory to list files in",
                        "default":     "."
                    },
                    "pattern": {
                        "type":        "string",
                        "description": "Glob pattern e.g. **/*.py",
                        "default":     "**/*.py"
                    }
                }
            }
        ),
        Tool(
            name="search_codebase",
            description="Search codebase for text pattern across all files",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "Text to search for"
                    },
                    "directory": {
                        "type":        "string",
                        "description": "Directory to search in",
                        "default":     "."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="explain_code",
            description="Extract specific lines from a file for analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "Path to file"
                    },
                    "start_line": {
                        "type":        "integer",
                        "description": "Start line number",
                        "default":     1
                    },
                    "end_line": {
                        "type":        "integer",
                        "description": "End line number",
                        "default":     50
                    }
                },
                "required": ["file_path"]
            }
        ),

        # Git Tools
        Tool(
            name="get_status",
            description="Get current git status including changed files and branch",
            inputSchema={
                "type":       "object",
                "properties": {}
            }
        ),
        Tool(
            name="create_branch",
            description="Create and checkout a new git branch",
            inputSchema={
                "type": "object",
                "properties": {
                    "branch_name": {
                        "type":        "string",
                        "description": "Name for new branch"
                    }
                },
                "required": ["branch_name"]
            }
        ),
        Tool(
            name="get_diff",
            description="Get current git diff showing all changes",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "Optional specific file path"
                    }
                }
            }
        ),
        Tool(
            name="create_pr",
            description="Create a GitHub Pull Request from current branch",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type":        "string",
                        "description": "PR title"
                    },
                    "description": {
                        "type":        "string",
                        "description": "PR description"
                    },
                    "base_branch": {
                        "type":        "string",
                        "description": "Base branch to merge into",
                        "default":     "main"
                    }
                },
                "required": ["title", "description"]
            }
        ),
        Tool(
            name="get_commit_history",
            description="Get recent commit history for repo or specific file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "Optional file path to filter history"
                    },
                    "limit": {
                        "type":        "integer",
                        "description": "Number of commits to return",
                        "default":     10
                    }
                }
            }
        ),

        # Test Tools
        Tool(
            name="run_tests",
            description="Run pytest test suite on the repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_path": {
                        "type":        "string",
                        "description": "Optional specific test file or directory"
                    },
                    "verbose": {
                        "type":        "boolean",
                        "description": "Show verbose output",
                        "default":     True
                    }
                }
            }
        ),
        Tool(
            name="run_single_test",
            description="Run a single test by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type":        "string",
                        "description": "Test function name to run"
                    }
                },
                "required": ["test_name"]
            }
        ),
        Tool(
            name="check_coverage",
            description="Run tests with coverage report",
            inputSchema={
                "type": "object",
                "properties": {
                    "module_path": {
                        "type":        "string",
                        "description": "Optional module to check coverage for"
                    }
                }
            }
        ),
        Tool(
            name="list_tests",
            description="List all available tests in the repository",
            inputSchema={
                "type":       "object",
                "properties": {
                    "directory": {
                        "type":        "string",
                        "description": "Test directory",
                        "default":     "tests"
                    }
                }
            }
        ),

        # Search Tools
        Tool(
            name="search_pattern",
            description="Search for exact pattern with context lines",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type":        "string",
                        "description": "Pattern to search for"
                    },
                    "directory": {
                        "type":        "string",
                        "description": "Directory to search in",
                        "default":     "."
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="semantic_search",
            description="Use AI to find semantically relevant code for a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "What you are looking for"
                    },
                    "directory": {
                        "type":        "string",
                        "description": "Directory to search in",
                        "default":     "."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_function",
            description="Find a specific function or class definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type":        "string",
                        "description": "Function or class name to find"
                    }
                },
                "required": ["function_name"]
            }
        ),
        Tool(
            name="analyze_imports",
            description="Analyze all imports in a file to understand dependencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type":        "string",
                        "description": "File to analyze imports for"
                    }
                },
                "required": ["file_path"]
            }
        ),
    ])


# ─── Tool Execution ─────────────────────────────────────

@server.call_tool()
async def call_tool(
    request: CallToolRequest
) -> CallToolResult:
    """Route tool calls to correct handler."""

    name = request.params.name
    args = request.params.arguments or {}

    logger.info("🔧 Tool called: %s", name)

    # Route to correct tool function
    tool_map = {
        # File tools
        "read_file":        lambda: read_file(**args),
        "write_file":       lambda: write_file(**args),
        "list_files":       lambda: list_files(**args),
        "search_codebase":  lambda: search_codebase(**args),
        "explain_code":     lambda: explain_code(**args),

        # Git tools
        "get_status":       lambda: get_status(),
        "create_branch":    lambda: create_branch(**args),
        "get_diff":         lambda: get_diff(**args),
        "create_pr":        lambda: create_pr(**args),
        "get_commit_history": lambda: get_commit_history(**args),
        "commit_changes":     lambda: commit_changes(**args),

        # Test tools
        "run_tests":        lambda: run_tests(**args),
        "run_single_test":  lambda: run_single_test(**args),
        "check_coverage":   lambda: check_coverage(**args),
        "list_tests":       lambda: list_tests(**args),

        # Search tools
        "search_pattern":   lambda: search_pattern(**args),
        "semantic_search":  lambda: semantic_search(**args),
        "find_function":    lambda: find_function(**args),
        "analyze_imports":  lambda: analyze_imports(**args),
    }

    if name not in tool_map:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps({
                    "error":   f"Unknown tool: {name}",
                    "success": False
                })
            )]
        )

    try:
        result = tool_map[name]()
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        )
    except Exception as exc:
        logger.error("Tool %s failed: %s", name, exc)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps({
                    "error":   str(exc),
                    "success": False
                })
            )]
        )


# ─── Run Server ─────────────────────────────────────────

async def run_mcp_server() -> None:
    """Start the MCP server via stdio."""
    logger.info("🚀 Starting Nexus AI MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nexus-ai",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                )
            )
        )