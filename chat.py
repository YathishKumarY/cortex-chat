import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Remove st.set_page_config since it's already set in main.py

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
st.session_state.model = genai.GenerativeModel("gemini-2.5-pro")

# Use a consistent identifier for new chats
NEW_CHAT_KEY = "NEW_CHAT_SESSION"

st.header("Gemini LLM ChatBot")

AI_AVATAR_ICON = "✨"


def generate_chat_summary(messages):
    """Generate a short summary of the conversation using Gemini."""
    if not messages or len(messages) < 2:
        return "New Chat"

    try:
        # Get the user's first question and AI's response
        conversation_text = ""

        # For early conversations (2-4 messages), use all available messages
        max_messages = min(len(messages), 4)
        for i, msg in enumerate(messages[:max_messages]):
            role = "User" if msg["role"] == "user" else "Assistant"
            # Use more content for fewer messages to get better context
            content_length = 300 if len(messages) <= 3 else 200
            conversation_text += f"{role}: {msg['content'][:content_length]}...\n"

        # Create a temporary model instance for summarization
        summary_model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )  # Use faster model for summaries

        prompt = f"""Generate a very short (3-5 words) title for this conversation:

{conversation_text}

Requirements:
- Maximum 5 words
- Descriptive and specific
- No generic phrases like "chat" or "conversation"
- Focus on the main topic or question asked
- Be specific to what the user is asking about

Example formats: "Python coding help", "Recipe recommendations", "Travel planning", "Math homework", "Image generation tips"

Title:"""

        response = summary_model.generate_content(prompt)
        summary = response.text.strip().replace('"', "").replace("'", "")

        # Ensure it's not too long
        if len(summary) > 40:
            summary = summary[:37] + "..."

        return summary if summary else "New Chat"

    except Exception as e:
        print(f"Error generating summary: {e}")
        return "New Chat"


try:
    os.mkdir("data/")
except:
    pass

try:
    past_chats: dict = joblib.load("data/past_chats_list")
except:
    past_chats = {}

with st.sidebar:
    # Initialize chat_id if not set
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = NEW_CHAT_KEY

    # Initialize confirm_delete state
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    # New Chat button with a distinct color
    if st.button("＋ New Chat", type="primary", use_container_width=True):
        st.session_state.chat_id = NEW_CHAT_KEY
        st.session_state.confirm_delete = False  # Reset any pending delete confirmation
        st.rerun()

    # Filter past_chats to include chats with saved messages OR the current active chat
    available_chats = {}
    for chat_id, title in past_chats.items():
        # Include if: 1) has saved files, OR 2) is the current active chat
        if (
            os.path.exists(f"data/{chat_id}-st_messages")
            or chat_id == st.session_state.chat_id
        ):
            available_chats[chat_id] = title

    # Sort chat IDs by timestamp (latest first) - extract timestamp from chat_id
    def get_chat_timestamp(chat_id):
        try:
            # Chat IDs are timestamps, so convert to float for sorting
            return float(chat_id)
        except:
            # If it's not a timestamp (like NEW_CHAT_KEY), put it at the end
            return 0

    sorted_chat_ids = sorted(
        available_chats.keys(), key=get_chat_timestamp, reverse=True
    )

    # Show dropdown only if there are history chats available
    if available_chats:
        st.markdown("# Chat History")

        # Determine current selection for history chats
        if st.session_state.get("chat_id") is None:
            # No current selection - don't auto-select anything
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
            )
        elif st.session_state.chat_id == NEW_CHAT_KEY:
            # Currently on new chat - show dropdown but no selection
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
            )
        elif st.session_state.chat_id in available_chats:
            # Currently on a valid existing chat - put current chat first, then sorted others
            other_chats = [
                id for id in sorted_chat_ids if id != st.session_state.chat_id
            ]
            options = [st.session_state.chat_id] + other_chats
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=options,
                index=0,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
            )
        else:
            # Current chat_id is invalid - reset to new chat
            st.session_state.chat_id = NEW_CHAT_KEY
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
            )

        # Update chat_id if a different chat was selected
        if selected_chat and selected_chat != st.session_state.get("chat_id"):
            st.session_state.chat_id = selected_chat
            st.rerun()
    else:
        st.info("📝 No chat history yet. Start a new conversation!")

    # Set chat title
    st.session_state.chat_title = available_chats.get(
        st.session_state.chat_id, "New Chat"
    )

# Check if chat_id has changed and force reload of messages
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = st.session_state.chat_id
    chat_changed = True
elif st.session_state.current_chat_id != st.session_state.chat_id:
    st.session_state.current_chat_id = st.session_state.chat_id
    chat_changed = True
else:
    chat_changed = False

# Handle message loading based on chat type
if st.session_state.chat_id == NEW_CHAT_KEY:
    # New chat - always start with empty messages
    if chat_changed:
        st.session_state.messages = []
        st.session_state.gemini_history = []
else:
    # Existing chat - load saved messages
    try:
        # Only reload messages if chat has changed or messages are empty
        if (
            chat_changed
            or not hasattr(st.session_state, "messages")
            or not st.session_state.messages
        ):
            st.session_state.messages = joblib.load(
                f"data/{st.session_state.chat_id}-st_messages"
            )
            st.session_state.gemini_history = joblib.load(
                f"data/{st.session_state.chat_id}-gemini_messages"
            )
    except:
        st.session_state.messages = []
        st.session_state.gemini_history = []

st.session_state.chat = st.session_state.model.start_chat(
    history=st.session_state.gemini_history,
)

