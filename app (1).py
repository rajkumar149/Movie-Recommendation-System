import streamlit as st
import pymongo
import pandas as pd
import requests
import pickle
import hashlib
import webbrowser
from datetime import datetime
import streamlit.components.v1 as components

# MongoDB setup
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client['movie_recommender']
users_collection = db['users']
favorites_collection = db['favorites']
comments_collection = db['comments']
movie_collection=db['movie_links']

# Movie recommendation functions
def fetch_poster(movie_id):
    response = requests.get(f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=a143c5ff9eaf8f01218029148cba86cd&language=en-US')
    data = response.json()
    return "https://image.tmdb.org/t/p/w500/" + data['poster_path']

def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:7]

    recommended_movies = []
    recommended_movies_posters = []
    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movies.append(movies.iloc[i[0]].title)
        recommended_movies_posters.append(fetch_poster(movie_id))
    return recommended_movies, recommended_movies_posters

# Load movie data
movies_dict = pickle.load(open('movie_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

# Streamlit app
st.title('Movie Recommender System')

# User Authentication
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    user = users_collection.find_one({"username": username})
    if user and user['password'] == hash_password(password):
        return True
    return False

def register_user(username, password):
    if users_collection.find_one({"username": username}):
        return False
    users_collection.insert_one({"username": username, "password": hash_password(password)})
    return True

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['show_register'] = False

def show_login_form():
    st.subheader("Login")
    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button(label='Login')
        if login_button:
            if authenticate(username, password):
                st.session_state['authenticated'] = True
                st.session_state['username'] = username
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")
    if st.button("Don't have an account? Register"):
        st.session_state['show_register'] = True
        st.experimental_rerun()

def show_register_form():
    st.subheader("Register")
    with st.form(key='register_form'):
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        register_button = st.form_submit_button(label='Register')
        if register_button:
            if register_user(new_username, new_password):
                st.success("User registered successfully!")
                st.session_state['show_register'] = False
                st.experimental_rerun()
            else:
                st.error("Username already exists")
    if st.button("Already have an account? Login"):
        st.session_state['show_register'] = False
        st.experimental_rerun()

if not st.session_state['authenticated']:
    placeholder = st.empty()
    with placeholder.container():
        if st.session_state['show_register']:
            show_register_form()
        else:
            show_login_form()
else:
    st.sidebar.write(f"Welcome, {st.session_state['username']}")
    
    if st.sidebar.button('Logout'):
        st.session_state['authenticated'] = False
        st.session_state['username'] = None
        st.experimental_rerun()

    selected_movie_name = st.selectbox('Select a movie:', movies['title'].values)

    if st.button('Recommend'):
        st.session_state.pop('selected_movie', None)
        st.session_state.pop('selected_movie_poster', None)
        names, posters = recommend(selected_movie_name)
        st.session_state['recommendations'] = names
        st.session_state['posters'] = posters
        st.experimental_rerun()

    if 'recommendations' in st.session_state:
        names = st.session_state['recommendations']
        posters = st.session_state['posters']
        cols = st.columns(3)
        for i in range(len(names)):
            with cols[i % 3]:
                st.header(names[i])
                st.image(posters[i])
                if st.button('Select', key=names[i]):
                    st.session_state['selected_movie'] = names[i]
                    st.session_state['selected_movie_poster'] = posters[i]
                    st.session_state.pop('recommendations', None)  # Clear recommendations
                    st.session_state.pop('posters', None)  # Clear posters
                    st.experimental_rerun()

    if 'selected_movie' in st.session_state:
        st.header(st.session_state['selected_movie'])
        st.image(st.session_state['selected_movie_poster'])

        movie_info = movie_collection.find_one({"title": st.session_state['selected_movie']})
        if movie_info and 'streaming_platforms' in movie_info:
            streaming_platforms = movie_info['streaming_platforms']
            
            # Display buttons side by side using columns
            num_platforms = len(streaming_platforms)
            cols = st.columns(num_platforms)
            for i, (platform, link) in enumerate(streaming_platforms.items()):
                with cols[i]:
                    if st.button(platform, key=f'{st.session_state["selected_movie"]}_{platform}_button'):
                        # Redirect to the streaming platform link
                        webbrowser.open_new_tab(link)
        
        # Function to display comments
        def display_comments():
            st.write("Comments:")
            # Fetch the latest 5 comments for the selected movie
            comments = comments_collection.find({"movie_title": st.session_state['selected_movie']}).sort("timestamp", -1).limit(5)
            for comment in comments:
                timestamp = comment.get('timestamp', 'No timestamp')
                st.write(f"{comment['username']}: {comment['text']} ({timestamp})")
        # Display the comments
        display_comments()

        # Add a comment
        comment_text = st.text_area("Add a comment")
        if st.button('Comment'):
            comments_collection.insert_one({
                "username": st.session_state['username'],
                "movie_title": st.session_state['selected_movie'],
                "text": comment_text,
                "timestamp": datetime.now()
            })
            st.success("Comment added!")
            st.experimental_rerun()

        # Add to favorites
        if st.button('Add to Favorites'):
            if favorites_collection.find_one({"username": st.session_state['username'], "movie_title": st.session_state['selected_movie']}):
                st.warning(f"{st.session_state['selected_movie']} is already in your favorite list!")
            else:
                favorites_collection.insert_one({"username": st.session_state['username'], "movie_title": st.session_state['selected_movie']})
                st.success(f"{st.session_state['selected_movie']} added to your favorite list!")

    st.sidebar.subheader("Favorite Movies")
    username = st.session_state.get('username', 'default_user')  # Replace 'default_user' with appropriate fallback
    favorite_movies = favorites_collection.find({"username": username})
    favorite_movie_titles = [fav['movie_title'] for fav in favorite_movies]
    for fav in favorite_movie_titles:
        col1, col2 = st.sidebar.columns([4, 1])
        col1.write(fav)
        if col2.button("X", key=f"remove_{fav}"):
            favorites_collection.delete_one({"username": username, "movie_title": fav})
            st.experimental_rerun()  # Trigger a rerun to update the UI
