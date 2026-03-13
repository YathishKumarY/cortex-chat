from dotenv import load_dotenv
import os
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
import time

# Load environment variables
load_dotenv()

# Remove st.set_page_config since it's already set in main.py

# Configure Gemini API
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except:
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    except:
        st.error("Please set your GEMINI_API_KEY in secrets.toml or .env file")
        st.stop()

AI_AVATAR_ICON = "🎨"


def generate_image_from_text(prompt):
    """Generate an image from a text prompt using Gemini."""
    try:
        response = client.models.generate_content(
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
                image = Image.open(BytesIO(part.inline_data.data))
                generated_images.append(image)

        return text_response, generated_images

    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        return None, []


def edit_image_with_text(prompt, uploaded_image):
    """Edit an uploaded image based on text prompt using Gemini."""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[prompt, uploaded_image],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        text_response = ""
        generated_images = []

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text
            elif part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                generated_images.append(image)

        return text_response, generated_images

    except Exception as e:
        st.error(f"Error editing image: {str(e)}")
        return None, []


# Streamlit UI
st.header("🎨 Gemini Image Generation")
st.markdown(
    "Generate and edit images using Google's Gemini 2.0 Flash Preview Image Generation model"
)

# Create tabs for different modes
tab1, tab2, tab3 = st.tabs(["Text to Image", "Image Editing", "Chat History"])

with tab1:
    st.subheader("Generate Images from Text")
    st.markdown(
        "Describe what you want to create and Gemini will generate an image for you."
    )

    # Chat input for image generation
    text_prompt = st.chat_input(
        "Describe the image you want to generate... e.g., A 3D rendered image of a pig with wings and a top hat flying over a happy futuristic sci-fi city with lots of greenery"
    )

    if text_prompt:
        with st.spinner("Generating image... This may take a few seconds."):
            text_response, images = generate_image_from_text(text_prompt)

            if images:
                st.success("Image generated successfully!")

                # Display text response if any
                if text_response:
                    st.markdown("**AI Response:**")
                    st.markdown(text_response)

                # Display generated images
                st.markdown("**Generated Image(s):**")
                for i, image in enumerate(images):
                    st.image(
                        image, caption=f"Generated Image {i+1}", use_column_width=True
                    )

                    # Provide download option
                    buf = BytesIO()
                    image.save(buf, format="PNG")
                    byte_im = buf.getvalue()

                    st.download_button(
                        label=f"Download Image {i+1}",
                        data=byte_im,
                        file_name=f"gemini_generated_image_{i+1}_{int(time.time())}.png",
                        mime="image/png",
                    )

with tab2:
    st.subheader("Edit Images with Text")
    st.markdown("Upload an image and describe how you want to modify it.")

    # File uploader for image editing
    uploaded_file = st.file_uploader(
        "Upload an image to edit:",
        type=["png", "jpg", "jpeg"],
        help="Supported formats: PNG, JPG, JPEG",
    )

    if uploaded_file:
        # Display uploaded image
        uploaded_image = Image.open(uploaded_file)
        st.image(uploaded_image, caption="Original Image", use_column_width=True)

        # Text input for editing instructions
        edit_prompt = st.text_area(
            "Describe how you want to edit the image:",
            placeholder="e.g., Add a llama next to me, Change the background to a beach scene, Make it look like a painting",
            height=100,
        )

        edit_button = st.button("✨ Edit Image", type="primary")

        if edit_button and edit_prompt:
            with st.spinner("Editing image... This may take a few seconds."):
                text_response, edited_images = edit_image_with_text(
                    edit_prompt, uploaded_image
                )

                if edited_images:
                    st.success("Image edited successfully!")

                    # Display text response if any
                    if text_response:
                        st.markdown("**AI Response:**")
                        st.markdown(text_response)

                    # Display edited images
                    st.markdown("**Edited Image(s):**")
                    for i, image in enumerate(edited_images):
                        st.image(
                            image, caption=f"Edited Image {i+1}", use_column_width=True
                        )

                        # Provide download option
                        buf = BytesIO()
                        image.save(buf, format="PNG")
                        byte_im = buf.getvalue()

                        st.download_button(
                            label=f"Download Edited Image {i+1}",
                            data=byte_im,
                            file_name=f"gemini_edited_image_{i+1}_{int(time.time())}.png",
                            mime="image/png",
                        )
        elif edit_button and not edit_prompt:
            st.warning("Please describe how you want to edit the image.")

with tab3:
    st.subheader("Generation History")
    st.markdown("Your image generation history will appear here.")

    # Initialize session state for history
    if "generation_history" not in st.session_state:
        st.session_state.generation_history = []

    if st.session_state.generation_history:
        for i, entry in enumerate(reversed(st.session_state.generation_history)):
            with st.expander(
                f"Generation {len(st.session_state.generation_history) - i}: {entry['prompt'][:50]}..."
            ):
                st.markdown(f"**Prompt:** {entry['prompt']}")
                st.markdown(f"**Generated at:** {entry['timestamp']}")
                if entry.get("image"):
                    st.image(entry["image"], caption="Generated Image")
    else:
        st.info("No generation history yet. Generate some images to see them here!")

# Sidebar with tips and information
with st.sidebar:
    st.markdown("### 💡 Tips for Better Results")
    st.markdown(
        """
    **For Text-to-Image:**
    - Be specific and descriptive
    - Include style preferences (e.g., "photorealistic", "cartoon", "oil painting")
    - Mention colors, lighting, and composition
    - Try phrases like "generate an image" for better results
    
    **For Image Editing:**
    - Clearly describe what you want to change
    - Be specific about additions or modifications
    - Consider the existing elements in the image
    """
    )

    st.markdown("### ⚠️ Limitations")
    st.markdown(
        """
    - Best performance with English prompts
    - May sometimes generate text-only responses
    - Image generation may not always trigger
    - All generated images include SynthID watermarks
    """
    )

    st.markdown("### 🔧 Model Information")
    st.markdown(
        """
    **Text/Chat Models:** gemini-2.5-pro
    **Image Generation:** gemini-2.0-flash-preview-image-generation
    
    Using Google's latest models that can:
    - Generate images from text descriptions
    - Edit existing images with text instructions
    - Maintain conversational context
    - Advanced reasoning and thinking capabilities
    """
    )