# Show delete button in top right corner for existing chats (not new chats)
if st.session_state.chat_id != NEW_CHAT_KEY and st.session_state.chat_id in past_chats:

    # Create header with delete button
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown("")  # Empty space
    with col2:
        if st.button(
            "🗑️ Delete Chat",
            key="delete_chat_main",
            help="Delete this chat permanently",
            type="secondary",
            use_container_width=True,
        ):
            st.session_state.confirm_delete = True
            st.rerun()


# Handle delete confirmation with dialog
@st.dialog("Delete Chat Confirmation")
def delete_chat_dialog():
    st.warning(f"Are you sure you want to permanently delete the chat:")
    st.markdown(f"**'{past_chats.get(st.session_state.chat_id, 'Unknown Chat')}'**")
    st.error("⚠️ This action cannot be undone!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🗑️ Delete Permanently",
            key="dialog_confirm_yes",
            type="primary",
            use_container_width=True,
        ):
            # Delete the chat
            chat_to_delete = st.session_state.chat_id

            try:
                st_messages_file = f"data/{chat_to_delete}-st_messages"
                gemini_messages_file = f"data/{chat_to_delete}-gemini_messages"

                files_deleted = 0
                if os.path.exists(st_messages_file):
                    os.remove(st_messages_file)
                    files_deleted += 1

                if os.path.exists(gemini_messages_file):
                    os.remove(gemini_messages_file)
                    files_deleted += 1

                # Remove from past_chats
                if chat_to_delete in past_chats:
                    del past_chats[chat_to_delete]
                    joblib.dump(past_chats, "data/past_chats_list")

                # Reset to new chat
                st.session_state.chat_id = NEW_CHAT_KEY
                st.session_state.current_chat_id = NEW_CHAT_KEY
                st.session_state.messages = []
                st.session_state.gemini_history = []
                st.session_state.confirm_delete = False

                st.success(f"✅ Chat deleted successfully!")
                time.sleep(0.5)
                st.rerun()

            except Exception as e:
                st.error(f"Error deleting chat: {str(e)}")
                st.session_state.confirm_delete = False

    with col2:
        if st.button("❌ Cancel", key="dialog_confirm_no", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()


# Show dialog if delete is confirmed
if st.session_state.get("confirm_delete", False):
    delete_chat_dialog()

# Show current chat title and option to regenerate if it's "New Chat"
if (
    hasattr(st.session_state, "chat_id")
    and st.session_state.chat_id in past_chats
    and past_chats[st.session_state.chat_id] == "New Chat"
    and len(st.session_state.messages) >= 2
):

    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("💡 This chat doesn't have a title yet. Generate one?")
    with col2:
        if st.button("Generate Title", key="main_generate_title"):
            with st.spinner("Generating title..."):
                summary = generate_chat_summary(st.session_state.messages)
                if summary and summary != "New Chat":
                    past_chats[st.session_state.chat_id] = summary
                    st.session_state.chat_title = summary
                    joblib.dump(past_chats, "data/past_chats_list")
                    st.success(f"Title set to: {summary}")
                    st.rerun()

for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message(message["role"], avatar="user"):
            st.markdown(message["content"])
    else:
        with st.chat_message(message["role"], avatar=AI_AVATAR_ICON):
            st.markdown(message["content"])

prompt = st.chat_input("Message Gemini")

if prompt:
    # If this is a new chat, create a timestamp-based ID
    if st.session_state.chat_id == NEW_CHAT_KEY:
        st.session_state.chat_id = f"{time.time()}"
        st.session_state.current_chat_id = (
            st.session_state.chat_id
        )  # Update the tracking variable

    if st.session_state.chat_id not in past_chats.keys():
        # For new chats, start with a temporary title
        past_chats[st.session_state.chat_id] = "New Chat"
        joblib.dump(past_chats, "data/past_chats_list")

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append(
        dict(
            role="user",
            content=prompt,
        )
    )

    response = st.session_state.chat.send_message(
        prompt,
        stream=True,
    )

    with st.chat_message(
        name="model",
        avatar=AI_AVATAR_ICON,
    ):
        message_placeholder = st.empty()
        full_response = ""

        try:
            for chunk in response:
                for ch in chunk.text.split(" "):
                    full_response += ch + " "
                    message_placeholder.write(full_response + "▌")

        except Exception as e:
            full_response += f"\n\n*[Error: {str(e)}]*"

        message_placeholder.write(full_response)

    # Add the response to messages
    final_content = full_response
    if st.session_state.chat.history:
        # Use the complete response from chat history if available
        try:
            final_content = st.session_state.chat.history[-1].parts[0].text
        except:
            pass

    st.session_state.messages.append(
        dict(
            role="model",
            content=final_content,
            avatar=AI_AVATAR_ICON,
        )
    )

    # Update gemini history
    st.session_state.gemini_history = st.session_state.chat.history

    # Generate summary after first AI response
    if (
        len(st.session_state.messages) >= 2
        and past_chats[st.session_state.chat_id] == "New Chat"
    ):
        # Generate summary immediately after first response for new chats
        summary = generate_chat_summary(st.session_state.messages)
        past_chats[st.session_state.chat_id] = summary
        st.session_state.chat_title = summary
        joblib.dump(past_chats, "data/past_chats_list")

    # Save the messages and history files immediately
    joblib.dump(
        st.session_state.messages,
        f"data/{st.session_state.chat_id}-st_messages",
    )

    joblib.dump(
        st.session_state.gemini_history,
        f"data/{st.session_state.chat_id}-gemini_messages",
    )

    # Force a rerun to update the sidebar with the new chat
    st.rerun()
