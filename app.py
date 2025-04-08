from flask import Flask, render_template, request, jsonify
import random

app = Flask(__name__)

ALL_EMOJIS = [
    {"emoji": "🍉"},
    {"emoji": "🐣"},
    {"emoji": "🚀"},
    {"emoji": "🌈"},
    {"emoji": "🎻"},
    {"emoji": "🦄"},
    {"emoji": "🚀"},
    {"emoji": "🌈"},
    {"emoji": "🎻"},
    {"emoji": "🦄"},
]

@app.route('/')
def index():
    emojis_to_show = random.sample(ALL_EMOJIS, 8)
    for i, e in enumerate(emojis_to_show):
        e['size'] = random.randint(20, 80)
        e['rotation'] = random.randint(0, 360)
        e['index'] = i # index determines the location of each emoji on card
    return render_template('emojis.html', emojis=emojis_to_show)

@app.route('/clicked', methods=['POST'])
def clicked():
    data = request.get_json()
    emoji = data.get('emoji')
    print(f'Emoji clicked: {emoji}')
    return jsonify({'message': f'You clicked on {emoji}!'})

if __name__ == '__main__':
    app.run(debug=True)
