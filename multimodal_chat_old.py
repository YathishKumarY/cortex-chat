import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
from PyPDF2 import PdfReader
import PyPDF2
from google import genai as google_genai
from google.genai import types
from io import BytesIO
import re
import random as rd
import urllib.parse

# Backend integration
try:
    from backend_client import (
        load_messages_from_backend, save_message_pair_to_backend,
        get_conversations_from_backend, get_or_create_conversation_session,
        delete_conversation_from_backend
    )
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False

load_dotenv()

# Remove st.set_page_config since it's already set in main.py

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
st.session_state.model = genai.GenerativeModel("gemini-2.0-flash")

# Configure Gemini API for image generation and search
try:
    image_gen_client = google_genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    search_client = google_genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except:
    try:
        image_gen_client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        search_client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    except:
        image_gen_client = None
        search_client = None
        st.warning("Image generation and search unavailable - please set GEMINI_API_KEY properly")

# Use a consistent identifier for new chats
NEW_CHAT_KEY = "NEW_MULTIMODAL_CHAT_SESSION"

st.header("🤖 Gemini Multimodal ChatBot")
st.markdown("*Chat with text, images, and PDFs all in one place*")

AI_AVATAR_ICON = "🤖"


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
            "gemini-2.0-flash"
        )  # Use faster model for summaries

        prompt = f"""Generate a very short (3-5 words) title for this conversation:

{conversation_text}

Requirements:
- Maximum 5 words
- Descriptive and specific
- No generic phrases like "chat" or "conversation"
- Focus on the main topic or question asked
- Be specific to what the user is asking about

Example formats: "Python coding help", "Recipe recommendations", "Travel planning", "Math homework", "Image analysis help"

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
        # Enhanced prompt for better quality with AI-optimized keywords
        # Use proven quality enhancement terms that work well with AI image generation
        quality_terms = "masterpiece, best quality, ultra detailed, 8k resolution, highly detailed, photorealistic, professional art, sharp focus, vivid colors, intricate details, fine art quality, ultra high resolution"

        # Combine original prompt with quality enhancement
        enhanced_prompt = f"{prompt}, {quality_terms}"

        response = image_gen_client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=enhanced_prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        text_response = ""
        generated_images = []

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text
            elif part.inline_data is not None:
                # Load image with high quality settings
                image = Image.open(BytesIO(part.inline_data.data))

                # Ensure we're working with RGB mode for best quality
                if image.mode != "RGB":
                    image = image.convert("RGB")

                generated_images.append(image)

        return text_response, generated_images

    except Exception as e:
        return f"Error generating image: {str(e)}", []


def edit_image_with_prompt(image, prompt):
    """Edit an uploaded image based on a text prompt using Gemini."""
    if not image_gen_client:
        return (
            "Image editing is not available. Please check your API configuration.",
            [],
        )

    try:
        # Convert PIL image to bytes for API
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_byte_arr = img_byte_arr.getvalue()

        # Enhanced prompt for better editing quality
        edit_prompt = f"Edit this image: {prompt}. Maintain high quality, detailed, 8k resolution, professional editing, sharp focus, vivid colors"

        response = image_gen_client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[
                edit_prompt,
                {"inline_data": {"mime_type": "image/png", "data": img_byte_arr}},
            ],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        text_response = ""
        edited_images = []

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text
            elif part.inline_data is not None:
                # Load edited image with high quality settings
                edited_image = Image.open(BytesIO(part.inline_data.data))

                # Ensure we're working with RGB mode for best quality
                if edited_image.mode != "RGB":
                    edited_image = edited_image.convert("RGB")

                edited_images.append(edited_image)

        return text_response, edited_images

    except Exception as e:
        return f"Error editing image: {str(e)}", []


def detect_image_generation_request(prompt):
    """Use AI to intelligently detect if the user wants image generation."""
    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.0-flash")

        detection_prompt = f"""
        Analyze this user prompt and determine if they want an IMAGE/VISUAL to be GENERATED/CREATED, or if they want TEXT information/conversation.

        User prompt: "{prompt}"

        Rules:
        - If they want ANY visual content created/generated/made (art, picture, image, character, scene, etc.), respond: IMAGE
        - If they want text information, explanations, conversations, analysis, etc., respond: TEXT
        - When in doubt about visual creation requests, lean towards IMAGE

        Examples:
        - "make a zenitsu image" → IMAGE
        - "create naruto artwork" → IMAGE  
        - "draw a sunset" → IMAGE
        - "what is zenitsu's power?" → TEXT
        - "explain naruto's story" → TEXT
        - "tell me about anime" → TEXT

        Respond with only one word: IMAGE or TEXT
        """

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


def detect_image_editing_request(prompt, has_uploaded_images):
    """Use AI to intelligently detect if the user wants to edit an uploaded image."""
    if not has_uploaded_images:
        return False

    try:
        # Create a temporary model for intelligent detection
        detection_model = genai.GenerativeModel("gemini-2.0-flash")

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
        detection_model = genai.GenerativeModel("gemini-2.0-flash")

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
            "latest", "recent", "current", "today", "news", "update", 
            "what happened", "breaking", "this year", "2024", "2025",
            "stock price", "weather", "score", "winner", "election"
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
        url = re.sub(r'[.,;:!?]+$', '', url)
        
        # Add https:// if missing
        if url.startswith('www.'):
            url = 'https://' + url
        
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
        detection_model = genai.GenerativeModel("gemini-2.0-flash")

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
            "summarize", "analyze", "extract", "compare", "what does", "read",
            "content", "information from", "details from", "explain this"
        ]
        return any(keyword in prompt.lower() for keyword in analysis_keywords)


def generate_with_url_context(prompt, urls, model_name="gemini-2.0-flash"):
    """Generate a response using URL context tool."""
    if not search_client or not urls:
        return None, None
    
    try:
        # Define the URL context tool
        url_context_tool = types.Tool(
            url_context=types.UrlContext()
        )

        # Configure generation settings
        config = types.GenerateContentConfig(
            tools=[url_context_tool],
            response_modalities=["TEXT"],
        )

        # Make the request
        response = search_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        return response, response.candidates[0].url_context_metadata if response.candidates else None

    except Exception as e:
        print(f"Error with URL context generation: {e}")
        return None, None


def generate_with_search_and_url_context(prompt, urls=None, model_name="gemini-2.0-flash"):
    """Generate a response using both Google Search and URL context tools."""
    if not search_client:
        return None, None, None
    
    try:
        # Define both tools
        tools = []
        if urls:
            tools.append(types.Tool(url_context=types.UrlContext()))
        tools.append(types.Tool(google_search=types.GoogleSearch()))

        # Configure generation settings
        config = types.GenerateContentConfig(
            tools=tools,
            response_modalities=["TEXT"],
        )

        # Make the request
        response = search_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        grounding_metadata = response.candidates[0].grounding_metadata if response.candidates else None
        url_context_metadata = response.candidates[0].url_context_metadata if response.candidates else None

        return response, grounding_metadata, url_context_metadata

    except Exception as e:
        print(f"Error with search and URL context generation: {e}")
        return None, None, None


def display_url_context_sources(url_context_metadata):
    """Display URL context sources in a nice format."""
    if not url_context_metadata:
        return
    
    try:
        if hasattr(url_context_metadata, 'url_metadata') and url_context_metadata.url_metadata:
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
                
                st.markdown(f"{i}. {status_icon} [{retrieved_url}]({retrieved_url}) - {status_text}")
                    
    except Exception as e:
        print(f"Error displaying URL context sources: {e}")


def serialize_url_context_metadata(url_context_metadata):
    """Convert URL context metadata to a serializable format."""
    if not url_context_metadata:
        return None
    
    try:
        serialized = {}
        
        # Extract URL metadata
        if hasattr(url_context_metadata, 'url_metadata') and url_context_metadata.url_metadata:
            url_data = []
            for url_info in url_context_metadata.url_metadata:
                url_data.append({
                    'retrieved_url': url_info.retrieved_url,
                    'url_retrieval_status': str(url_info.url_retrieval_status)
                })
            serialized['url_metadata'] = url_data
        
        return serialized if serialized else None
    except Exception as e:
        print(f"Error serializing URL context metadata: {e}")
        return None


def display_serialized_url_context_sources(serialized_metadata):
    """Display URL context sources from serialized metadata."""
    if not serialized_metadata:
        return
    
    try:
        if 'url_metadata' in serialized_metadata:
            st.markdown("**🔗 URLs Analyzed:**")
            for i, url_data in enumerate(serialized_metadata['url_metadata'], 1):
                retrieved_url = url_data['retrieved_url']
                status = url_data['url_retrieval_status']
                
                # Show status with appropriate icon
                if "SUCCESS" in status:
                    status_icon = "✅"
                    status_text = "Successfully retrieved"
                else:
                    status_icon = "❌"
                    status_text = f"Failed: {status}"
                
                st.markdown(f"{i}. {status_icon} [{retrieved_url}]({retrieved_url}) - {status_text}")
                    
    except Exception as e:
        print(f"Error displaying serialized URL context sources: {e}")


def add_citations_to_text(text, grounding_metadata):
    """Add inline citations to the response text using grounding metadata."""
    if not grounding_metadata or not hasattr(grounding_metadata, 'grounding_supports'):
        return text
    
    try:
        supports = grounding_metadata.grounding_supports
        chunks = grounding_metadata.grounding_chunks
        
        if not supports or not chunks:
            return text

        # Sort supports by end_index in descending order to avoid shifting issues when inserting
        sorted_supports = sorted(supports, key=lambda s: s.segment.end_index, reverse=True)

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
        if hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
            st.markdown("**🔍 Search Queries Used:**")
            for i, query in enumerate(grounding_metadata.web_search_queries, 1):
                st.markdown(f"{i}. `{query}`")
        
        # Display sources
        if hasattr(grounding_metadata, 'grounding_chunks') and grounding_metadata.grounding_chunks:
            st.markdown("**📚 Sources:**")
            for i, chunk in enumerate(grounding_metadata.grounding_chunks, 1):
                if hasattr(chunk, 'web') and chunk.web:
                    title = chunk.web.title if hasattr(chunk.web, 'title') else "Unknown Source"
                    uri = chunk.web.uri if hasattr(chunk.web, 'uri') else "#"
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
        if hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
            serialized['web_search_queries'] = list(grounding_metadata.web_search_queries)
        
        # Extract grounding chunks (sources)
        if hasattr(grounding_metadata, 'grounding_chunks') and grounding_metadata.grounding_chunks:
            chunks = []
            for chunk in grounding_metadata.grounding_chunks:
                if hasattr(chunk, 'web') and chunk.web:
                    chunk_data = {
                        'title': chunk.web.title if hasattr(chunk.web, 'title') else "Unknown Source",
                        'uri': chunk.web.uri if hasattr(chunk.web, 'uri') else "#"
                    }
                    chunks.append(chunk_data)
            serialized['grounding_chunks'] = chunks
        
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
        if 'web_search_queries' in serialized_metadata:
            st.markdown("**🔍 Search Queries Used:**")
            for i, query in enumerate(serialized_metadata['web_search_queries'], 1):
                st.markdown(f"{i}. `{query}`")
        
        # Display sources
        if 'grounding_chunks' in serialized_metadata:
            st.markdown("**📚 Sources:**")
            for i, chunk in enumerate(serialized_metadata['grounding_chunks'], 1):
                title = chunk.get('title', 'Unknown Source')
                uri = chunk.get('uri', '#')
                st.markdown(f"[{i}] [{title}]({uri})")
                    
    except Exception as e:
        print(f"Error displaying serialized search sources: {e}")


def generate_with_search(prompt, model_content=None, model_name="gemini-2.0-flash"):
    """Generate a response using Google Search grounding."""
    if not search_client:
        return None, None
    
    try:
        # Define the grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        # Configure generation settings
        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )

        # Use model_content if provided, otherwise just the prompt
        content_to_send = model_content if model_content else prompt

        # Make the request
        response = search_client.models.generate_content(
            model=model_name,
            contents=content_to_send,
            config=config,
        )

        return response, response.candidates[0].grounding_metadata if response.candidates else None

    except Exception as e:
        print(f"Error with search generation: {e}")
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
        word in suggestion_lower for word in ["url", "webpage", "website", "link", "compare", "page"]
    ):
        return "🔗"
    elif any(
        word in suggestion_lower for word in ["latest", "current", "news", "recent", "today", "stock", "weather", "breaking"]
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

"""Conversation history mapping contract

