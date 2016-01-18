import datetime
import functools
import os
import subprocess
import StringIO

import flask
import piazza_api
import requests
from werkzeug import exceptions

import common

import config


EXPECTED_SLACK_TOKEN = config.slash_command_expected_slack_token


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
  p.user_login(email=config.piazza_username, password=config.piazza_password)
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


def convert_post_to_slack_data(post, clazz, class_id):
  slack_attachment = common.make_piazza_attachment(clazz, class_id, post)
  return {
    'response_type': 'in_channel',
    'attachments': [slack_attachment]
  }


@app.route('/slack/<class_id>', methods=['POST'])
@slack_POST
def get_post_for_slack(class_id):
  clazz = PIAZZA.network(class_id)
  post_content = flask.request.form['text']
  annotations = common.annotate_piazza_post_mentions(post_content)
  try:
    posts = [(annotation, clazz.get_post(annotation.post_id)) for annotation in annotations]
  except piazza_api.exceptions.RequestError as e:
    return e, 400
  else:
    slack_attachments = [
      common.make_piazza_attachment(clazz, class_id, post)
        for post in posts
    ]
    data = {
      'response_type': 'in_channel',
      'username': flask.request.form['user_name'],
      'text': common.apply_annotations(annotations, text, lambda annot, text: ''.join([
          '<',
          common.make_piazza_link(class_id, annot.post_id),
          '|',
          text,
          '>'
        ]
      'attachments': slack_attachments
    }
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
