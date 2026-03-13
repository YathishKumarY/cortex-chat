import os
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import re
import random as rd

# Load environment variables
load_dotenv()

# Configure the API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

suggestion_count = int(os.getenv("SUGGESTION_COUNT"))

# Set up the Streamlit page
st.set_page_config("Gemini LLM ChatBot", page_icon="favicon.ico", layout="wide", initial_sidebar_state="auto")

st.header("✨ Gemini LLM ChatBot" )

st.session_state.model = genai.GenerativeModel('gemini-1.5-flash')

prompt_ideas = ["latest trends", "recent news", "tips and tricks", "new technologies", "sports", "culture", "fashion trends", "food", "music", "movies", "books", "travel", "photography", "nature", "animals", "science", "history", "technology", "education", "health", "fitness", "lifestyle", "family", "friendship", "work", "career", "business", "entrepreneurship", "marketing", "social media", "communication", "creativity", "innovation", "leadership", "productivity", "happiness", "well-being", "mental health", "stress", "self-improvement", "personal growth", "suggest youtube videos", "surprise ideas", "prank ideas", "funny jokes", "riddles", "brainteasers", "puzzles", "games", "challenges", "quizzes","facts", "statistics", "research", "studies", "experiments", "surveys", "interviews", "debates", "discussions", "conversations", "negotiation", "conflict resolution", "problem-solving", "decision-making", "critical thinking", "creativity", "innovation", "imagination", "visualization", "trip planning", "organization", "time management", "plan trips", "find recipes", "learn new languages", "practice coding", "write stories", "draw pictures", "compose music", "play instruments", "songs", "paint", "sculpt", "photograph", "film", "edit videos", "coding tips and tricks"]

if "prompt_ideas" not in st.session_state:
    st.session_state.prompt_ideas = rd.choices(prompt_ideas, k=suggestion_count)

if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

st.session_state.prompt = st.chat_input("Enter your message here", key="chat_input")

def generate_suggested_prompts(input):
    # Generate suggestions using the Gemini API
    chat_session = st.session_state.model.start_chat()

    # Send a message to generate suggestions
    response = chat_session.send_message(f"Please provide {suggestion_count} creative and engaging suggestion prompts based on the topic: '{input}'. Each suggestion should be concise and fit within 80 tokens. give prompts in first person perspective.")

    # Extract the suggestions from the response
    suggestions = response.candidates[0].content.parts[0].text.split("\n")

    return suggestions

def remove_numbered_bullets(bulleted_list):
    cleaned_list = []
    for item in bulleted_list:
        # Remove numbered bullets using regex
        cleaned_item = re.sub(r'^\d+\.\s*', '', item)
        cleaned_list.append(cleaned_item)
    return cleaned_list

# Generate and display suggestions
input_for_suggestion = ", ".join(st.session_state.prompt_ideas)
st.write(f"Based on your input: {input_for_suggestion}")
raw_suggestions = generate_suggested_prompts(input_for_suggestion)
st.write("Here are some suggested prompts:")
st.session_state.suggestions = remove_numbered_bullets(raw_suggestions)
st.session_state.suggestions = [item for item in st.session_state.suggestions if item]
st.session_state.suggestions = st.session_state.suggestions[-suggestion_count:]

row = st.columns(suggestion_count, gap="large")


def handle_click(suggestion):
    st.session_state.prompt = suggestion

for i, col in enumerate(row):
    with col:
        if st.session_state.suggestions:
            st.button(f"{st.session_state.suggestions[i]}", on_click=handle_click, args=(st.session_state.suggestions[i],))

if st.session_state.prompt:
    chat_session = st.session_state.model.start_chat()
    response = chat_session.send_message(st.session_state.prompt)
    st.write(response.candidates[0].content.parts[0].text)