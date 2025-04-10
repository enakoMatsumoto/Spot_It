from flask import Flask, render_template, request, jsonify
import random
import numpy as np
import sympy

app = Flask(__name__)

ALL_EMOJIS = [
    "😀", "😂", "🥰", "😎", "😭", "😡", "👍", "👎", "🙏", "💪", 
    "🔥", "🌟", "🎉", "🎶", "🚀", "🍕", "🍔", "🍎", "⚽", "🏀",
    "🐶", "🐱", "🐼", "🦄", "🌈", "🍄", "🌍", "🌙", "☀️", "⭐",
    "🏡", "🏖️", "🛒", "✈️", "🚗", "🚲", "💡", "📚", "💻", "📱",
    "🎮", "🎨", "🎤", "🏆", "🥇", "🥈", "🥉", "🚴", "🏃", "🧘",
    "🛌", "🛫", "🛬", "📷", "🎥", "🧸", "💎"
]

def generate_cards():
  """
    faro plane with 57 points and 57 lines. 8 points per line. we are working over the field 𝔽₇ (integers mod 7).
    each point is an emoji, each line is a card
    variable lines contain a list of tuples with each tuple containing 8 numbers corresponding to 8 emojis. 
  """
  # Define field and projective plane parameters
  q = 7
  F = sympy.GF(q)

  # Generate all nonzero triples (x, y, z)
  points = []
  for x in range(q):
      for y in range(q):
          for z in range(q):
              if (x, y, z) != (0, 0, 0):
                  points.append((x, y, z))

  # Normalize points: treat (x,y,z) ~ (λx,λy,λz) for any nonzero λ
  def normalize_point(p):
      for coord in p:
          if coord != 0:
              inv = sympy.invert(coord, q)
              return tuple((inv * x) % q for x in p)
      return p


  norm_points = []
  seen = set()

  for p in points:
      np = normalize_point(p)
      if np not in seen:
          seen.add(np)
          norm_points.append(np)

  # Now norm_points should have exactly 57 points
  assert len(norm_points) == q**2 + q + 1

  # Build lines: each line corresponds to a linear form ax + by + cz = 0
  lines = []

  for a in range(q):
      for b in range(q):
          for c in range(q):
              if (a, b, c) != (0, 0, 0):
                  line = []
                  for i, (x, y, z) in enumerate(norm_points):
                      if (a * x + b * y + c * z) % q == 0:
                          # line.append((x, y, z))
                          line.append(i)
                  if len(line) == 8:
                      # Normalize line by sorting points
                      # line_sorted = tuple(sorted(line))
                      lines.append(tuple(line))

  # Deduplicate lines
  lines = list(set(lines))
  return lines

@app.route('/')
def index():
    cards = generate_cards()
    selected_emojis = random.sample(cards, 1)[0] # pick one random card to display
    emojis_to_show = []
    for i, emoji in enumerate(selected_emojis):
        e = {}
        e['emoji'] = ALL_EMOJIS[emoji]
        e['size'] = random.randint(20, 80)
        e['rotation'] = random.randint(0, 360)
        e['index'] = i # index determines the location of each emoji on card
        emojis_to_show.append(e)
    return render_template('emojis.html', emojis=emojis_to_show)

@app.route('/clicked', methods=['POST'])
def clicked():
    data = request.get_json()
    emoji = data.get('emoji')
    print(f'Emoji clicked: {emoji}')
    return jsonify({'message': f'You clicked on {emoji}!'})

if __name__ == '__main__':
    app.run(debug=True)
