from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
import bcrypt
from google.cloud import vision
import os
import urllib.parse  # 추가
import shazamio
import asyncio
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'mysecret'

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/myDatabase"
mongo = PyMongo(app)

@app.route('/')
def home():
    recommended_playlists = mongo.db.playlists.find().limit(5)
    popular_users = mongo.db.users.find().sort("followers", -1).limit(5)
    return render_template('home.html', recommended_playlists=recommended_playlists, popular_users=popular_users)

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
