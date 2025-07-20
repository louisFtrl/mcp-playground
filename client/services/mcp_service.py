from typing import Dict, List, Optional
import streamlit as st

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from services.ai_service import create_llm_model
from utils.async_helpers import run_async


async def setup_mcp_client(server_config: Dict[str, Dict]) -> MultiServerMCPClient:
    """Initialize a MultiServerMCPClient with the provided server configuration."""
    client = MultiServerMCPClient(server_config)
    return await client.__aenter__()

async def get_tools_from_client(client: MultiServerMCPClient) -> List[BaseTool]:
    """Get tools from the MCP client."""
    return client.get_tools()

async def execute_tool_with_context(tool_func, tool_args: dict, extra_context: dict):
    if 'access_token' not in tool_args and 'access_token' in extra_context:
        tool_args['access_token'] = extra_context['access_token']
    return await tool_func.ainvoke(**tool_args)

async def run_agent(agent, message: str) -> Dict:
    """Run the agent with the provided message and optional context."""
    payload = {"messages": message}
    return await agent.ainvoke(payload)

async def run_tool(tool, **kwargs):
    """Run a tool with the provided parameters."""
    return await tool.ainvoke(**kwargs)

def connect_to_mcp_servers():
    # Clean up existing client if any
    client = st.session_state.get("client")
    if client:
        try:
            run_async(client.__aexit__(None, None, None))
        except Exception as e:
            st.warning(f"Error closing previous client: {str(e)}")


    # Collect LLM config dynamically from session state
    params = st.session_state['params']
    llm_provider = params.get("model_id")
    try:
        llm = create_llm_model(llm_provider, temperature=params['temperature'], max_tokens=params['max_tokens'])
    except Exception as e:
        st.error(f"Failed to initialize LLM: {e}")
        st.stop()
        return

    # Setup new client
    st.session_state.client = run_async(setup_mcp_client(st.session_state.servers))
    st.session_state.tools = run_async(get_tools_from_client(st.session_state.client))
    st.session_state.agent = create_react_agent(llm, st.session_state.tools)


def disconnect_from_mcp_servers():
    # Clean up existing client if any and session state connections
    client = st.session_state.get("client")
    if client:
        try:
            run_async(client.__aexit__(None, None, None))
        except Exception as e:
            st.warning(f"Error during disconnect: {str(e)}")
    else:
        st.info("No MCP connection to disconnect.")

    # Clean up session state
    st.session_state.client = None
    st.session_state.tools = []
    st.session_state.agent = None