past_chats in session_state MUST be a dict: conversation_id -> title
Special new chat placeholder key: NEW_CHAT_KEY (value: 'NEW_MULTIMODAL_CHAT_SESSION')
Legacy persisted formats (title->id or {"New Chat":"NEW_CHAT"}) are auto-normalized.
"""

# Load / normalize past chats mapping
if 'past_chats' not in st.session_state:
    loaded = {}
    if BACKEND_AVAILABLE and st.session_state.get("backend_user_id"):
        try:
            loaded = get_conversations_from_backend(st.session_state.backend_user_id)
        except Exception as e:
            st.error(f"Error loading conversations: {e}")
            loaded = {"NEW_CHAT": "New Chat"}
    else:
        # Fallback local persisted list (may be legacy)
        try:
            loaded = joblib.load("data/multimodal_past_chats_list")
        except Exception:
            loaded = {"NEW_CHAT": "New Chat"}

    # Normalization heuristics
    # Case 1: keys look like titles and values look like IDs -> invert
    try:
        if loaded:
            sample_k, sample_v = next(iter(loaded.items()))
            import re
            uuid_pattern = re.compile(r"^[0-9a-fA-F-]{8,}$")
            if (sample_k.lower() == 'new chat' or not uuid_pattern.match(sample_k)) and uuid_pattern.match(str(sample_v)):
                loaded = {v: k for k, v in loaded.items()}
    except Exception:
        pass

    # Ensure placeholder exists in normalized form
    if "NEW_CHAT" not in loaded:
        loaded["NEW_CHAT"] = "New Chat"

    st.session_state.past_chats = loaded

past_chats = st.session_state.past_chats  # id -> title mapping

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
    if search_client:
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
    if search_client:
        if url_context_enabled:
            st.success("🟢 URL analysis is enabled and ready")
        else:
            st.info("🔵 URL analysis is available but disabled")
    else:
        st.error("🔴 URL analysis unavailable - check API configuration")

    st.markdown("💡 **Tip:** Paste URLs directly in your messages for analysis!")

    st.markdown("---")

    # Filter past_chats to include available conversations
    available_chats = {}
    for chat_id, title in past_chats.items():
        # Skip synthetic new placeholder key; real NEW_CHAT placeholder is "NEW_CHAT"
        if chat_id in [NEW_CHAT_KEY]:
            continue
        # Always include existing real chats (exclude NEW_CHAT placeholder except when active)
        if chat_id == "NEW_CHAT":
            if st.session_state.multimodal_chat_id == "NEW_CHAT":
                available_chats[chat_id] = title
            continue
        available_chats[chat_id] = title

    # Sort chat IDs by timestamp (latest first) - extract timestamp from chat_id
    def get_chat_timestamp(chat_id):
        # Prefer creation time encoded in UUID v1? If not, fallback numeric parse else 0
        try:
            return float(chat_id)
        except Exception:
            return 0

    sorted_chat_ids = sorted(
        available_chats.keys(), key=get_chat_timestamp, reverse=True
    )

    # Show dropdown only if there are history chats available
    if available_chats:
        st.markdown("### 💬 Chat History")

        # Build a display mapping: id -> friendly label (Title • short id)
        display_map = {}
        for cid, title in available_chats.items():
            if cid in ["NEW_CHAT", NEW_CHAT_KEY]:
                continue
            short_id = cid.split('-')[0][:8] if '-' in cid else cid[:8]
            # Avoid duplicating short id if title already unique enough
            if title.lower() == "new chat" or not title.strip():
                label = f"(Untitled) • {short_id}"
            else:
                label = f"{title} • {short_id}"
            display_map[cid] = label

        # Ordered options (exclude NEW_CHAT placeholder from selection list)
        ordered_ids = [cid for cid in sorted_chat_ids if cid not in ["NEW_CHAT", NEW_CHAT_KEY]]

        # Insert current chat if somehow missing
        if (st.session_state.multimodal_chat_id not in ordered_ids 
            and st.session_state.multimodal_chat_id not in [NEW_CHAT_KEY, "NEW_CHAT"]):
            ordered_ids = [st.session_state.multimodal_chat_id] + ordered_ids

        def _format_func(cid):
            return display_map.get(cid, available_chats.get(cid, "Unknown Chat"))

        # Provide a clearer placeholder
        current_id = st.session_state.get("multimodal_chat_id")
        if current_id in [NEW_CHAT_KEY, "NEW_CHAT", None]:
            index_default = None
        else:
            try:
                index_default = ordered_ids.index(current_id)
            except ValueError:
                index_default = None

        selected_chat = st.selectbox(
            label="Select a conversation:",
            options=ordered_ids,
            index=index_default,
            format_func=_format_func,
            placeholder="Choose a previous conversation…",
            key="multimodal_chat_selector",
        )

        # Update selection
        if selected_chat and selected_chat != current_id:
            st.session_state.multimodal_chat_id = selected_chat
            st.rerun()
        # Provide a compact list view with clickable selection (secondary UI)
        with st.expander("Show all conversations", expanded=False):
            for cid in ordered_ids:
                label = _format_func(cid)
                cols = st.columns([8,2])
                with cols[0]:
                    st.markdown(f"- **{label}**")
                with cols[1]:
                    if st.button("Open", key=f"open_conv_{cid}"):
                        st.session_state.multimodal_chat_id = cid
                        st.rerun()
    else:
        st.info("📝 No chat history yet. Start a new conversation!")

    # Set chat title
    st.session_state.multimodal_chat_title = past_chats.get(
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
if st.session_state.multimodal_chat_id in [NEW_CHAT_KEY, "NEW_CHAT"]:
    # New chat - always start with empty messages
    st.session_state.multimodal_messages = []
    st.session_state.multimodal_gemini_history = []
    # Unset backend conversation ID for new chats
    if "backend_conversation_id" in st.session_state:
        del st.session_state.backend_conversation_id
else:
    # Existing chat - load from backend or local files
    # We should reload messages if the chat has changed.
    if chat_changed:
        try:
            if BACKEND_AVAILABLE and st.session_state.get("backend_user_id"):
                st.session_state.backend_conversation_id = st.session_state.multimodal_chat_id
                backend_messages = load_messages_from_backend(
                    st.session_state.backend_user_id,
                    st.session_state.multimodal_chat_id,
                )
                st.session_state.multimodal_messages = backend_messages or []
                st.session_state.multimodal_gemini_history = []
            else:
                # Legacy fallback
                st.session_state.multimodal_messages = joblib.load(
                    f"data/multimodal_{st.session_state.multimodal_chat_id}-st_messages"
                )
                st.session_state.multimodal_gemini_history = joblib.load(
                    f"data/multimodal_{st.session_state.multimodal_chat_id}-gemini_messages"
                )
        except Exception:
            st.session_state.multimodal_messages = []
            st.session_state.multimodal_gemini_history = []

st.session_state.multimodal_chat = st.session_state.model.start_chat(
    history=st.session_state.multimodal_gemini_history,
)

# Show delete button in top right corner for existing chats (not new chats)
if (
    st.session_state.multimodal_chat_id not in [NEW_CHAT_KEY, "NEW_CHAT"]
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
            # The ID of the chat to delete is the currently selected chat ID
            chat_id_to_delete = st.session_state.multimodal_chat_id
            chat_title_to_delete = past_chats.get(chat_id_to_delete, "this chat")

            try:
                # --- Backend Deletion ---
                if BACKEND_AVAILABLE and st.session_state.get("backend_user_id"):
                    success = delete_conversation_from_backend(
                        st.session_state.backend_user_id,
                        chat_id_to_delete
                    )
                    
                    if not success:
                        st.error(f"Failed to delete chat '{chat_title_to_delete}' from the backend. Please try again.")
                        st.session_state.multimodal_confirm_delete = False
                        st.rerun()
                        return # Stop execution if backend deletion fails
                
                # --- Local State Update ---
                # Remove from past_chats dictionary
                if chat_id_to_delete in past_chats:
                    del past_chats[chat_id_to_delete]

                # --- Legacy Local File Cleanup (optional but good practice) ---
                try:
                    st_messages_file = f"data/multimodal_{chat_id_to_delete}-st_messages"
                    gemini_messages_file = f"data/multimodal_{chat_id_to_delete}-gemini_messages"
                    if os.path.exists(st_messages_file):
                        os.remove(st_messages_file)
                    if os.path.exists(gemini_messages_file):
                        os.remove(gemini_messages_file)
                except OSError:
                    pass # Ignore errors in deleting old local files

                # --- Reset UI to New Chat State ---
                st.session_state.multimodal_chat_id = NEW_CHAT_KEY
                st.session_state.multimodal_current_chat_id = NEW_CHAT_KEY
                st.session_state.multimodal_messages = []
                st.session_state.multimodal_gemini_history = []
                st.session_state.multimodal_confirm_delete = False
                
                # Use a success message that disappears on the next action
                st.toast(f"Chat '{chat_title_to_delete}' deleted successfully!", icon="✅")
                st.rerun()

            except Exception as e:
                st.error(f"An unexpected error occurred while deleting the chat: {str(e)}")
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
    and st.session_state.multimodal_chat_id != NEW_CHAT_KEY
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
                    if st.session_state.multimodal_chat_id in past_chats:
                        past_chats[st.session_state.multimodal_chat_id] = summary
                    st.session_state.multimodal_chat_title = summary
                    
                    # Update title in backend if available
                    if BACKEND_AVAILABLE and st.session_state.get("backend_user_id") and st.session_state.get("backend_conversation_id"):
                        try:
                            # Note: We would need to implement update_conversation_title in backend_client
                            # For now, the title will be updated locally only
                            pass
                        except Exception as e:
                            # Silently handle backend errors
                            pass
                    
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
        with st.chat_message(message["role"], avatar="user"):
            st.markdown(message["content"])
    else:
        with st.chat_message(message["role"], avatar=AI_AVATAR_ICON):
            st.markdown(message["content"])

            # Display search details if this was a search response
            if "grounding_metadata" in message and message["grounding_metadata"]:
                with st.expander("🔍 Search Details", expanded=False):
                    display_serialized_search_sources(message["grounding_metadata"])

            # Display URL context details if this was a URL analysis response
            if "url_context_metadata" in message and message["url_context_metadata"]:
                with st.expander("🔗 URL Analysis Details", expanded=False):
                    display_serialized_url_context_sources(message["url_context_metadata"])

            # Display combined details if both search and URL context were used
            if ("grounding_metadata" in message and message["grounding_metadata"] and
                "url_context_metadata" in message and message["url_context_metadata"]):
                # Override the individual expanders above with a combined one
                with st.expander("🔍🔗 Search & URL Analysis Details", expanded=False):
                    display_serialized_search_sources(message["grounding_metadata"])
                    st.markdown("---")
                    display_serialized_url_context_sources(message["url_context_metadata"])

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
    detected_urls = detect_urls_in_prompt(prompt) if st.session_state.get("multimodal_enable_url_context", True) else []
    
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
        and search_client 
        and detect_url_context_need(prompt, detected_urls)
        and not is_image_generation 
        and not is_image_editing
    )
    
    # Initialize search and combined usage flags
    use_search = False
    use_combined = False

    # Handle new chat creation - consolidate logic
    if st.session_state.multimodal_chat_id in [NEW_CHAT_KEY, "NEW_CHAT"]:
        # Create new conversation in backend
        if BACKEND_AVAILABLE and st.session_state.get("backend_user_id"):
            try:
                conversation_id = get_or_create_conversation_session(
                    st.session_state.backend_user_id, 
                    "New Chat", 
                    past_chats
                )
                if conversation_id:
                    st.session_state.multimodal_chat_id = conversation_id
                    st.session_state.backend_conversation_id = conversation_id
                    # Add to past_chats dict with "New Chat" as title initially
                    past_chats[conversation_id] = "New Chat"
                else:
                    # Backend failed, use fallback
                    st.session_state.multimodal_chat_id = f"local_{int(time.time())}"
            except Exception as e:
                st.error(f"Error creating conversation: {e}")
                st.session_state.multimodal_chat_id = f"local_{int(time.time())}"
        else:
            # Fallback to timestamp-based ID
            st.session_state.multimodal_chat_id = f"local_{int(time.time())}"
    
    # Update tracking variable
    if hasattr(st.session_state, "multimodal_current_chat_id"):
        st.session_state.multimodal_current_chat_id = st.session_state.multimodal_chat_id

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
            name="model",
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
                    st.error(
                        "❌ Failed to generate image. Please try again with a different prompt."
                    )
                    full_response = (
                        text_response
                        if text_response
                        else "I wasn't able to generate an image from your request. Please try rephrasing your prompt or being more specific about what you'd like me to create."
                    )

    elif is_image_editing:
        # Handle image editing
        with st.chat_message(
            name="model",
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
            and search_client 
            and detect_search_need(prompt)
            and not files_data  # Don't use search when analyzing uploaded files
            and not use_url_context  # Don't use search when analyzing URLs
        )
        
        # Determine if we need both search and URL context
        use_combined = (
            use_url_context 
            and st.session_state.get("multimodal_enable_search", True) 
            and search_client
            and detect_search_need(prompt)
        )
        
        if use_combined:
            # Use both search and URL context
            with st.chat_message(name="model", avatar=AI_AVATAR_ICON):
                with st.spinner("Searching the web and analyzing URLs..."):
                    search_response, grounding_metadata, url_context_metadata = generate_with_search_and_url_context(prompt, detected_urls)
                    
                    if search_response and search_response.text:
                        # Add citations to the response text
                        response_text = add_citations_to_text(search_response.text, grounding_metadata)
                        
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
                        st.session_state.multimodal_current_grounding_metadata = grounding_metadata
                        st.session_state.multimodal_current_url_context_metadata = url_context_metadata
                    else:
                        st.warning("⚠️ Search and URL analysis encountered issues - some sites may be restricted during the experimental phase. Continuing with regular chat.")
                        # Fall back to regular chat
                        use_combined = False
                        use_search = False
                        use_url_context = False
                        st.session_state.multimodal_current_grounding_metadata = None
                        st.session_state.multimodal_current_url_context_metadata = None
        
        elif use_url_context:
            # Use URL context only
            with st.chat_message(name="model", avatar=AI_AVATAR_ICON):
                with st.spinner("Analyzing URL content..."):
                    url_response, url_context_metadata = generate_with_url_context(prompt, detected_urls)
                    
                    if url_response and url_response.text:
                        st.markdown(url_response.text)
                        
                        # Display URL sources if available
                        if url_context_metadata:
                            with st.expander("🔗 URL Analysis Details", expanded=False):
                                display_url_context_sources(url_context_metadata)
                        
                        full_response = url_response.text
                        # Store URL context metadata
                        st.session_state.multimodal_current_url_context_metadata = url_context_metadata
                        st.session_state.multimodal_current_grounding_metadata = None
                    else:
                        st.warning("⚠️ URL analysis failed - some sites may be restricted during the experimental phase. Continuing with regular chat.")
                        # Fall back to regular chat
                        use_url_context = False
                        st.session_state.multimodal_current_url_context_metadata = None
        
        elif use_search:
            # Use search-enabled generation only
            with st.chat_message(name="model", avatar=AI_AVATAR_ICON):
                with st.spinner("Searching the web for current information..."):
                    search_response, grounding_metadata = generate_with_search(prompt)
                    
                    if search_response and search_response.text:
                        # Add citations to the response text
                        response_text = add_citations_to_text(search_response.text, grounding_metadata)
                        
                        st.markdown(response_text)
                        
                        # Display search sources if available
                        if grounding_metadata:
                            with st.expander("🔍 Search Details", expanded=False):
                                display_search_sources(grounding_metadata)
                        
                        full_response = response_text
                        # Store grounding metadata for this search
                        st.session_state.multimodal_current_grounding_metadata = grounding_metadata
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
    if (use_search or use_combined) and st.session_state.get("multimodal_current_grounding_metadata"):
        serialized_metadata = serialize_grounding_metadata(st.session_state.multimodal_current_grounding_metadata)
        if serialized_metadata:
            message_data["grounding_metadata"] = serialized_metadata

    # Add URL context metadata for URL analysis responses
    if (use_url_context or use_combined) and st.session_state.get("multimodal_current_url_context_metadata"):
        serialized_url_metadata = serialize_url_context_metadata(st.session_state.multimodal_current_url_context_metadata)
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
        and st.session_state.multimodal_chat.history
    ):
        # Use the complete response from chat history if available (only for regular chat)
        try:
            final_content = st.session_state.multimodal_chat.history[-1].parts[0].text
            message_data["content"] = final_content
        except:
            pass

    st.session_state.multimodal_messages.append(message_data)

    # Save to backend if available (for regular text conversations)
    if (BACKEND_AVAILABLE 
        and st.session_state.get("backend_user_id") 
        and st.session_state.get("backend_conversation_id")
        and not is_image_generation 
        and not is_image_editing
        and len(st.session_state.multimodal_messages) >= 2  # Ensure we have both user and AI message
    ):
        try:
            # Get the user message (second to last message) and AI response (last message)
            user_msg = st.session_state.multimodal_messages[-2]
            ai_msg = st.session_state.multimodal_messages[-1]
            
            if user_msg["role"] == "user" and ai_msg["role"] == "model":
                # Save both messages to backend
                save_message_pair_to_backend(
                    st.session_state.backend_user_id,
                    st.session_state.backend_conversation_id,
                    user_msg["content"],
                    ai_msg["content"]
                )
        except Exception as e:
            # Silently handle backend errors to not disrupt the chat experience
            pass

    # Clear processing flag now that message is added
    st.session_state.multimodal_processing = False

    # Update gemini history (only for regular chat without search/URL context, not image generation or editing)
    if not is_image_generation and not is_image_editing and not use_search and not use_url_context and not use_combined:
        st.session_state.multimodal_gemini_history = (
            st.session_state.multimodal_chat.history
        )

    # Generate summary after first AI response for new chats
    if (
        len(st.session_state.multimodal_messages) >= 2
        and st.session_state.multimodal_chat_id not in [NEW_CHAT_KEY, "NEW_CHAT"]
        and (
            # Either it's in past_chats with "New Chat" title
            (st.session_state.multimodal_chat_id in past_chats and past_chats[st.session_state.multimodal_chat_id] == "New Chat")
            or
            # Or it's a new conversation that needs a title (for backend conversations)
            (BACKEND_AVAILABLE and st.session_state.get("backend_conversation_id") == st.session_state.multimodal_chat_id)
        )
    ):
        # Generate summary immediately after first response for new chats
        summary = generate_chat_summary(st.session_state.multimodal_messages)
        if summary and summary != "New Chat":
            # Update local past_chats
            past_chats[st.session_state.multimodal_chat_id] = summary
            st.session_state.multimodal_chat_title = summary
            
            # Update title in backend if available - we'll implement this function
            if BACKEND_AVAILABLE and st.session_state.get("backend_user_id") and st.session_state.get("backend_conversation_id"):
                try:
                    # For now, just update locally. Later we can add backend title update API
                    pass
                except Exception as e:
                    # Silently handle backend errors
                    pass
        
        # Update title in backend if available
        if BACKEND_AVAILABLE and st.session_state.get("backend_user_id") and st.session_state.get("backend_conversation_id"):
            try:
                # Note: We would need to implement update_conversation_title in backend_client
                # For now, the title will be updated locally only
                pass
            except Exception as e:
                # Silently handle backend errors
                pass

    # Messages are already saved to backend earlier in the code
    # No need to save to local files anymore
    # The following joblib.dump calls are replaced with backend persistence

    # Clean up temporary generated images from session state
    if "generated_images" in st.session_state:
        del st.session_state.generated_images

    # Clean up grounding metadata from session state
    if "multimodal_current_grounding_metadata" in st.session_state:
        del st.session_state.multimodal_current_grounding_metadata

    # Clean up URL context metadata from session state
    if "multimodal_current_url_context_metadata" in st.session_state:
        del st.session_state.multimodal_current_url_context_metadata

    # Messages are already saved to backend earlier in the code
    # No need to save to local files anymore
    # The following joblib.dump calls are replaced with backend persistence
