import json
import logging
import re
import sys
import time

import piazza_api
import slackclient

import common
import config


TOKEN = config.slack_bot_token

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def _init_piazza_network():
  p = piazza_api.Piazza()
  p.user_login(email=config.piazza_username, password=config.piazza_password)
  return p.network(config.piazza_class_id)


PIAZZA_NETWORK = _init_piazza_network()
PIAZZA_CLASS_ID = config.piazza_class_id


class MySlackClient(slackclient.SlackClient):
  def __init__(self, *args, **kwargs):
    super(MySlackClient, self).__init__(*args, **kwargs)

  def api_call(self, *args, **kwargs):
    return json.loads(super(MySlackClient, self).api_call(*args, **kwargs))


def post_message_with_piazza_links(sc, post_ids, user, channel):
  posts = []
  post_id_error_list = []
  for post_id in post_ids:
    try:
      post = PIAZZA_NETWORK.get_post(post_id)
      posts.append(post)
    except piazza_api.exceptions.RequestError as e:
      post_id_error_list.append((post_id, e))

  if post_id_error_list:
    error_text = 'Could not fetch Piazza post{}: {}'.format(
      '(s)' if len(post_id_error_list) > 1 else '',
      ', '.join('@{}'.format(p) for p, _ in post_id_error_list))
      # '\n'.join('@{}: {}'.format(p, e) for p, e in post_id_error_list))
  else:
    error_text = ''

  if posts:
    link_text = 'Linked Piazza post{}: {}\n'.format(
      '(s)' if len(posts) > 1 else '',
      ', '.join('<https://www.piazza.com/class/{}?cid={}|@{}>'
                .format(PIAZZA_CLASS_ID, p['nr'], p['nr']) for p in posts))
  else:
    link_text = ''

  text = '<@{}>: {}{}'.format(user, link_text, error_text)

  piazza_attachments = common.make_piazza_attachments(
    PIAZZA_NETWORK, PIAZZA_CLASS_ID, posts)

  sc.api_call('chat.postMessage', channel=channel, text=text,
              unfurl_links=False, attachments=json.dumps(piazza_attachments),
              as_user=True)


def _process_event(sc, event, my_id):
  if event['type'] == 'error':
    logger.error(event)
  elif event['type'] == 'message':
    if 'user' in event and event['user'] != my_id:
      post_ids = common.find_piazza_post_ids(event['text'])
      if post_ids:
        post_message_with_piazza_links(sc, post_ids, event['user'], event['channel'])
  else:
    pass


def process_event(sc, event, my_id):
  try:
    _process_event(sc, event, my_id)
  except KeyError as e:
    logger.exception(e)


def main():
  sc = MySlackClient(TOKEN)
  if sc.rtm_connect():
    r = sc.api_call('auth.test')
    if not r['ok']:
      sys.exit(r)

    my_id = r['user_id']

    logging.info('Waiting for Slack RTM API endpoint...')
    while True:
      events = sc.rtm_read()
      for event in events:
        process_event(sc, event, my_id)
      time.sleep(1)
  else:
    sys.exit('Connection failed; invalid token?')


if __name__ == '__main__':
  main()
