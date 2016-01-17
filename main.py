import datetime
import flask
import functools
import os
import piazza_api
import requests
import subprocess
import StringIO
from werkzeug import exceptions

import config

USERNAME = config.username
PASSWORD = config.password
EXPECTED_SLACK_TOKEN = config.slack_token


class Error(Exception):
  '''Base exception for this module.'''
  pass


class BadTokenException(Error):
  pass


class SlackResponseException(Error):
  def __init__(self, cause):
    self.cause = cause


def _init_piazza():
  p = piazza_api.Piazza()
  p.user_login(email=USERNAME, password=PASSWORD)
  return p


# FIXME: This Piazza object might need to be refreshed if the cookies expire
PIAZZA = _init_piazza()

app = flask.Flask(__name__)


@app.route('/')
def index():
    return '17'


@app.errorhandler(BadTokenException)
def handle_bad_token(e):
  return exceptions.Forbidden.description, exceptions.Forbidden.code


@app.errorhandler(SlackResponseException)
def handle_slack_response_exception(e):
  return exceptions.BadRequest.description, exceptions.BadRequest.code


@app.errorhandler(Error)
def handle_error(e):
  return e, 500


def slack_POST(f):
  @functools.wraps(f)
  def decorator(*args, **kwargs):
    if EXPECTED_SLACK_TOKEN == flask.request.form['token']:
      return f(*args, **kwargs)
    raise BadTokenException()
  return decorator


def convert_html_to_markdown(text):
  p = subprocess.Popen(['pandoc', '-f', 'html', '-t', 'markdown'],
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
  # ugh python text encoding problems
  out, _ = p.communicate(text.encode('utf-8'))
  return out


def convert_post_to_slack_data(post, clazz, class_id):
  latest = post['history'][0]
  user = clazz.get_users([latest['uid']])[0]
  content = convert_html_to_markdown(latest['content'])
  slack_attachment = {
    'fallback': 'Piazza post @{}'.format(post['nr']),
    'pretext': 'Piazza post @{}'.format(post['nr']),
    'author_name': user['name'] + (' (anonymous)' if latest['anon'] == 'stud' else ''),
    # how do we convert get the actual image given by user['photo']
    # 'author_icon': user['photo'],
    'title': latest['subject'],
    'title_link': 'https://www.piazza.com/{}?cid={}'.format(class_id, post['nr']),
    'text': content,
    'fields': [
      {'title': 'created', 'value': latest['created'], 'short': True},
      {'title': 'views', 'value': post['unique_views'], 'short': True},
      {'title': 'tags', 'value': ', '.join(post['folders']) if post['folders'] else '(none)', 'short': True}
    ]
  }
  return {
    'response_type': 'in_channel',
    'attachments': [slack_attachment]
  }


@app.route('/slack/<class_id>', methods=['POST'])
@slack_POST
def get_post_for_slack(class_id):
  clazz = PIAZZA.network(class_id)
  post_id = flask.request.form['text']
  post = clazz.get_post(post_id)
  data = convert_post_to_slack_data(post, clazz, class_id)
  r = requests.post(flask.request.form['response_url'], json=data)
  try:
    r.raise_for_status()
  except requests.exceptions.HTTPError as e:
    raise SlackResponseException(e)
  return ''


if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser(description='Start a server for Piazza integration with Slack.')
  parser.add_argument('--port', type=int, default=80, metavar='N', help='Port to listen on')
  parser.add_argument('--debug', action='store_true', default=False, help='Run in debug mode')

  args = parser.parse_args()

  app.run(host='0.0.0.0', port=args.port, threaded=True, debug=args.debug)
