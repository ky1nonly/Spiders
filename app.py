from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
import bcrypt
from google.cloud import vision
import os
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.parse  
import shazamio
from google.oauth2 import service_account
import requests
from youtubesearchpython import VideosSearch
import asyncio
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'mysecret'

# MongoDB configuration
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/webapp")
mongo = PyMongo(app)


mongo = PyMongo(app)
shazam = shazamio.Shazam()
credentials = service_account.Credentials.from_service_account_file(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
vision_client = vision.ImageAnnotatorClient(credentials=credentials)₩
@app.route('/')
def home():
    recommended_playlists = mongo.db.playlists.find().limit(5)
    popular_users = mongo.db.users.find().sort("followers", -1).limit(5)
    return render_template('home.html', recommended_playlists=recommended_playlists, popular_users=popular_users)

@app.route('/profile')
def profile():
    if 'username' in session:
        return f'Logged in as {session["username"]}'
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        login_user = users.find_one({'username': request.form['username']})

        if login_user:
            if bcrypt.checkpw(request.form['password'].encode('utf-8'), login_user['password']):
                session['username'] = request.form['username']
                return redirect(url_for('home'))
        flash('Invalid username/password combination')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'username': request.form['username']})

        if existing_user is None:
            hashpass = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
            users.insert_one({'username': request.form['username'], 'password': hashpass})
            session['username'] = request.form['username']
            return redirect(url_for('home'))
        flash('That username already exists!')
    return render_template('register.html')

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if 'username' in session:
        username = request.json.get('username')
        method = request.json.get('method')
        data = request.json.get('data')

        if method == 'shazam':
            # 샤잠 음성 인식 로직
            # 예시: 음성 파일을 처리하여 트랙 정보를 반환
            track = shazam_recognition(data)
            if track:
                mongo.db.playlists.insert_one({'username': username, 'track': track})
                return jsonify({'success': True, 'track': track})
            else:
                return jsonify({'success': False, 'error': 'Shazam recognition failed'})

        elif method == 'vision':
            # 이미지 인식 로직
            track = vision_recognition(data)
            if track:
                mongo.db.playlists.insert_one({'username': username, 'track': track})
                return jsonify({'success': True, 'track': track})
            else:
                return jsonify({'success': False, 'error': 'Vision recognition failed'})

        elif method == 'search':
            # 검색 기능 로직
            results = youtube_search(data)
            return jsonify({'success': True, 'results': results})

    return jsonify({'success': False}), 403

def shazam_recognition(audio_data):
    # 샤잠 API 호출하여 음성 인식
    return shazam.recognize_song(audio_data)

def vision_recognition(image_data):
    # Google Vision API 호출하여 이미지 인식
    image = vision.Image(content=image_data)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return None

def youtube_search(query):
    # YouTube Data API를 사용하여 검색
    videosSearch = VideosSearch(query, limit=10)
    results = videosSearch.result()
    return [{'title': video['title'], 'videoId': video['id']} for video in results['result']]


@app.route('/my_playlists')
def my_playlists():
    if 'username' in session:
        playlists = mongo.db.playlists.find({'username': session['username']})
        return render_template('my_playlists.html', playlists=playlists)
    return redirect(url_for('login'))

@app.route('/popular_playlists')
def popular_playlists():
    playlists = mongo.db.playlists.find().sort("likes", -1).limit(10)
    return render_template('popular_playlists.html', playlists=playlists)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' in session:
        if request.method == 'POST':
            users = mongo.db.users
            hashpass = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
            users.update_one({'username': session['username']}, {"$set": {'password': hashpass}})
            flash('Settings updated!')
        return render_template('settings.html')
    return redirect(url_for('login'))

@app.route('/add_track', methods=['POST'])
def add_track():
    if 'username' in session:
        username = request.json.get('username')
        video_id = request.json.get('videoId')
        track = {'videoId': video_id}
        mongo.db.playlists.insert_one({'username': username, 'track': track})
        return jsonify({'success': True})
    return jsonify({'success': False}), 403


@app.route('/ai_features', methods=['GET', 'POST'])
def ai_features():
    if request.method == 'POST':
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                client = vision.ImageAnnotatorClient()
                content = image.read()
                image = vision.Image(content=content)
                response = client.text_detection(image=image)
                texts = response.text_annotations
                detected_text = texts[0].description if texts else 'No text detected'
                return render_template('ai_features.html', text=detected_text)

        if 'audio' in request.files:
            audio = request.files['audio']
            if audio.filename != '':
                song_info = asyncio.run(process_audio(audio))
                return render_template('ai_features.html', song_info=song_info)

    return render_template('ai_features.html')

async def process_audio(audio):
    shazam = shazamio.Shazam()
    out = await shazam.recognize_song(audio)
    song_info = {
        'track': out['track']['title'],
        'artist': out['track']['subtitle']
    }
    return song_info

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
