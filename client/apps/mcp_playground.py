import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import datetime
import streamlit as st
from urllib.parse import urlencode
from langchain_core.messages import HumanMessage, ToolMessage
from services.ai_service import get_response_stream
from services.mcp_service import run_agent
from services.chat_service import get_current_chat, _append_message_to_session
from utils.async_helpers import run_async
from utils.ai_prompts import make_system_prompt, make_main_prompt
import ui_components.sidebar_components as sd_compents
from  ui_components.main_components import display_tool_executions
from config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
import traceback
from services.google_oauth import get_authorization_url, get_flow, fetch_token
import json


# Load your client secret JSON string from Streamlit secrets
CLIENT_SECRET_JSON = st.secrets["GOOGLE_OAUTH_CREDENTIALS"]["CLIENT_SECRET_JSON"]

# Parse JSON string to dict
CLIENT_CONFIG = json.loads(CLIENT_SECRET_JSON)

# Redirect URI must match what you set in Google Console
REDIRECT_URI = CLIENT_CONFIG["web"]["redirect_uris"][0]

def main():
    # --- Google OAuth Flow ---
    query_params = st.query_params  # safer than experimental_get_query_params
    if "credentials" not in st.session_state:
        # If returned from Google with a code, fetch token
        if "code" in query_params:
            flow = get_flow()
            query_string = urlencode(query_params, doseq=True)
            authorization_response_url = REDIRECT_URI + "?" + query_string
            credentials = fetch_token(flow, authorization_response_url)
            st.session_state["credentials"] = credentials
            st.success("✅ Connected to Google Drive!")
            st.rerun()

        else:
            st.write("### Connect your Google Drive to access files or tools")
            if st.button("Connect Google Drive"):
                auth_url, state = get_authorization_url()
                st.session_state["oauth_state"] = state  # Optionally save state
                st.markdown(f"[Click here to authorize Google Drive]({auth_url})", unsafe_allow_html=True)
                st.stop()
    else:
        st.success("✅ Google Drive Connected")
        # Optional: display token expiry or info
        # st.write(f"Access Token Expires: {st.session_state.credentials.expiry}")


    with st.sidebar:
        st.subheader("Chat History")
    sd_compents.create_history_chat_container()

# ------------------------------------------------------------------ Chat Part
    # Main chat interface
    st.header("Chat with Agent")
    messages_container = st.container(border=True, height=600)
# ------------------------------------------------------------------ Chat history
     # Re-render previous messages
    if st.session_state.get('current_chat_id'):
        st.session_state["messages"] = get_current_chat(st.session_state['current_chat_id'])
        for m in st.session_state["messages"]:
            with messages_container.chat_message(m["role"]):
                if "tool" in m and m["tool"]:
                    st.code(m["tool"], language='yaml')
                if "content" in m and m["content"]:
                    st.markdown(m["content"])

# ------------------------------------------------------------------ Chat input
    user_text = st.chat_input("Ask a question or explore available MCP tools")

# ------------------------------------------------------------------ SideBar widgets
    # Main sidebar widgets
    sd_compents.create_sidebar_chat_buttons()
    sd_compents.create_provider_select_widget()
    sd_compents.create_advanced_configuration_widget()
    sd_compents.create_mcp_connection_widget()
    sd_compents.create_mcp_tools_widget()

# ------------------------------------------------------------------ Main Logic
    if user_text is None:  # nothing submitted yet
        st.stop()

    params = st.session_state.get('params')
    if not (
        params.get('api_key') or
        (   params.get('model_id') == 'Bedrock' and
            params.get('region_name') and
            params.get('aws_access_key') and
            params.get('aws_secret_key')
        )
    ):
        err_mesg = "❌ Missing credentials: provide either an API key or complete AWS credentials."
        _append_message_to_session({"role": "assistant", "content": err_mesg})
        with messages_container.chat_message("assistant"):
            st.markdown(err_mesg)
        st.rerun()

# ------------------------------------------------------------------ handle question (if any text)
    if user_text:
        user_text_dct = {"role": "user", "content": user_text}
        _append_message_to_session(user_text_dct)
        with messages_container.chat_message("user"):
            st.markdown(user_text)

        with st.spinner("Thinking…", show_time=True):
            system_prompt = make_system_prompt()
            main_prompt = make_main_prompt(user_text)
            try:
                # If agent is available, use it
                if st.session_state.agent:
                    response = run_async(run_agent(st.session_state.agent, user_text))
                    tool_output = None
                    # Extract tool executions if available
                    if "messages" in response:
                        for msg in response["messages"]:
                            # Look for AIMessage with tool calls
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    # Find corresponding ToolMessage
                                    tool_output = next(
                                        (m.content for m in response["messages"]
                                            if isinstance(m, ToolMessage) and
                                            m.tool_call_id == tool_call['id']),
                                        None
                                    )
                                    if tool_output:
                                        st.session_state.tool_executions.append({
                                            "tool_name": tool_call['name'],
                                            "input": tool_call['args'],
                                            "output": tool_output,
                                            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        })
                    # Extract and display the response
                    output = ""
                    tool_count = 0
                    if "messages" in response:
                        for msg in response["messages"]:
                            if isinstance(msg, HumanMessage):
                                continue  # Skip human messages
                            elif hasattr(msg, 'name') and msg.name:  # ToolMessage
                                tool_count += 1
                                with messages_container.chat_message("assistant"):
                                    tool_message = f"**ToolMessage - {tool_count} ({msg.name}):** \n" + msg.content
                                    st.code(tool_message, language='yaml')
                                    _append_message_to_session({'role': 'assistant', 'tool': tool_message, })
                            else:  # AIMessage
                                if hasattr(msg, "content") and msg.content:
                                    with messages_container.chat_message("assistant"):
                                        output = str(msg.content)
                                        st.markdown(output)
                    response_dct = {"role": "assistant", "content": output}
                # Fall back to regular stream response if agent not available
                else:
                    st.warning("You are not connect to MCP servers!")
                    response_stream = get_response_stream(
                        main_prompt,
                        llm_provider=st.session_state['params']['model_id'],
                        system=system_prompt,
                        temperature=st.session_state['params'].get('temperature', DEFAULT_TEMPERATURE),
                        max_tokens=st.session_state['params'].get('max_tokens', DEFAULT_MAX_TOKENS),
                    )
                    with messages_container.chat_message("assistant"):
                        response = st.write_stream(response_stream)
                        response_dct = {"role": "assistant", "content": response}
            except Exception as e:
                response = f"⚠️ Something went wrong: {str(e)}"
                st.error(response)
                st.code(traceback.format_exc(), language="python")
                st.stop()
        # Add assistant message to chat history
        _append_message_to_session(response_dct)

    display_tool_executions()
