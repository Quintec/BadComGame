from flask import Flask, render_template, request, current_app
from flask_socketio import SocketIO, emit, join_room, leave_room
import os, string, random, threading, time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET')

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

class TimerClass(threading.Thread):
  def __init__(self, num, room):
    threading.Thread.__init__(self)
    self.event = threading.Event()
    self.count = num
    self.rid = room

  def run(self, app):
    while self.count > 0 and not self.event.is_set():
      socketio.emit("timer", self.count, room=self.rid)
      self.count -= 1
      self.event.wait(1)
    if self.count == 0:
      socketio.emit("timeUp", room=self.rid)
      fail(self.rid)
      new_phrase(self.rid)

  def stop(self):
    self.event.set()

games = {}
ids = []

phrases = os.getenv('PHRASES').split('\n')

@app.route('/')
def index():
  return render_template('index.html')

@app.route('/play/speaker/<idd>')
def speaker(idd):
  if idd in games:
    if 'uid' in request.cookies and request.cookies.get('uid') == games[idd]['speaker']:
      return render_template('speaker.html')
    else:
      return "Game access denied", 403
  else:
    return "Game not found", 404

@app.route('/play/typer/<idd>')
def typer(idd):
  if idd in games:
    if 'uid' in request.cookies and request.cookies.get('uid') == games[idd]['typer']:
      return render_template('typer.html')
    else:
      return "Game access denied", 403
  else:
    return "Game not found", 404

@socketio.on('startGame')
def start_game(data):
  uid = data['uid']
  game = data['rid']
  if len(games[game]['joined']) < 2:
    emit('notReady')
  elif games[game]['speaker'] == uid:
    emit('gameStart', room=game)
    new_phrase(game)

@socketio.on('typerGuess')
def typer_guess(data):
  uid = data['uid']
  game = data['game']
  if game in games and games[game]['typer'] == uid:
    if games[game]['phrase'] == data['guess']:
      sc = get_score(games[game]['timer'].count)
      emit('correct', {'phrase': games[game]['phrase'], 'pts': sc}, room=game)
      games[game]['score'] += sc
      emit('score', games[game]['score'], room=game)
    else:
      emit('wrong', room=game)
      fail(game)
    if game in games:
      games[game]['timer'].stop()
      new_phrase(game)

def get_score(time_left):
  return [2, 3, 5, 5][time_left // 3]

def fail(game):
  games[game]['lives'] -= 1
  if games[game]['lives'] == 0:
    socketio.emit('gameOver', games[game]['score'], room=game)
    del games[game]
  else:
    socketio.emit('lifeChange', games[game]['lives'], room=game)

def new_phrase(game):
  phr = random.choice(phrases)
  games[game]['phrase'] = phr
  socketio.emit('phrase', phr, room='speaker')
  games[game]['timer'] = TimerClass(15, game)
  with app.app_context():
    socketio.start_background_task(games[game]['timer'].run, current_app._get_current_object())

@socketio.on('joinGame')
def join_game(data):
  uid = data['uid']
  game = data['game']
  if games[game]['speaker'] == uid or games[game]['typer'] == uid:
    games[game]['joined'].add(uid)
    join_room(game)
  if games[game]['speaker'] == uid:
    join_room('speaker')
  elif games[game]['typer'] == uid:
    join_room('typer')

@socketio.on('getID')
def get_id():
  chars = string.ascii_letters + string.digits
  name = ''.join(random.choices(chars, k=10))
  while name in ids:
    name = ''.join(random.choices(chars, k=10))
  ids.append(name)
  emit('id', name)

@socketio.on('typerJoin')
def typer_join(data):
  uid = data['uid']
  rid = data['rid']
  if rid not in games:
    emit('gameDNE')
  elif games[rid]['typer'] is None:
    games[rid]['typer'] = uid
    emit('typer', rid)
  else:
    emit('typerExists')

@socketio.on('getHost')
def get_host(idd):
  chars = string.ascii_letters + string.digits
  name = ''.join(random.choices(chars, k=6))
  while name in games:
    name = ''.join(random.choices(chars, k=6))
  games[name] = {'speaker': idd, 'typer': None, 'joined': set(), 'lives': 3, 'score': 0, 'phrase': '', 'timer': None}
  emit('host', name)

if __name__ == "__main__":
  socketio.run(app,'0.0.0.0')
