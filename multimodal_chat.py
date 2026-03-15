"""
Gemini Multimodal Chat Application with Backend Integration

This application provides a full-featured multimodal chat interface with:
- Text, image, and PDF analysis
- Real-time web search and URL analysis
- Image generation and editing
- PostgreSQL backend integration for persistence
- Local storage fallback when backend is unavailable

Backend Features:
- User authentication and session management
- Conversation persistence in PostgreSQL
- Image storage and retrieval
- Chat history across sessions
- Automatic fallback to local storage

The app automatically detects backend availability and seamlessly
switches between PostgreSQL (when available) and local file storage.
"""

import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from google import genai as google_genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
from PyPDF2 import PdfReader
import PyPDF2
from io import BytesIO
import re
import random as rd
import urllib.parse
import requests
import base64
from api_client import get_api_client, get_conversation_summary

load_dotenv()

# Remove st.set_page_config since it's already set in main.py

# Configure Gemini API
try:
    # Try to get API key from Streamlit secrets first
    api_key = st.secrets.get("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        st.session_state.model = genai.GenerativeModel("gemini-2.5-flash")
        # Initialize image generation client
        image_gen_client = google_genai.Client(api_key=api_key)
        image_gen_available = True
        search_available = True
        print(
            "✅ Gemini API and image generation client initialized with Streamlit secrets"
        )
    else:
        raise ValueError("No API key in Streamlit secrets")
except Exception as e1:
    print(f"Failed to initialize with Streamlit secrets: {e1}")
    try:
        # Fallback to environment variable
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            st.session_state.model = genai.GenerativeModel("gemini-2.5-flash")
            # Initialize image generation client
            image_gen_client = google_genai.Client(api_key=api_key)
            image_gen_available = True
            search_available = True
            print(
                "✅ Gemini API and image generation client initialized with environment variable"
            )
        else:
            raise ValueError("No API key in environment")
    except Exception as e2:
        print(f"Failed to initialize with environment variable: {e2}")
        image_gen_client = None
        image_gen_available = False
        search_available = False
        st.error(
            "🔴 Gemini API unavailable - please set GEMINI_API_KEY in secrets.toml or environment"
        )
        st.info(
            "💡 Add your API key to .streamlit/secrets.toml: GEMINI_API_KEY = 'your-key-here'"
        )

# Use a consistent identifier for new chats
NEW_CHAT_KEY = "NEW_MULTIMODAL_CHAT_SESSION"


# Backend integration setup
def get_backend_client():
    """Get API client with JWT token from session."""
    return get_api_client()


def initialize_backend_session():
    """Initialize backend session with user authentication"""
    try:
        api_client = get_backend_client()

        # Set JWT token from session state (set by main.py login)
        token = st.session_state.get("jwt_token")
        if token:
            api_client.set_token(token)

        # Check if backend is available
        if api_client.health_check():
            st.session_state.backend_available = True
            # Use authenticated user_id from session state (set by main.py login)
            user_id = st.session_state.get("user_id")
            if user_id:
                st.session_state.backend_user_id = user_id
            return True
        else:
            st.session_state.backend_available = False
            st.warning("🔴 Backend unavailable - using local storage only")
            return False
    except Exception as e:
        st.session_state.backend_available = False
        st.warning(f"🔴 Backend connection failed: {str(e)} - using local storage only")
        return False


def save_message_to_backend(
    user_id: str, conversation_id: str, role: str, content: str, metadata: dict = None
):
    """Send chat message to backend (which handles both user and AI response)"""
    if not st.session_state.get("backend_available", False):
        return False

    try:
        api_client = get_backend_client()

        # Only send user messages to backend - let backend generate AI responses
        if role == "user":
            result = api_client.send_chat_message(user_id, content, conversation_id)
            return result is not None and "message" in result
        else:
            # For assistant messages, we already got them from the backend
            return True
    except Exception as e:
        st.error(f"Failed to send message to backend: {e}")
        return False


def save_image_to_backend(
    user_id: str, conversation_id: str, image_data: bytes, filename: str
):
    """Save generated/edited image to backend storage"""
    if not st.session_state.get("backend_available", False):
        return None

    try:
        api_client = get_backend_client()
        result = api_client.upload_file(user_id, image_data, filename, conversation_id)
        return result.get("file_url") if result else None
    except Exception as e:
        st.error(f"Failed to save image to backend: {e}")
        return None


def create_backend_conversation(user_id: str, title: str):
    """Create a new conversation in the backend"""
    if not st.session_state.get("backend_available", False):
        return None

    try:
        api_client = get_backend_client()
        result = api_client.create_conversation(user_id, title)
        return result.get("conversation_id") if result else None
    except Exception as e:
        st.error(f"Failed to create conversation in backend: {e}")
        return None


def load_conversations_from_backend(user_id: str):
    """Load user conversations from backend"""
    if not st.session_state.get("backend_available", False):
        return []

    try:
        api_client = get_backend_client()
        conversations = api_client.get_user_conversations(user_id)
        return conversations
    except Exception as e:
        st.error(f"Failed to load conversations from backend: {e}")
        return []


def load_messages_from_backend(conversation_id: str):
    """Load conversation messages from backend"""
    if not st.session_state.get("backend_available", False):
        return []

    try:
        api_client = get_backend_client()
        messages = api_client.get_conversation_messages(conversation_id)
        return messages
    except Exception as e:
        st.error(f"Failed to load messages from backend: {e}")
        return []


# Initialize backend session
initialize_backend_session()

st.header("🤖 Gemini Multimodal ChatBot")
st.markdown("*Chat with text, images, and PDFs all in one place*")

# Show backend status
if st.session_state.get("backend_available", False):
    st.success("🟢 Backend connected - PostgreSQL persistence enabled")
else:
    st.info("🔵 Using local storage - backend unavailable")

# Show image generation status
if image_gen_client:
    st.success("🟢 Image generation enabled")
else:
    st.error("🔴 Image generation disabled - check API key configuration")

AI_AVATAR_ICON = "✨"


def generate_chat_summary(messages):
    """Generate a short summary of the conversation using Gemini."""
    if not messages or len(messages) < 2:
        return "New Chat"

    try:
        # Get the first user message to check if it's meaningful
        first_user_msg = ""
        for msg in messages:
            if msg["role"] == "user":
                first_user_msg = msg["content"].strip().lower()
                break

        # If the user just sent a greeting, use it directly instead of wasting an API call
        greetings = ["hi", "hello", "hey", "hii", "hiii", "sup", "yo", "hola", "howdy", "greetings"]
        if first_user_msg in greetings:
            return "New Chat"

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

        prompt = f"""Generate a very short (3-5 words) title for this conversation. The title should describe what the user is asking about.

{conversation_text}

Rules:
- Maximum 5 words
- Be SPECIFIC to the user's actual question or topic
- NEVER use generic titles like "Any topic assistance", "General help", "Chat assistance", "Greeting exchange"
- If the user asked about Python, say "Python ..."
- If the user asked about food, say "Food ..."
- Focus ONLY on the user's message, ignore the assistant's greeting

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


def generate_image_from_text(prompt):
    """Generate a high-quality image from a text prompt using Gemini."""
    if not image_gen_client:
        return (
            "Image generation is not available. Please check your API configuration.",
            [],
        )

    try:
        response = image_gen_client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        text_response = ""
        generated_images = []

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text
            elif part.inline_data is not None:
                try:
                    # Try simple approach first
                    image = Image.open(BytesIO(part.inline_data.data))
                    generated_images.append(image)
                except:
                    # Fallback to base64 decoding
                    import base64

                    image_data = base64.b64decode(part.inline_data.data)
                    image = Image.open(BytesIO(image_data))
                    generated_images.append(image)

        return text_response, generated_images

    except Exception as e:
        return f"Error generating image: {str(e)}", []


def edit_image_with_prompt(image, prompt):
    """Edit an uploaded image based on a text prompt using Gemini."""
    try:
        # For now, provide a description of what the edit would look like
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Convert image to base64 for analysis
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_byte_arr = img_byte_arr.getvalue()

        # Create a descriptive response about what the edited image would look like
        response = model.generate_content(
            [
                f"Describe how this image would look after this edit: {prompt}. "
                f"Be specific about what changes would be made to the colors, composition, "
                f"objects, lighting, and overall appearance.",
                image,
            ]
        )

        text_response = response.text
        edited_images = []  # No actual edited images for now

        return text_response, edited_images

    except Exception as e:
        return f"Error editing image: {str(e)}", []


def detect_image_generation_request(prompt):
    """Use AI to intelligently detect if the user wants image generation."""
    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.5-flash")

        detection_prompt = f"""
        Analyze this user prompt and determine if they want an IMAGE/VISUAL to be GENERATED/CREATED, or if they want TEXT information/conversation.

        User prompt: "{prompt}"

        Rules:
        - If they want ANY visual content created/generated/made (art, picture, image, character, scene, landscape, etc.), respond: IMAGE
        - If they want text information, explanations, conversations, analysis, etc., respond: TEXT
        - When in doubt about visual creation requests, lean towards IMAGE

        Examples:
        - "Generate a fantasy landscape with dragons and castles" → IMAGE
        - "Create an abstract art piece inspired by music" → IMAGE
        - "make a zenitsu image" → IMAGE
        - "create naruto artwork" → IMAGE  
        - "draw a sunset" → IMAGE
        - "generate a cyberpunk city" → IMAGE
        - "what is zenitsu's power?" → TEXT
        - "explain naruto's story" → TEXT
        - "tell me about anime" → TEXT

        Respond with only one word: IMAGE or TEXT
        """

        response = detection_model.generate_content(detection_prompt)
        result = response.text.strip().upper()

        # Debug logging
        print(f"Image detection for '{prompt}': {result}")

        return result == "IMAGE"

    except Exception as e:
        print(f"Image detection error: {e}")
        # Fallback: if AI detection fails, look for basic visual keywords
        visual_keywords = [
            "image",
            "picture",
            "draw",
            "create",
            "make",
            "generate",
            "art",
            "visual",
            "landscape",
            "fantasy",
            "portrait",
            "scene",
            "design",
            "illustration",
        ]
        detected = any(keyword in prompt.lower() for keyword in visual_keywords)
        print(f"Fallback detection for '{prompt}': {detected}")
        return detected


def detect_image_editing_request(prompt, has_uploaded_images):
    """Use AI to intelligently detect if the user wants to edit an uploaded image."""
    if not has_uploaded_images:
        return False

    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.5-flash")

        detection_prompt = f"""
        The user has uploaded an image and made this request. Determine if they want to EDIT/MODIFY the uploaded image, or just ANALYZE/DISCUSS it.

        User prompt: "{prompt}"

        Rules:
        - If they want to modify, edit, change, transform, or alter the uploaded image, respond: EDIT
        - If they want to analyze, describe, ask questions about, or discuss the image, respond: ANALYZE
        - Image editing keywords: edit, change, modify, transform, alter, remove, add, replace, make it, turn it into, convert to

        Examples:
        - "edit this image to make it darker" → EDIT
        - "change the background to blue" → EDIT
        - "remove the person from this image" → EDIT
        - "make this image look like anime style" → EDIT
        - "what do you see in this image?" → ANALYZE
        - "describe this picture" → ANALYZE
        - "who is in this photo?" → ANALYZE

        Respond with only one word: EDIT or ANALYZE
        """

        response = detection_model.generate_content(detection_prompt)
        result = response.text.strip().upper()

        return result == "EDIT"

    except Exception as e:
        # Fallback: if AI detection fails, look for basic editing keywords
        edit_keywords = [
            "edit",
            "change",
            "modify",
            "transform",
            "alter",
            "remove",
            "add",
            "replace",
            "make it",
            "turn it into",
            "convert",
        ]
        return any(keyword in prompt.lower() for keyword in edit_keywords)

        response = detection_model.generate_content(detection_prompt)
        result = response.text.strip().upper()

        return result == "IMAGE"

    except Exception as e:
        # Fallback: if AI detection fails, look for basic visual keywords
        visual_keywords = [
            "image",
            "picture",
            "draw",
            "create",
            "make",
            "generate",
            "art",
            "visual",
        ]
        return any(keyword in prompt.lower() for keyword in visual_keywords)


def extract_text_from_pdf(uploaded_file):
    """Extract text from uploaded PDF file."""
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def extract_text_from_txt(uploaded_file):
    """Extract text from uploaded TXT file."""
    return uploaded_file.getvalue().decode("utf-8")


def process_uploaded_files(uploaded_files):
    """Process and prepare uploaded files for the model."""
    files_data = []
    file_info = []

    for uploaded_file in uploaded_files:
        if uploaded_file.type.startswith("image/"):
            # Handle image files - convert to PIL Image
            image = Image.open(uploaded_file)
            files_data.append(image)
            file_info.append(f"📷 Image: {uploaded_file.name}")

        elif uploaded_file.type == "application/pdf":
            # Handle PDF files
            text = extract_text_from_pdf(uploaded_file)
            files_data.append(text)
            file_info.append(f"📄 PDF: {uploaded_file.name}")

        elif uploaded_file.type == "text/plain":
            # Handle text files
            text = extract_text_from_txt(uploaded_file)
            files_data.append(text)
            file_info.append(f"📝 Text: {uploaded_file.name}")

    return files_data, file_info


def detect_search_need(prompt):
    """Use AI to intelligently detect if the user's query would benefit from web search."""
    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.5-flash")

        detection_prompt = f"""
        Analyze this user prompt and determine if it would benefit from real-time web search to provide accurate, current information.

        User prompt: "{prompt}"

        Search is needed for:
        - Current events, recent news, latest developments
        - Real-time data (stock prices, weather, sports scores)
        - Recent releases, updates, or announcements
        - Questions about "latest", "recent", "current", "today", "this year"
        - Factual questions that may have changed since knowledge cutoff
        - Questions about specific people, companies, or events that need current info

        Search is NOT needed for:
        - General knowledge, definitions, explanations
        - Creative writing, storytelling, poems
        - Personal advice, opinions, hypotheticals
        - Math, coding, technical explanations
        - Image generation or editing requests
        - Analysis of uploaded files/documents

        Examples:
        - "What's the latest news about AI?" → SEARCH
        - "Who won the 2024 election?" → SEARCH  
        - "Current stock price of Apple" → SEARCH
        - "Explain how photosynthesis works" → NO_SEARCH
        - "Write a story about dragons" → NO_SEARCH

        Respond with only: SEARCH or NO_SEARCH
        """

        response = detection_model.generate_content(detection_prompt)
        result = response.text.strip().upper()

        return result == "SEARCH"

    except Exception as e:
        # Fallback: look for search-indicating keywords
        search_keywords = [
            "latest",
            "recent",
            "current",
            "today",
            "news",
            "update",
            "what happened",
            "breaking",
            "this year",
            "2024",
            "2025",
            "stock price",
            "weather",
            "score",
            "winner",
            "election",
        ]
        return any(keyword in prompt.lower() for keyword in search_keywords)


def detect_urls_in_prompt(prompt):
    """Extract and validate URLs from the user's prompt."""
    # Regex pattern to match URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'

    # Find all URLs in the prompt
    urls = re.findall(url_pattern, prompt)

    # Clean and validate URLs
    cleaned_urls = []
    for url in urls:
        # Remove trailing punctuation
        url = re.sub(r"[.,;:!?]+$", "", url)

        # Add https:// if missing
        if url.startswith("www."):
            url = "https://" + url

        # Basic validation
        if is_valid_url(url):
            cleaned_urls.append(url)

    return cleaned_urls


def is_valid_url(url):
    """Basic URL validation."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def detect_url_context_need(prompt, urls):
    """Use AI to intelligently detect if the user wants URL content analysis."""
    if not urls:
        return False

    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.5-flash")

        detection_prompt = f"""
        The user has provided URLs and made this request. Determine if they want to ANALYZE the content from the URLs or just need general information.

        User prompt: "{prompt}"
        URLs provided: {urls}

        URL context is needed for:
        - Analyzing, summarizing, or extracting information from specific URLs
        - Comparing content across multiple URLs
        - Questions about the content of specific pages
        - Tasks that require reading the actual content of the URLs

        URL context is NOT needed for:
        - General questions unrelated to the URLs
        - When URLs are just mentioned as examples
        - When user wants current/general information about topics

        Examples:
        - "Summarize this article: https://example.com/article" → URL_CONTEXT
        - "Compare these two products: url1 and url2" → URL_CONTEXT
        - "What does this page say about X: url" → URL_CONTEXT
        - "I found this link https://example.com but tell me about AI" → NO_URL_CONTEXT

        Respond with only: URL_CONTEXT or NO_URL_CONTEXT
        """

        response = detection_model.generate_content(detection_prompt)
        result = response.text.strip().upper()

        return result == "URL_CONTEXT"

    except Exception as e:
        # Fallback: if URLs are present and user uses analysis keywords, assume URL context needed
        analysis_keywords = [
            "summarize",
            "analyze",
            "extract",
            "compare",
            "what does",
            "read",
            "content",
            "information from",
            "details from",
            "explain this",
        ]
        return any(keyword in prompt.lower() for keyword in analysis_keywords)


def generate_with_url_context(prompt, urls, model_name="gemini-2.5-flash"):
    """Generate a response using URL content analysis."""
    if not search_available or not urls:
        return None, None

    try:
        # Use standard Gemini model for analysis
        model = genai.GenerativeModel(model_name)

        # Fetch content from URLs manually
        url_contents = []
        for url in urls:
            try:
                response = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    # Get first 3000 characters of content
                    content = response.text[:3000]
                    url_contents.append(f"Content from {url}:\n{content}\n")
            except Exception as e:
                url_contents.append(f"Could not fetch content from {url}: {str(e)}\n")

        # Combine URL content with user prompt
        enhanced_prompt = f"""
        Based on the following web content, please answer the user's question:
        
        {' '.join(url_contents)}
        
        User question: {prompt}
        """

        # Generate response
        response = model.generate_content(enhanced_prompt)

        return response, (
            response.candidates[0].url_context_metadata if response.candidates else None
        )

    except Exception as e:
        print(f"Error with URL context generation: {e}")
        return None, None


def generate_with_search_and_url_context(
    prompt, urls=None, model_name="gemini-2.5-flash"
):
    """Generate a response using web search and URL context analysis."""
    if not search_available:
        return None, None, None

    try:
        # Initialize the search client
        search_client = google_genai.Client(api_key=api_key)

        # Define the grounding tool using the correct format
        grounding_tool = types.Tool(google_search=types.GoogleSearch())

        # Configure generation settings
        config = types.GenerateContentConfig(tools=[grounding_tool])

        # Fetch URL content if provided
        url_content = ""
        if urls:
            for url in urls:
                try:
                    response = requests.get(
                        url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if response.status_code == 200:
                        content = response.text[:2000]
                        url_content += f"Content from {url}:\n{content}\n\n"
                except:
                    url_content += f"Could not fetch content from {url}\n"

        # Create enhanced prompt with URL context
        if url_content:
            enhanced_prompt = f"""
            Based on the following web content, please answer the user's question:
            
            {url_content}
            
            Question: {prompt}
            """
        else:
            enhanced_prompt = prompt

        # Make the request using the google_genai client
        response = search_client.models.generate_content(
            model=model_name,
            contents=enhanced_prompt,
            config=config,
        )

        grounding_metadata = (
            response.candidates[0].grounding_metadata if response.candidates else None
        )
        url_context_metadata = (
            response.candidates[0].url_context_metadata if response.candidates else None
        )

        return response, grounding_metadata, url_context_metadata

    except Exception as e:
        print(f"Error with search and URL context generation: {e}")
        # Fallback to regular generation without search
        try:
            model = genai.GenerativeModel(model_name)
            if url_content:
                enhanced_prompt = (
                    f"Based on this content: {url_content}\n\nQuestion: {prompt}"
                )
            else:
                enhanced_prompt = prompt
            response = model.generate_content(enhanced_prompt)
            return response, None, None
        except:
            return None, None, None


def display_url_context_sources(url_context_metadata):
    """Display URL context sources in a nice format."""
    if not url_context_metadata:
        return

    try:
        if (
            hasattr(url_context_metadata, "url_metadata")
            and url_context_metadata.url_metadata
        ):
            st.markdown("**🔗 URLs Analyzed:**")
            for i, url_info in enumerate(url_context_metadata.url_metadata, 1):
                retrieved_url = url_info.retrieved_url
                status = url_info.url_retrieval_status

                # Show status with appropriate icon
                if "SUCCESS" in str(status):
                    status_icon = "✅"
                    status_text = "Successfully retrieved"
                else:
                    status_icon = "❌"
                    status_text = f"Failed: {status}"

                st.markdown(
                    f"{i}. {status_icon} [{retrieved_url}]({retrieved_url}) - {status_text}"
                )

    except Exception as e:
        print(f"Error displaying URL context sources: {e}")


def serialize_url_context_metadata(url_context_metadata):
    """Convert URL context metadata to a serializable format."""
    if not url_context_metadata:
        return None

    try:
        serialized = {}

        # Extract URL metadata
        if (
            hasattr(url_context_metadata, "url_metadata")
            and url_context_metadata.url_metadata
        ):
            url_data = []
            for url_info in url_context_metadata.url_metadata:
                url_data.append(
                    {
                        "retrieved_url": url_info.retrieved_url,
                        "url_retrieval_status": str(url_info.url_retrieval_status),
                    }
                )
            serialized["url_metadata"] = url_data

        return serialized if serialized else None
    except Exception as e:
        print(f"Error serializing URL context metadata: {e}")
        return None


def display_serialized_url_context_sources(serialized_metadata):
    """Display URL context sources from serialized metadata."""
    if not serialized_metadata:
        return

    try:
        if "url_metadata" in serialized_metadata:
            st.markdown("**🔗 URLs Analyzed:**")
            for i, url_data in enumerate(serialized_metadata["url_metadata"], 1):
                retrieved_url = url_data["retrieved_url"]
                status = url_data["url_retrieval_status"]

                # Show status with appropriate icon
                if "SUCCESS" in status:
                    status_icon = "✅"
                    status_text = "Successfully retrieved"
                else:
                    status_icon = "❌"
                    status_text = f"Failed: {status}"

                st.markdown(
                    f"{i}. {status_icon} [{retrieved_url}]({retrieved_url}) - {status_text}"
                )

    except Exception as e:
        print(f"Error displaying serialized URL context sources: {e}")


def add_citations_to_text(text, grounding_metadata):
    """Add inline citations to the response text using grounding metadata."""
    if not grounding_metadata or not hasattr(grounding_metadata, "grounding_supports"):
        return text

    try:
        supports = grounding_metadata.grounding_supports
        chunks = grounding_metadata.grounding_chunks

        if not supports or not chunks:
            return text

        # Sort supports by end_index in descending order to avoid shifting issues when inserting
        sorted_supports = sorted(
            supports, key=lambda s: s.segment.end_index, reverse=True
        )

        for support in sorted_supports:
            end_index = support.segment.end_index
            if support.grounding_chunk_indices:
                # Create citation string like [1][2]
                citation_links = []
                for i in support.grounding_chunk_indices:
                    if i < len(chunks):
                        citation_links.append(f"[{i + 1}]")

                citation_string = "".join(citation_links)
                text = text[:end_index] + citation_string + text[end_index:]

        return text
    except Exception as e:
        print(f"Error adding citations: {e}")
        return text


def display_search_sources(grounding_metadata):
    """Display search sources and queries in a nice format."""
    if not grounding_metadata:
        return

    try:
        # Display search queries used
        if (
            hasattr(grounding_metadata, "web_search_queries")
            and grounding_metadata.web_search_queries
        ):
            st.markdown("**🔍 Search Queries Used:**")
            for i, query in enumerate(grounding_metadata.web_search_queries, 1):
                st.markdown(f"{i}. `{query}`")

        # Display sources
        if (
            hasattr(grounding_metadata, "grounding_chunks")
            and grounding_metadata.grounding_chunks
        ):
            st.markdown("**📚 Sources:**")
            for i, chunk in enumerate(grounding_metadata.grounding_chunks, 1):
                if hasattr(chunk, "web") and chunk.web:
                    title = (
                        chunk.web.title
                        if hasattr(chunk.web, "title")
                        else "Unknown Source"
                    )
                    uri = chunk.web.uri if hasattr(chunk.web, "uri") else "#"
                    st.markdown(f"[{i}] [{title}]({uri})")

    except Exception as e:
        print(f"Error displaying search sources: {e}")


def serialize_grounding_metadata(grounding_metadata):
    """Convert grounding metadata to a serializable format."""
    if not grounding_metadata:
        return None

    try:
        serialized = {}

        # Extract search queries
        if (
            hasattr(grounding_metadata, "web_search_queries")
            and grounding_metadata.web_search_queries
        ):
            serialized["web_search_queries"] = list(
                grounding_metadata.web_search_queries
            )

        # Extract grounding chunks (sources)
        if (
            hasattr(grounding_metadata, "grounding_chunks")
            and grounding_metadata.grounding_chunks
        ):
            chunks = []
            for chunk in grounding_metadata.grounding_chunks:
                if hasattr(chunk, "web") and chunk.web:
                    chunk_data = {
                        "title": (
                            chunk.web.title
                            if hasattr(chunk.web, "title")
                            else "Unknown Source"
                        ),
                        "uri": chunk.web.uri if hasattr(chunk.web, "uri") else "#",
                    }
                    chunks.append(chunk_data)
            serialized["grounding_chunks"] = chunks

        return serialized if serialized else None
    except Exception as e:
        print(f"Error serializing grounding metadata: {e}")
        return None


def display_serialized_search_sources(serialized_metadata):
    """Display search sources from serialized metadata."""
    if not serialized_metadata:
        return

    try:
        # Display search queries used
        if "web_search_queries" in serialized_metadata:
            st.markdown("**🔍 Search Queries Used:**")
            for i, query in enumerate(serialized_metadata["web_search_queries"], 1):
                st.markdown(f"{i}. `{query}`")

        # Display sources
        if "grounding_chunks" in serialized_metadata:
            st.markdown("**📚 Sources:**")
            for i, chunk in enumerate(serialized_metadata["grounding_chunks"], 1):
                title = chunk.get("title", "Unknown Source")
                uri = chunk.get("uri", "#")
                st.markdown(f"[{i}] [{title}]({uri})")

    except Exception as e:
        print(f"Error displaying serialized search sources: {e}")


def generate_with_search(prompt, model_content=None, model_name="gemini-2.5-flash"):
    """Generate a response using Google Search grounding."""
    if not search_available:
        return None, None

    try:
        # Initialize the search client
        search_client = google_genai.Client(api_key=api_key)

        # Define the grounding tool using the correct format
        grounding_tool = types.Tool(google_search=types.GoogleSearch())

        # Configure generation settings
        config = types.GenerateContentConfig(tools=[grounding_tool])

        # Use model_content if provided, otherwise just the prompt
        content_to_send = model_content if model_content else prompt

        # Make the request using the google_genai client
        response = search_client.models.generate_content(
            model=model_name,
            contents=content_to_send,
            config=config,
        )

        return response, (
            response.candidates[0].grounding_metadata if response.candidates else None
        )

    except Exception as e:
        print(f"Error with search generation: {e}")
        # Fallback to regular generation without search
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response, None
        except:
            return None, None


# Curated high-quality suggestion categories for multimodal chat
SUGGESTION_CATEGORIES = {
    "image_generation": [
        "Generate a cyberpunk cityscape with neon lights at night",
        "Create a minimalist logo design for a tech startup",
        "Generate a fantasy landscape with dragons and castles",
        "Create a realistic portrait of a person from the 1920s",
        "Generate a futuristic car design concept",
        "Create an abstract art piece inspired by music",
        "Generate a cozy coffee shop interior design",
        "Create a magical forest scene with glowing elements",
        "Generate a space station orbiting a distant planet",
        "Create a vintage poster design for a jazz festival",
    ],
    "image_analysis": [
        "What architectural style is shown in this building?",
        "Analyze the composition and color scheme of this artwork",
        "Identify the objects and their relationships in this scene",
        "What emotions does this image convey and why?",
        "Describe the technical aspects of this photograph",
        "What historical period does this image represent?",
        "Analyze the fashion and styling in this photo",
        "What story does this image tell?",
        "Identify any cultural symbols or references",
        "Evaluate the artistic techniques used here",
    ],
    "document_analysis": [
        "Summarize the key points from this research paper",
        "Extract actionable insights from this business report",
        "Analyze the main arguments in this document",
        "Create a mind map from this text content",
        "Identify the target audience for this material",
        "Compare different viewpoints presented here",
        "Extract statistics and data points",
        "Suggest improvements for this writing",
        "Find potential gaps or weaknesses in the argument",
        "Create a timeline from the events mentioned",
    ],
    "creative_writing": [
        "Write a short story about time travel to ancient Rome",
        "Create a dialogue between AI and humans in 2050",
        "Write a product description for an imaginary invention",
        "Compose a poem about the beauty of mathematics",
        "Create a script for a 2-minute comedy sketch",
        "Write a letter from the perspective of a historical figure",
        "Design a character profile for a fantasy novel",
        "Create an elevator pitch for a revolutionary app",
        "Write a travel blog post about a fictional destination",
        "Compose lyrics for a song about overcoming challenges",
    ],
    "problem_solving": [
        "How can I improve my productivity while working from home?",
        "What's the best way to learn a new programming language?",
        "Help me plan a budget-friendly week-long vacation",
        "How do I prepare for a technical job interview?",
        "What are effective strategies for public speaking?",
        "How can I start a small business with limited funds?",
        "What's the best approach to learning data science?",
        "How do I build better habits and break bad ones?",
        "What are some creative solutions for small space living?",
        "How can I improve my photography skills?",
    ],
    "educational": [
        "Explain quantum computing in simple terms",
        "How does machine learning actually work?",
        "What are the causes and effects of climate change?",
        "Explain the basics of cryptocurrency and blockchain",
        "How do vaccines work at the molecular level?",
        "What makes a good investment strategy?",
        "Explain the psychology behind decision making",
        "How does the human brain process language?",
        "What are the principles of sustainable design?",
        "Explain the economics of supply and demand",
    ],
    "real_time_search": [
        "What's the latest news in artificial intelligence?",
        "Current stock price of major tech companies",
        "Recent developments in space exploration",
        "Latest updates on climate change initiatives",
        "What happened in today's sports games?",
        "Recent breakthroughs in medical research",
        "Current weather conditions around the world",
        "Latest political developments and elections",
        "Recent technology product launches",
        "Breaking news from around the globe",
    ],
    "url_analysis": [
        "Summarize the key points from this article: [paste URL here]",
        "Compare the features between these two product pages: [URL1] and [URL2]",
        "Extract the main arguments from this blog post: [paste URL here]",
        "What are the pricing details mentioned on this page: [paste URL here]",
        "Analyze the research methodology described in this paper: [paste URL here]",
        "What are the specifications listed on this product page: [paste URL here]",
        "Compare the approaches discussed in these articles: [URLs]",
        "Extract the event details from this webpage: [paste URL here]",
        "What solutions does this documentation provide: [paste URL here]",
        "Summarize the company information from this about page: [paste URL here]",
    ],
}


def get_smart_suggestions(count=4, mix_categories=True):
    """Generate high-quality, curated suggestions for multimodal chat."""
    if mix_categories:
        # Mix different types of suggestions for variety
        suggestions = []
        categories = list(SUGGESTION_CATEGORIES.keys())

        # Ensure we get at least one from image generation and one from analysis
        priority_categories = [
            "image_generation",
            "image_analysis",
            "real_time_search",
            "url_analysis",
            "problem_solving",
            "educational",
        ]

        # Get one from each priority category first
        for i, category in enumerate(priority_categories[:count]):
            if category in SUGGESTION_CATEGORIES:
                category_suggestions = SUGGESTION_CATEGORIES[category]
                suggestion = rd.choice(category_suggestions)
                suggestions.append(suggestion)

        # Fill remaining slots with random selections
        while len(suggestions) < count:
            category = rd.choice(categories)
            suggestion = rd.choice(SUGGESTION_CATEGORIES[category])
            if suggestion not in suggestions:  # Avoid duplicates
                suggestions.append(suggestion)

        return suggestions[:count]
    else:
        # Get all from random categories
        all_suggestions = []
        for category_suggestions in SUGGESTION_CATEGORIES.values():
            all_suggestions.extend(category_suggestions)

        return rd.sample(all_suggestions, min(count, len(all_suggestions)))


def get_category_suggestions(category, count=4):
    """Get suggestions from a specific category."""
    if category in SUGGESTION_CATEGORIES:
        return rd.sample(
            SUGGESTION_CATEGORIES[category],
            min(count, len(SUGGESTION_CATEGORIES[category])),
        )
    return []


def get_suggestion_category_icon(suggestion):
    """Get an appropriate icon based on the suggestion content."""
    suggestion_lower = suggestion.lower()

    if any(
        word in suggestion_lower for word in ["generate", "create", "design", "draw"]
    ):
        return "🎨"
    elif any(
        word in suggestion_lower
        for word in ["url", "webpage", "website", "link", "compare", "page"]
    ):
        return "🔗"
    elif any(
        word in suggestion_lower
        for word in [
            "latest",
            "current",
            "news",
            "recent",
            "today",
            "stock",
            "weather",
            "breaking",
        ]
    ):
        return "🌐"
    elif any(
        word in suggestion_lower for word in ["analyze", "identify", "describe", "what"]
    ):
        return "🔍"
    elif any(
        word in suggestion_lower
        for word in ["document", "summarize", "extract", "report"]
    ):
        return "📄"
    elif any(word in suggestion_lower for word in ["write", "story", "poem", "script"]):
        return "✍️"
    elif any(word in suggestion_lower for word in ["how", "explain", "learn", "teach"]):
        return "🧠"
    elif any(
        word in suggestion_lower for word in ["help", "plan", "strategy", "improve"]
    ):
        return "�"
    else:
        return "💬"


def get_contextual_suggestions(uploaded_files=None, conversation_history=None, count=4):
    """Generate contextual suggestions based on uploaded files and conversation."""
    suggestions = []

    if uploaded_files:
        # Analyze uploaded files and suggest relevant prompts
        has_images = any(file.type.startswith("image/") for file in uploaded_files)
        has_pdfs = any(file.type == "application/pdf" for file in uploaded_files)
        has_text = any(file.type == "text/plain" for file in uploaded_files)

        if has_images:
            suggestions.extend(rd.sample(SUGGESTION_CATEGORIES["image_analysis"], 2))

        if has_pdfs or has_text:
            suggestions.extend(rd.sample(SUGGESTION_CATEGORIES["document_analysis"], 2))

    # Fill remaining slots with mixed suggestions
    remaining_count = count - len(suggestions)
    if remaining_count > 0:
        mixed_suggestions = get_smart_suggestions(remaining_count, mix_categories=True)
        suggestions.extend(mixed_suggestions)

    return suggestions[:count]


def remove_numbered_bullets(bulleted_list):
    """Remove numbered bullets from a list of suggestions."""
    cleaned_list = []
    for item in bulleted_list:
        # Remove numbered bullets using regex
        cleaned_item = re.sub(r"^\d+\.\s*", "", item)
        # Remove asterisks and other bullet points
        cleaned_item = re.sub(r"^\*\s*", "", cleaned_item)
        # Remove dashes
        cleaned_item = re.sub(r"^-\s*", "", cleaned_item)
        cleaned_item = cleaned_item.strip()
        if cleaned_item:  # Only add non-empty items
            cleaned_list.append(cleaned_item)
    return cleaned_list


try:
    os.mkdir("data/")
except:
    pass

# Load conversations from backend if available, otherwise fall back to local storage
try:
    if st.session_state.get("backend_available", False):
        # Load conversations from backend
        user_id = st.session_state.get("backend_user_id")
        if user_id:
            backend_conversations = load_conversations_from_backend(user_id)
            past_chats = {}
            for conv in backend_conversations:
                past_chats[str(conv.get("conversation_id", conv.get("id")))] = conv.get(
                    "title", "New Chat"
                )
        else:
            past_chats = {}
    else:
        # Fall back to local storage
        past_chats: dict = joblib.load("data/multimodal_past_chats_list")
except:
    past_chats = {}

with st.sidebar:
    # Initialize chat_id if not set
    if "multimodal_chat_id" not in st.session_state:
        st.session_state.multimodal_chat_id = NEW_CHAT_KEY

    # Initialize confirm_delete state
    if "multimodal_confirm_delete" not in st.session_state:
        st.session_state.multimodal_confirm_delete = False

    # Initialize suggestions state
    if "multimodal_suggestions" not in st.session_state:
        st.session_state.multimodal_suggestions = []

    if "multimodal_show_suggestions" not in st.session_state:
        st.session_state.multimodal_show_suggestions = True

    # Track if user has ever typed (to distinguish first-time vs clearing input)
    if "multimodal_user_has_typed" not in st.session_state:
        st.session_state.multimodal_user_has_typed = False

    # Temporary hide state for when user is typing
    if "multimodal_temp_hide_suggestions" not in st.session_state:
        st.session_state.multimodal_temp_hide_suggestions = False

    # Initialize file uploader key
    if "multimodal_file_uploader_key" not in st.session_state:
        st.session_state.multimodal_file_uploader_key = 0

    # New Chat button with a distinct color
    if st.button("＋ New Multimodal Chat", type="primary", use_container_width=True):
        st.session_state.multimodal_chat_id = NEW_CHAT_KEY
        st.session_state.multimodal_confirm_delete = (
            False  # Reset any pending delete confirmation
        )
        # Clear uploaded files for new chat
        st.session_state.multimodal_file_uploader_key += 1
        st.rerun()

    # File uploader section
    st.markdown("### 📁 Upload Files")
    uploaded_files = st.file_uploader(
        "Choose files (Images, PDFs, Text)",
        type=["jpg", "jpeg", "png", "pdf", "txt"],
        accept_multiple_files=True,
        help="Support for images, PDFs, and text files",
        key=f"multimodal_file_uploader_{st.session_state.multimodal_file_uploader_key}",
    )

    # Display uploaded files info
    if uploaded_files:
        st.markdown("**Uploaded Files:**")
        for uploaded_file in uploaded_files:
            if uploaded_file.type.startswith("image/"):
                st.markdown(f"📷 {uploaded_file.name}")
            elif uploaded_file.type == "application/pdf":
                st.markdown(f"📄 {uploaded_file.name}")
            elif uploaded_file.type == "text/plain":
                st.markdown(f"📝 {uploaded_file.name}")

    # Suggestions toggle
    st.markdown("### 💡 Suggestions")
    suggestions_enabled = st.checkbox(
        "Show suggestion prompts",
        value=st.session_state.multimodal_show_suggestions,
        help="Toggle prompt suggestions above the chat input",
    )

    if suggestions_enabled != st.session_state.multimodal_show_suggestions:
        st.session_state.multimodal_show_suggestions = suggestions_enabled
        # Clear suggestions to force regeneration when turned back on
        if suggestions_enabled:
            st.session_state.multimodal_suggestions = []
        st.rerun()

    # Initialize search state
    if "multimodal_enable_search" not in st.session_state:
        st.session_state.multimodal_enable_search = True

    # Search toggle
    st.markdown("### 🌐 Web Search")
    search_enabled = st.checkbox(
        "Enable real-time web search",
        value=st.session_state.multimodal_enable_search,
        help="Allow the AI to search the web for current information and provide citations",
    )

    if search_enabled != st.session_state.multimodal_enable_search:
        st.session_state.multimodal_enable_search = search_enabled
        st.rerun()

    # Show search availability status
    if search_available:
        if search_enabled:
            st.success("🟢 Web search is enabled and ready")
        else:
            st.info("🔵 Web search is available but disabled")
    else:
        st.error("🔴 Web search unavailable - check API configuration")

    # Initialize URL context state
    if "multimodal_enable_url_context" not in st.session_state:
        st.session_state.multimodal_enable_url_context = True

    # URL Context toggle
    st.markdown("### 🔗 URL Analysis")
    url_context_enabled = st.checkbox(
        "Enable URL content analysis",
        value=st.session_state.multimodal_enable_url_context,
        help="Allow the AI to read and analyze content from URLs you provide in your messages",
    )

    if url_context_enabled != st.session_state.multimodal_enable_url_context:
        st.session_state.multimodal_enable_url_context = url_context_enabled
        st.rerun()

    # Show URL context availability status
    if search_available:
        if url_context_enabled:
            st.success("🟢 URL analysis is enabled and ready")
        else:
            st.info("🔵 URL analysis is available but disabled")
    else:
        st.error("🔴 URL analysis unavailable - check API configuration")

    st.markdown("💡 **Tip:** Paste URLs directly in your messages for analysis!")

    # Backend status section
    st.markdown("### 🗄️ Backend & Database")
    backend_status = st.session_state.get("backend_available", False)

    if backend_status:
        st.success("🟢 PostgreSQL backend connected")
        user_id = st.session_state.get("backend_user_id", "Unknown")
        st.caption(f"User ID: {user_id}")

        # Show backend API health
        try:
            api_client = get_backend_client()
            if api_client.health_check():
                st.caption("✅ API health check passed")
            else:
                st.caption("⚠️ API health check failed")
        except:
            st.caption("❌ API unreachable")
    else:
        st.error("🔴 Backend unavailable")
        st.caption("Chat history stored locally only")

        # Offer retry button
        if st.button("🔄 Retry Backend Connection", use_container_width=True):
            initialize_backend_session()
            st.rerun()

    # Image Generation Test Section
    st.markdown("### 🎨 Image Generation")
    if image_gen_client:
        st.success("🟢 Image generation available")
        if st.button("🧪 Test Image Generation", use_container_width=True):
            with st.spinner("Testing image generation..."):
                test_prompt = "a simple red circle"
                text_response, test_images = generate_image_from_text(test_prompt)
                if test_images:
                    st.success("✅ Image generation test passed!")
                    st.image(test_images[0], caption="Test image", width=150)
                else:
                    st.error(f"❌ Image generation test failed: {text_response}")
    else:
        st.error("🔴 Image generation unavailable")
        st.caption("Check your GEMINI_API_KEY configuration")

    st.markdown("---")

    # Filter past_chats to include chats with saved messages OR the current active chat
    available_chats = {}
    for chat_id, title in past_chats.items():
        # Include if: 1) backend is available (conversations already loaded from DB),
        # 2) has local saved files, OR 3) is the current active chat
        if (
            st.session_state.get("backend_available", False)
            or os.path.exists(f"data/multimodal_{chat_id}-st_messages")
            or chat_id == st.session_state.multimodal_chat_id
        ):
            available_chats[chat_id] = title

    # Sort chat IDs by timestamp (latest first) - extract timestamp from chat_id
    def get_chat_timestamp(chat_id):
        try:
            # Chat IDs are timestamps, so convert to float for sorting
            return float(chat_id)
        except (ValueError, TypeError):
            # Backend chat IDs have format "user_timestamp" - extract the timestamp part
            try:
                return float(chat_id.rsplit("_", 1)[-1])
            except (ValueError, TypeError, IndexError):
                # If it's not a timestamp (like NEW_CHAT_KEY), put it at the end
                return 0

    sorted_chat_ids = sorted(
        available_chats.keys(), key=get_chat_timestamp, reverse=True
    )

    # Show dropdown only if there are history chats available
    if available_chats:
        st.markdown("### 💬 Chat History")

        # Determine current selection for history chats
        if st.session_state.get("multimodal_chat_id") is None:
            # No current selection - don't auto-select anything
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
                key="multimodal_chat_selector",
            )
        elif st.session_state.multimodal_chat_id == NEW_CHAT_KEY:
            # Currently on new chat - show dropdown but no selection
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
                key="multimodal_chat_selector",
            )
        elif st.session_state.multimodal_chat_id in available_chats:
            # Currently on a valid existing chat - put current chat first, then sorted others
            other_chats = [
                id
                for id in sorted_chat_ids
                if id != st.session_state.multimodal_chat_id
            ]
            options = [st.session_state.multimodal_chat_id] + other_chats
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=options,
                index=0,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
                key="multimodal_chat_selector",
            )
        else:
            # Current chat_id is invalid - reset to new chat
            st.session_state.multimodal_chat_id = NEW_CHAT_KEY
            selected_chat = st.selectbox(
                label="Select a chat history:",
                options=sorted_chat_ids,
                index=None,
                format_func=lambda x: available_chats.get(x, "Unknown Chat"),
                placeholder="Select a chat...",
                key="multimodal_chat_selector",
            )

        # Update chat_id if a different chat was selected
        if selected_chat and selected_chat != st.session_state.get(
            "multimodal_chat_id"
        ):
            st.session_state.multimodal_chat_id = selected_chat
            st.rerun()
    else:
        st.info("📝 No chat history yet. Start a new conversation!")

    # Set chat title
    st.session_state.multimodal_chat_title = available_chats.get(
        st.session_state.multimodal_chat_id, "New Chat"
    )

# Check if chat_id has changed and force reload of messages
if "multimodal_current_chat_id" not in st.session_state:
    st.session_state.multimodal_current_chat_id = st.session_state.multimodal_chat_id
    chat_changed = True
elif st.session_state.multimodal_current_chat_id != st.session_state.multimodal_chat_id:
    st.session_state.multimodal_current_chat_id = st.session_state.multimodal_chat_id
    chat_changed = True
    # Only clear uploaded files when actually switching between different chats
    if st.session_state.multimodal_chat_id != NEW_CHAT_KEY:
        # Clear the file uploader by using a unique key that changes with chat
        if "multimodal_file_uploader_key" not in st.session_state:
            st.session_state.multimodal_file_uploader_key = 0
        else:
            st.session_state.multimodal_file_uploader_key += 1
else:
    chat_changed = False

# Handle message loading based on chat type
if st.session_state.multimodal_chat_id == NEW_CHAT_KEY:
    # New chat - always start with empty messages
    if chat_changed:
        st.session_state.multimodal_messages = []
        st.session_state.multimodal_gemini_history = []
else:
    # Existing chat - load saved messages
    try:
        # Only reload messages if chat has changed or messages are empty
        if (
            chat_changed
            or not hasattr(st.session_state, "multimodal_messages")
            or not st.session_state.multimodal_messages
        ):
            if st.session_state.get("backend_available", False):
                # Load messages from backend
                backend_messages = load_messages_from_backend(
                    st.session_state.multimodal_chat_id
                )
                if backend_messages:
                    # Convert backend messages to frontend format
                    st.session_state.multimodal_messages = []
                    for msg in backend_messages:
                        # Map backend message_type ("Human"/"AI") to frontend role ("user"/"assistant")
                        msg_type = msg.get("message_type", "")
                        if msg_type == "Human":
                            role = "user"
                        elif msg_type == "AI":
                            role = "assistant"
                        else:
                            role = msg.get("role", "user")
                        message_data = {
                            "role": role,
                            "content": msg.get("content", ""),
                        }
                        # Add metadata if available
                        if msg.get("metadata"):
                            metadata = msg["metadata"]
                            if metadata.get("grounding_metadata"):
                                message_data["grounding_metadata"] = metadata[
                                    "grounding_metadata"
                                ]
                            if metadata.get("url_context_metadata"):
                                message_data["url_context_metadata"] = metadata[
                                    "url_context_metadata"
                                ]
                        st.session_state.multimodal_messages.append(message_data)

                    # Create Gemini history for continuing conversation
                    st.session_state.multimodal_gemini_history = []
                    for msg in st.session_state.multimodal_messages:
                        # Map "assistant" to "model" for Gemini API
                        gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
                        if gemini_role in ["user", "model"]:
                            st.session_state.multimodal_gemini_history.append(
                                {"role": gemini_role, "parts": [msg["content"]]}
                            )
                else:
                    st.session_state.multimodal_messages = []
                    st.session_state.multimodal_gemini_history = []
            else:
                # Fall back to local storage
                st.session_state.multimodal_messages = joblib.load(
                    f"data/multimodal_{st.session_state.multimodal_chat_id}-st_messages"
                )
                st.session_state.multimodal_gemini_history = joblib.load(
                    f"data/multimodal_{st.session_state.multimodal_chat_id}-gemini_messages"
                )
    except Exception as e:
        st.warning(f"Failed to load conversation: {e}")
        st.session_state.multimodal_messages = []
        st.session_state.multimodal_gemini_history = []

st.session_state.multimodal_chat = st.session_state.model.start_chat(
    history=st.session_state.multimodal_gemini_history,
)

# Show delete button in top right corner for existing chats (not new chats)
if (
    st.session_state.multimodal_chat_id != NEW_CHAT_KEY
    and st.session_state.multimodal_chat_id in past_chats
):

    # Create header with delete button
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown("")  # Empty space
    with col2:
        if st.button(
            "🗑️ Delete Chat",
            key="multimodal_delete_chat_main",
            help="Delete this chat permanently",
            type="secondary",
            use_container_width=True,
        ):
            st.session_state.multimodal_confirm_delete = True
            st.rerun()


# Handle delete confirmation with dialog
@st.dialog("Delete Multimodal Chat Confirmation")
def delete_multimodal_chat_dialog():
    st.warning(f"Are you sure you want to permanently delete the chat:")
    st.markdown(
        f"**'{past_chats.get(st.session_state.multimodal_chat_id, 'Unknown Chat')}'**"
    )
    st.error("⚠️ This action cannot be undone!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🗑️ Delete Permanently",
            key="multimodal_dialog_confirm_yes",
            type="primary",
            use_container_width=True,
        ):
            # Delete the chat
            chat_to_delete = st.session_state.multimodal_chat_id

            try:
                if st.session_state.get("backend_available", False):
                    # Delete from backend
                    user_id = st.session_state.get("backend_user_id")
                    api_client = get_backend_client()
                    success = api_client.delete_conversation(chat_to_delete, user_id)

                    if success:
                        # Remove from local past_chats cache
                        if chat_to_delete in past_chats:
                            del past_chats[chat_to_delete]
                        st.success("✅ Chat deleted from backend database!")
                    else:
                        st.error("❌ Failed to delete chat from backend")
                        return
                else:
                    # Delete from local storage
                    st_messages_file = f"data/multimodal_{chat_to_delete}-st_messages"
                    gemini_messages_file = (
                        f"data/multimodal_{chat_to_delete}-gemini_messages"
                    )

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
                        joblib.dump(past_chats, "data/multimodal_past_chats_list")

                    st.success(
                        f"✅ Chat deleted successfully! ({files_deleted} files removed)"
                    )

                # Reset to new chat
                st.session_state.multimodal_chat_id = NEW_CHAT_KEY
                st.session_state.multimodal_current_chat_id = NEW_CHAT_KEY
                st.session_state.multimodal_messages = []
                st.session_state.multimodal_gemini_history = []
                st.session_state.multimodal_confirm_delete = False

                st.success(f"✅ Chat deleted successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Error deleting chat: {str(e)}")
                st.session_state.multimodal_confirm_delete = False

    with col2:
        if st.button(
            "❌ Cancel", key="multimodal_dialog_confirm_no", use_container_width=True
        ):
            st.session_state.multimodal_confirm_delete = False
            st.rerun()


# Show dialog if delete is confirmed
if st.session_state.get("multimodal_confirm_delete", False):
    delete_multimodal_chat_dialog()

# Show current chat title and option to regenerate if it's "New Chat"
if (
    hasattr(st.session_state, "multimodal_chat_id")
    and st.session_state.multimodal_chat_id in past_chats
    and past_chats[st.session_state.multimodal_chat_id] == "New Chat"
    and len(st.session_state.multimodal_messages) >= 2
):

    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("💡 This chat doesn't have a title yet. Generate one?")
    with col2:
        if st.button("Generate Title", key="multimodal_main_generate_title"):
            with st.spinner("Generating title..."):
                summary = generate_chat_summary(st.session_state.multimodal_messages)
                if summary and summary != "New Chat":
                    past_chats[st.session_state.multimodal_chat_id] = summary
                    st.session_state.multimodal_chat_title = summary
                    if st.session_state.get("backend_available", False):
                        api_client = get_backend_client()
                        api_client.update_conversation(
                            st.session_state.multimodal_chat_id, summary
                        )
                    else:
                        joblib.dump(past_chats, "data/multimodal_past_chats_list")
                    st.success(f"Title set to: {summary}")
                    st.rerun()

# Display uploaded files preview in main area
if uploaded_files:
    st.markdown("### 📁 Uploaded Files Preview")

    # Create columns for file previews
    cols = st.columns(min(len(uploaded_files), 3))

    for i, uploaded_file in enumerate(uploaded_files):
        with cols[i % 3]:
            if uploaded_file.type.startswith("image/"):
                image = Image.open(uploaded_file)
                # Use specific width instead of full column width
                st.image(image, caption=uploaded_file.name, width=300)
            elif uploaded_file.type == "application/pdf":
                st.markdown(f"📄 **{uploaded_file.name}**")
                # Show first few lines of PDF text
                try:
                    text_preview = extract_text_from_pdf(uploaded_file)[:200] + "..."
                    st.text_area("PDF Preview", text_preview, height=100, disabled=True)
                except:
                    st.markdown("*PDF content preview unavailable*")
            elif uploaded_file.type == "text/plain":
                st.markdown(f"📝 **{uploaded_file.name}**")
                # Show first few lines of text
                try:
                    text_preview = extract_text_from_txt(uploaded_file)[:200] + "..."
                    st.text_area(
                        "Text Preview", text_preview, height=100, disabled=True
                    )
                except:
                    st.markdown("*Text content preview unavailable*")

    st.markdown("---")

# Display chat messages
for message in st.session_state.multimodal_messages:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant", avatar=AI_AVATAR_ICON):
            st.markdown(message["content"])

            # Display search details if this was a search response
            if "grounding_metadata" in message and message["grounding_metadata"]:
                with st.expander("🔍 Search Details", expanded=False):
                    display_serialized_search_sources(message["grounding_metadata"])

            # Display URL context details if this was a URL analysis response
            if "url_context_metadata" in message and message["url_context_metadata"]:
                with st.expander("🔗 URL Analysis Details", expanded=False):
                    display_serialized_url_context_sources(
                        message["url_context_metadata"]
                    )

            # Display combined details if both search and URL context were used
            if (
                "grounding_metadata" in message
                and message["grounding_metadata"]
                and "url_context_metadata" in message
                and message["url_context_metadata"]
            ):
                # Override the individual expanders above with a combined one
                with st.expander("🔍🔗 Search & URL Analysis Details", expanded=False):
                    display_serialized_search_sources(message["grounding_metadata"])
                    st.markdown("---")
                    display_serialized_url_context_sources(
                        message["url_context_metadata"]
                    )

            # Display stored images if any
            if "images" in message and message["images"]:
                st.markdown("**Generated Image(s):**")
                for i, image_bytes in enumerate(message["images"]):
                    image = Image.open(BytesIO(image_bytes))
                    # Display with reasonable size for chat
                    st.image(
                        image,
                        caption=f"Generated Image {i+1}",
                        width=400,  # Fixed width instead of full width
                    )

                    # Show image dimensions
                    st.caption(f"Resolution: {image.width} × {image.height} pixels")

                    # Provide high-quality download option
                    st.download_button(
                        label="📥 Download Image",
                        data=image_bytes,
                        file_name=f"multimodal_hq_stored_image_{i+1}_{int(time.time())}.png",
                        mime="image/png",
                        key=f"stored_download_img_{i}_{hash(str(message['content']))}",
                    )

# Suggestions section - show when there are no messages and suggestions are enabled
# With default chat input, we can't detect real-time typing, so suggestions show until first message
show_suggestions_and_welcome = (
    not st.session_state.multimodal_messages
    or st.session_state.get("multimodal_show_suggestions", True)
) and not st.session_state.get("multimodal_processing", False)

if show_suggestions_and_welcome:

    # Generate suggestions if they don't exist or need refresh
    if not st.session_state.multimodal_suggestions:
        with st.spinner("Loading suggestions..."):
            # Use contextual suggestions based on uploaded files
            if "uploaded_files" in locals() and uploaded_files:
                st.session_state.multimodal_suggestions = get_contextual_suggestions(
                    uploaded_files=uploaded_files, count=4
                )
            else:
                # Use smart mixed suggestions for new chats
                st.session_state.multimodal_suggestions = get_smart_suggestions(count=4)

    # Display suggestions if we have any
    if st.session_state.multimodal_suggestions:
        st.markdown("#### 💡 Suggested Prompts")

        # Create columns for suggestion buttons
        cols = st.columns(len(st.session_state.multimodal_suggestions))

        def handle_suggestion_click(suggestion):
            """Handle when a suggestion button is clicked."""
            # Store the suggestion as the prompt input
            st.session_state.multimodal_selected_suggestion = suggestion
            # Hide suggestions after selection
            st.session_state.multimodal_show_suggestions = False
            st.rerun()

        for i, col in enumerate(cols):
            if i < len(st.session_state.multimodal_suggestions):
                with col:
                    suggestion = st.session_state.multimodal_suggestions[i]
                    icon = get_suggestion_category_icon(suggestion)

                    # Truncate long suggestions for button display
                    button_text = suggestion
                    if len(button_text) > 45:
                        button_text = button_text[:42] + "..."

                    # Add icon to button
                    display_text = f"{icon} {button_text}"

                    if st.button(
                        display_text,
                        key=f"multimodal_suggestion_{i}",
                        help=suggestion,  # Show full text on hover
                        use_container_width=True,
                    ):
                        handle_suggestion_click(suggestion)

        # Refresh suggestions button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 New Suggestions", key="refresh_multimodal_suggestions"):
                # Clear current suggestions to force regeneration with new random selections
                st.session_state.multimodal_suggestions = []
                st.rerun()

        st.markdown("---")

# Always show the chat input at the bottom
prompt = st.chat_input("Message Gemini (supports text, images, PDFs, and URLs)")

# Handle selected suggestion (this will override the prompt if a suggestion was clicked)
if st.session_state.get("multimodal_selected_suggestion"):
    prompt = st.session_state.multimodal_selected_suggestion
    # Clear the selected suggestion
    del st.session_state.multimodal_selected_suggestion

if prompt:
    # Set flag to indicate prompt is being processed (hides welcome message)
    st.session_state.multimodal_processing = True

    # Hide suggestions after first interaction
    if not st.session_state.multimodal_messages:
        st.session_state.multimodal_show_suggestions = False
        # Set a flag to remember user has started typing
        st.session_state.multimodal_user_has_typed = True

    # Process uploaded files first
    files_data, file_info = (
        process_uploaded_files(uploaded_files) if uploaded_files else ([], [])
    )

    # Check for URLs in the prompt
    detected_urls = (
        detect_urls_in_prompt(prompt)
        if st.session_state.get("multimodal_enable_url_context", True)
        else []
    )

    # Check what type of request this is
    has_uploaded_images = any(isinstance(data, Image.Image) for data in files_data)
    is_image_editing = detect_image_editing_request(prompt, has_uploaded_images)
    is_image_generation = (
        detect_image_generation_request(prompt) if not is_image_editing else False
    )

    # Determine if URL context should be used
    use_url_context = (
        st.session_state.get("multimodal_enable_url_context", True)
        and detected_urls
        and search_available
        and detect_url_context_need(prompt, detected_urls)
        and not is_image_generation
        and not is_image_editing
    )

    # Initialize search and combined usage flags
    use_search = False
    use_combined = False

    # If this is a new chat, create a timestamp-based ID
    if st.session_state.multimodal_chat_id == NEW_CHAT_KEY:
        st.session_state.multimodal_chat_id = f"{time.time()}"
        st.session_state.multimodal_current_chat_id = (
            st.session_state.multimodal_chat_id
        )  # Update the tracking variable

    if st.session_state.multimodal_chat_id not in past_chats.keys():
        # For new chats, start with a temporary title
        past_chats[st.session_state.multimodal_chat_id] = "New Chat"

        # Create conversation in backend if available
        if st.session_state.get("backend_available", False):
            user_id = st.session_state.get("backend_user_id")
            backend_conversation_id = create_backend_conversation(user_id, "New Chat")
            if backend_conversation_id:
                st.session_state.multimodal_chat_id = str(backend_conversation_id)
                past_chats[str(backend_conversation_id)] = "New Chat"
        else:
            # Save to local storage
            joblib.dump(past_chats, "data/multimodal_past_chats_list")

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
        if file_info:
            st.markdown("**Attached files:**")
            for info in file_info:
                st.markdown(f"- {info}")
        if detected_urls:
            st.markdown("**URLs to analyze:**")
            for url in detected_urls:
                st.markdown(f"- [{url}]({url})")

    # Add user message to session state
    st.session_state.multimodal_messages.append(
        dict(
            role="user",
            content=prompt,
        )
    )

    if is_image_generation:
        # Handle image generation
        with st.chat_message(
            name="assistant",
            avatar=AI_AVATAR_ICON,
        ):
            with st.spinner("Generating image... This may take a few seconds."):
                text_response, generated_images = generate_image_from_text(prompt)

                if generated_images:

                    # Display text response if any
                    if text_response:
                        st.markdown("**AI Response:**")
                        st.markdown(text_response)

                    # Display generated images
                    st.markdown("**Generated Image(s):**")
                    for i, image in enumerate(generated_images):
                        # Display with reasonable size for chat
                        st.image(
                            image,
                            caption=f"Generated Image {i+1}",
                            width=400,  # Fixed width instead of full width
                        )

                        # Show image dimensions
                        st.caption(f"Resolution: {image.width} × {image.height} pixels")

                        # Provide high-quality download option
                        buf = BytesIO()
                        # Save with maximum quality settings
                        image.save(buf, format="PNG", optimize=False, compress_level=0)
                        byte_im = buf.getvalue()

                        st.download_button(
                            label="📥 Download Image",
                            data=byte_im,
                            file_name=f"multimodal_hq_image_{i+1}_{int(time.time())}.png",
                            mime="image/png",
                            key=f"download_img_{i}_{time.time()}",
                        )

                    full_response = f"I've generated {len(generated_images)} image(s) based on your request: '{prompt}'"
                    if text_response:
                        full_response += f"\n\n{text_response}"

                    # Store images in session state for persistence
                    st.session_state.generated_images = generated_images
                else:
                    # Show detailed error message
                    st.error("❌ Image generation failed")
                    st.markdown("**Error Details:**")
                    st.markdown(text_response)

                    # Provide troubleshooting suggestions
                    with st.expander("🛠️ Troubleshooting"):
                        st.markdown(
                            """
                        **Possible solutions:**
                        1. **Try a simpler prompt** - Complex prompts may be filtered
                        2. **Check API quota** - You may have reached daily limits
                        3. **Avoid restricted content** - Some topics are blocked for safety
                        4. **Try again later** - Temporary service issues may resolve
                        5. **Use the test button** in the sidebar to verify image generation is working
                        """
                        )

                    full_response = f"I wasn't able to generate an image for: '{prompt}'. {text_response}"

    elif is_image_editing:
        # Handle image editing
        with st.chat_message(
            name="assistant",
            avatar=AI_AVATAR_ICON,
        ):
            with st.spinner("Editing image... This may take a few seconds."):
                # Find the first uploaded image
                uploaded_image = None
                for data in files_data:
                    if isinstance(data, Image.Image):
                        uploaded_image = data
                        break

                if uploaded_image:
                    text_response, edited_images = edit_image_with_prompt(
                        uploaded_image, prompt
                    )

                    if edited_images:

                        # Display text response if any
                        if text_response:
                            st.markdown("**AI Response:**")
                            st.markdown(text_response)

                        # Display edited images
                        st.markdown("**Edited Image(s):**")
                        for i, image in enumerate(edited_images):
                            # Display with reasonable size for chat
                            st.image(
                                image,
                                caption=f"Edited Image {i+1}",
                                width=400,  # Fixed width instead of full width
                            )

                            # Show image dimensions
                            st.caption(
                                f"Resolution: {image.width} × {image.height} pixels"
                            )

                            # Provide high-quality download option
                            buf = BytesIO()
                            # Save with maximum quality settings
                            image.save(
                                buf, format="PNG", optimize=False, compress_level=0
                            )
                            byte_im = buf.getvalue()

                            st.download_button(
                                label="📥 Download Edited Image",
                                data=byte_im,
                                file_name=f"multimodal_edited_image_{i+1}_{int(time.time())}.png",
                                mime="image/png",
                                key=f"download_edited_img_{i}_{time.time()}",
                            )

                        full_response = (
                            f"I've edited the image based on your request: '{prompt}'"
                        )
                        if text_response:
                            full_response += f"\n\n{text_response}"

                        # Store edited images in session state for persistence
                        st.session_state.generated_images = edited_images
                    else:
                        st.error(
                            "❌ Failed to edit image. Please try again with a different prompt."
                        )
                        full_response = (
                            text_response
                            if text_response
                            else "I wasn't able to edit the image as requested. Please try rephrasing your editing instructions."
                        )
                else:
                    st.error("❌ No image found to edit. Please upload an image first.")
                    full_response = (
                        "Please upload an image file before requesting edits."
                    )

    else:
        # Handle regular chat (text, file analysis, etc.)
        # Determine processing approach based on available tools and user needs

        # Check if search should be used (but not if we're doing URL context or file analysis)
        use_search = (
            st.session_state.get("multimodal_enable_search", True)
            and search_available
            and detect_search_need(prompt)
            and not files_data  # Don't use search when analyzing uploaded files
            and not use_url_context  # Don't use search when analyzing URLs
        )

        # Determine if we need both search and URL context
        use_combined = (
            use_url_context
            and st.session_state.get("multimodal_enable_search", True)
            and search_available
            and detect_search_need(prompt)
        )

        if use_combined:
            # Use both search and URL context
            with st.chat_message(name="assistant", avatar=AI_AVATAR_ICON):
                with st.spinner("Searching the web and analyzing URLs..."):
                    search_response, grounding_metadata, url_context_metadata = (
                        generate_with_search_and_url_context(prompt, detected_urls)
                    )

                    if search_response and search_response.text:
                        # Add citations to the response text
                        response_text = add_citations_to_text(
                            search_response.text, grounding_metadata
                        )

                        st.markdown(response_text)

                        # Display search and URL sources if available
                        if grounding_metadata or url_context_metadata:
                            with st.expander("🔍 Search & URL Details", expanded=False):
                                if grounding_metadata:
                                    display_search_sources(grounding_metadata)
                                    if url_context_metadata:
                                        st.markdown("---")
                                if url_context_metadata:
                                    display_url_context_sources(url_context_metadata)

                        full_response = response_text
                        # Store metadata for this search
                        st.session_state.multimodal_current_grounding_metadata = (
                            grounding_metadata
                        )
                        st.session_state.multimodal_current_url_context_metadata = (
                            url_context_metadata
                        )
                    else:
                        st.warning(
                            "⚠️ Search and URL analysis encountered issues - some sites may be restricted during the experimental phase. Continuing with regular chat."
                        )
                        # Fall back to regular chat
                        use_combined = False
                        use_search = False
                        use_url_context = False
                        st.session_state.multimodal_current_grounding_metadata = None
                        st.session_state.multimodal_current_url_context_metadata = None

        elif use_url_context:
            # Use URL context only
            with st.chat_message(name="assistant", avatar=AI_AVATAR_ICON):
                with st.spinner("Analyzing URL content..."):
                    url_response, url_context_metadata = generate_with_url_context(
                        prompt, detected_urls
                    )

                    if url_response and url_response.text:
                        st.markdown(url_response.text)

                        # Display URL sources if available
                        if url_context_metadata:
                            with st.expander("🔗 URL Analysis Details", expanded=False):
                                display_url_context_sources(url_context_metadata)

                        full_response = url_response.text
                        # Store URL context metadata
                        st.session_state.multimodal_current_url_context_metadata = (
                            url_context_metadata
                        )
                        st.session_state.multimodal_current_grounding_metadata = None
                    else:
                        st.warning(
                            "⚠️ URL analysis failed - some sites may be restricted during the experimental phase. Continuing with regular chat."
                        )
                        # Fall back to regular chat
                        use_url_context = False
                        st.session_state.multimodal_current_url_context_metadata = None

        elif use_search:
            # Use search-enabled generation only
            with st.chat_message(name="assistant", avatar=AI_AVATAR_ICON):
                with st.spinner("Searching the web for current information..."):
                    search_response, grounding_metadata = generate_with_search(prompt)

                    if search_response and search_response.text:
                        # Add citations to the response text
                        response_text = add_citations_to_text(
                            search_response.text, grounding_metadata
                        )

                        st.markdown(response_text)

                        # Display search sources if available
                        if grounding_metadata:
                            with st.expander("🔍 Search Details", expanded=False):
                                display_search_sources(grounding_metadata)

                        full_response = response_text
                        # Store grounding metadata for this search
                        st.session_state.multimodal_current_grounding_metadata = (
                            grounding_metadata
                        )
                        st.session_state.multimodal_current_url_context_metadata = None
                    else:
                        st.error("❌ Search failed. Falling back to regular chat.")
                        # Fall back to regular chat
                        use_search = False
                        st.session_state.multimodal_current_grounding_metadata = None

        if not use_search and not use_url_context and not use_combined:
            # Regular chat without search or URL context
            # Clear any previous metadata
            st.session_state.multimodal_current_grounding_metadata = None
            st.session_state.multimodal_current_url_context_metadata = None

            # Check if we should use backend for regular text chat
            if (
                st.session_state.get("backend_available", False)
                and not files_data  # No files to analyze locally
                and not is_image_generation
                and not is_image_editing
            ):

                # Use backend for text-only chat
                with st.chat_message(name="assistant", avatar=AI_AVATAR_ICON):
                    with st.spinner("Processing with backend..."):
                        user_id = st.session_state.get("backend_user_id")
                        api_client = get_backend_client()

                        try:
                            # Send to backend and get AI response
                            result = api_client.send_chat_message(
                                user_id, prompt, st.session_state.multimodal_chat_id
                            )

                            if result and "ai_message" in result:
                                backend_response = result["ai_message"]["content"]
                                st.markdown(backend_response)
                                full_response = backend_response

                                # Update conversation_id if new one was created
                                if result.get("conversation_id"):
                                    st.session_state.multimodal_chat_id = str(
                                        result["conversation_id"]
                                    )
                            else:
                                st.error("❌ Backend response failed")
                                full_response = "Sorry, I couldn't process your request at the moment."

                        except Exception as e:
                            st.error(f"❌ Backend error: {e}")
                            full_response = (
                                "Sorry, there was an error processing your request."
                            )
            else:
                # Use local Gemini model for file analysis, image generation, or when backend unavailable
                # Prepare content for the model
                model_content = [prompt]

                # Add file data to model content
                for file_data in files_data:
                    model_content.append(file_data)

                # Add system prompt for multimodal understanding
                system_prompt = """You are an expert AI assistant capable of understanding and analyzing text, images, and documents. 
                When provided with files, analyze them thoroughly and provide helpful, detailed responses. 
                For images, describe what you see and answer any questions about them.
                For PDFs and text files, summarize content and answer questions based on the text."""

                model_content.append(system_prompt)

                # Generate response
                response = st.session_state.multimodal_chat.send_message(
                    model_content,
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
    message_data = dict(
        role="model",
        content=final_content,
        avatar=AI_AVATAR_ICON,
    )

    # Add grounding metadata for search responses
    if (use_search or use_combined) and st.session_state.get(
        "multimodal_current_grounding_metadata"
    ):
        serialized_metadata = serialize_grounding_metadata(
            st.session_state.multimodal_current_grounding_metadata
        )
        if serialized_metadata:
            message_data["grounding_metadata"] = serialized_metadata

    # Add URL context metadata for URL analysis responses
    if (use_url_context or use_combined) and st.session_state.get(
        "multimodal_current_url_context_metadata"
    ):
        serialized_url_metadata = serialize_url_context_metadata(
            st.session_state.multimodal_current_url_context_metadata
        )
        if serialized_url_metadata:
            message_data["url_context_metadata"] = serialized_url_metadata

    # Add image data for image generation or editing messages
    if (
        (is_image_generation or is_image_editing)
        and "generated_images" in st.session_state
        and st.session_state.generated_images
    ):
        # Convert images to bytes for storage with high quality
        image_bytes_list = []
        for image in st.session_state.generated_images:
            buf = BytesIO()
            # Save with maximum quality for storage
            image.save(buf, format="PNG", optimize=False, compress_level=0)
            image_bytes_list.append(buf.getvalue())
        message_data["images"] = image_bytes_list

    if (
        not is_image_generation
        and not is_image_editing
        and not use_search
        and not use_url_context
        and not use_combined
        and not (st.session_state.get("backend_available", False) and not files_data)
        and st.session_state.multimodal_chat.history
    ):
        # Use the complete response from chat history if available (only for local Gemini chat)
        try:
            final_content = st.session_state.multimodal_chat.history[-1].parts[0].text
            message_data["content"] = final_content
        except:
            pass

    st.session_state.multimodal_messages.append(message_data)

    # Clear processing flag now that message is added
    st.session_state.multimodal_processing = False

    # Update gemini history (only for regular chat without search/URL context, not image generation or editing)
    if (
        not is_image_generation
        and not is_image_editing
        and not use_search
        and not use_url_context
        and not use_combined
    ):
        st.session_state.multimodal_gemini_history = (
            st.session_state.multimodal_chat.history
        )

    # Generate summary after first AI response
    if (
        len(st.session_state.multimodal_messages) >= 2
        and past_chats[st.session_state.multimodal_chat_id] == "New Chat"
    ):
        # Generate summary immediately after first response for new chats
        summary = generate_chat_summary(st.session_state.multimodal_messages)
        if summary != "New Chat":
            past_chats[st.session_state.multimodal_chat_id] = summary
            st.session_state.multimodal_chat_title = summary

        # Save to backend if available
        if st.session_state.get("backend_available", False):
            # Update conversation title in backend
            api_client = get_backend_client()
            api_client.update_conversation(
                st.session_state.multimodal_chat_id, summary
            )
        else:
            # Save to local storage
            joblib.dump(past_chats, "data/multimodal_past_chats_list")

    # Save messages to backend if available, otherwise use local storage
    if st.session_state.get("backend_available", False):
        # Save to backend database
        user_id = st.session_state.get("backend_user_id")
        conversation_id = st.session_state.multimodal_chat_id

        # For backend text chat, messages are already saved by the API
        # For local processing (files, images), we need to save manually
        if (
            files_data
            or is_image_generation
            or is_image_editing
            or use_search
            or use_url_context
            or use_combined
        ):
            # Save user message manually (for file/image processing)
            save_message_to_backend(
                user_id=user_id,
                conversation_id=conversation_id,
                role="user",
                content=prompt,
                metadata={"has_files": bool(files_data)},
            )

            # Save assistant response manually
            save_message_to_backend(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                metadata={
                    "grounding_metadata": st.session_state.get(
                        "multimodal_current_grounding_metadata"
                    ),
                    "url_context_metadata": st.session_state.get(
                        "multimodal_current_url_context_metadata"
                    ),
                    "images": bool(
                        "generated_images" in st.session_state
                        and st.session_state.generated_images
                    ),
                },
            )

        # Save generated images to backend storage
        if "generated_images" in st.session_state and st.session_state.generated_images:
            for i, image in enumerate(st.session_state.generated_images):
                # Convert image to bytes
                buf = BytesIO()
                image.save(buf, format="PNG", optimize=False, compress_level=0)
                image_data = buf.getvalue()

                # Save to backend storage
                filename = f"generated_image_{int(time.time())}_{i}.png"
                image_url = save_image_to_backend(
                    user_id, conversation_id, image_data, filename
                )
                if image_url:
                    st.success(f"✅ Image saved to backend: {filename}")
    else:
        # Fall back to local storage
        joblib.dump(
            st.session_state.multimodal_messages,
            f"data/multimodal_{st.session_state.multimodal_chat_id}-st_messages",
        )

        joblib.dump(
            st.session_state.multimodal_gemini_history,
            f"data/multimodal_{st.session_state.multimodal_chat_id}-gemini_messages",
        )

    # Clean up temporary generated images from session state
    if "generated_images" in st.session_state:
        del st.session_state.generated_images

    # Clean up grounding metadata from session state
    if "multimodal_current_grounding_metadata" in st.session_state:
        del st.session_state.multimodal_current_grounding_metadata

    # Clean up URL context metadata from session state
    if "multimodal_current_url_context_metadata" in st.session_state:
        del st.session_state.multimodal_current_url_context_metadata

    # Force a rerun to update the sidebar with the new chat
    st.rerun()

# Show helpful tips if no messages yet and not currently processing
if (
    not st.session_state.multimodal_messages
    and not st.session_state.get("multimodal_processing", False)
    and not st.session_state.get("multimodal_temp_hide_suggestions", False)
):
    st.markdown("### 🚀 Welcome to Multimodal Chat!")
    st.info(
        """
    **What you can do:**
    - 💬 **Text Chat**: Ask questions, get explanations, have conversations
    - 🌐 **Web Search**: Get real-time information with "What's the latest news about..." or "Current stock price of..."
    - � **URL Analysis**: Paste URLs to analyze, summarize, or extract information from web pages
    - �📷 **Image Analysis**: Upload images and ask questions about them
    - 📄 **PDF Analysis**: Upload PDFs and ask questions about the content
    - 📝 **Text File Analysis**: Upload text files for analysis
    - 🎨 **Image Generation**: Create images by asking "generate an image of..." or "create a picture of..."
    - ✏️ **Image Editing**: Upload images and edit them with prompts like "change the background to blue" or "make it anime style"
    - 🔄 **Mixed Mode**: Combine text, images, documents, URL analysis, and image generation in one conversation
    
    **Tips:**
    - Upload files first using the sidebar for analysis
    - You can upload multiple files at once
    - Paste URLs directly in your messages for instant analysis
    - Ask specific questions about your uploaded content or URLs
    - Mix different types of content in the same conversation
    - For image generation, use phrases like "generate an image", "create a picture", "draw", etc.
    - For image editing, upload an image first, then ask to "edit", "change", "modify", or "transform" it
    - For current information, ask about "latest", "recent", "current" events and the AI will search the web
    - For URL analysis, try phrases like "summarize this article: [URL]" or "compare these pages: [URL1] and [URL2]"
    - **Note**: URL analysis is experimental - works best with standard web pages, news articles, and blogs
    - Citations [1], [2], etc. refer to sources shown in the "Search Details" section below responses
    - URLs analyzed are shown in the "URL Analysis Details" section below responses
    """
    )
