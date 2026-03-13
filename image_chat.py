from dotenv import load_dotenv
from PIL import Image
import os
import streamlit as st
import google.generativeai as genai

# Remove st.set_page_config since it's already set in main.py

# Load environment variables
load_dotenv()
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Initialize the model
model = genai.GenerativeModel("gemini-2.5-pro")

AI_AVATAR_ICON = "✨"


def convert_messages(messages):
    return [{"role": m["role"], "parts": m["parts"]} for m in messages]


def get_multi_file_response(input, files_data, prompt):
    # Dynamically pass all files and the prompt to the model
    return model.generate_content([input] + files_data + [prompt]).text


def input_files_setup(uploaded_files):
    """Process and set up the uploaded files for the model."""
    files_parts = []

    for uploaded_file in uploaded_files:
        if uploaded_file is not None:
            # Get file data as bytes
            bytes_data = uploaded_file.getvalue()
            # Append file's metadata and content to the list
            files_parts.append({"mime_type": uploaded_file.type, "data": bytes_data})

    return files_parts


# Streamlit UI header
st.header("Gemini Image Chat")

# Allow user to upload multiple files (images or documents)
uploaded_files = st.file_uploader(
    "Choose files", type=["jpg", "jpeg", "png"], accept_multiple_files=True
)

# If image files are uploaded, display them
if uploaded_files:
    # Create columns for better image layout
    cols = st.columns(min(len(uploaded_files), 3))

    for i, uploaded_file in enumerate(uploaded_files):
        if uploaded_file.type.startswith("image/"):
            image = Image.open(uploaded_file)
            # Use specific width instead of full column width
            with cols[i % 3]:
                st.image(image, caption=uploaded_file.name, width=300)

if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message(message["role"], avatar="user"):
            st.markdown(message.get("parts", message.get("content", "")))
    else:
        with st.chat_message(message["role"], avatar=AI_AVATAR_ICON):
            st.markdown(message.get("parts", message.get("content", "")))

# Static prompt for the Gemini model
prompt = """
You are an expert in understanding various file types and answering questions related to them.
"""

if input_prompt := st.chat_input("Input your question or prompt"):
    if not uploaded_files:
        st.error("Please upload at least one file")
    else:
        st.session_state.messages.append({"role": "user", "parts": input_prompt})
        with st.chat_message("user"):
            st.markdown(input_prompt)

        with st.chat_message("model", avatar=AI_AVATAR_ICON):
            message_placeholder = st.empty()
            full_response = ""

            # Set up file data for all uploaded files
            files_data = input_files_setup(uploaded_files)

            # Generate the response from the model
            response = model.generate_content(
                [input_prompt] + files_data + [prompt], stream=True
            )

            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")

            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "model", "parts": full_response})
