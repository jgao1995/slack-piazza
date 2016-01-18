'''Common utility functions.'''
import re
import subprocess


_POST_ID_PATTERN = re.compile(r'(?:@|post\s+|followup\s+to\s+|Piazza\s+)(\d+)',
                              flags=re.IGNORECASE)


def find_piazza_post_ids(text):
  return (int(post_id) for post_id in _POST_ID_PATTERN.findall(text))


def convert_html_to_markdown(text):
  p = subprocess.Popen(['pandoc', '-f', 'html', '-t', 'markdown'],
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
  # ugh python text encoding problems
  out, _ = p.communicate(text.encode('utf-8'))
  return out


def make_piazza_attachment(network, class_id, post):
  latest = post['history'][0]
  user = network.get_users([latest['uid']])[0]
  if not user:
    user = {'name': '(UID={})'.format(latest['uid']), 'photo': '(unknown photo ID)'}
  content = convert_html_to_markdown(latest['content'])
  return {
    'fallback': 'Piazza post @{}'.format(post['nr']),
    'pretext': 'Piazza post @{}'.format(post['nr']),
    'author_name': user['name'] + (' (anonymous)' if latest['anon'] == 'stud' else ''),
    # how do we convert get the actual image given by user['photo']
    # 'author_icon': user['photo'],
    'title': latest['subject'],
    'title_link': 'https://www.piazza.com/class/{}?cid={}'.format(class_id, post['nr']),
    'text': content,
    'fields': [
      {'title': 'created', 'value': latest['created'], 'short': True},
      {'title': 'views', 'value': post['unique_views'], 'short': True},
      {'title': 'tags', 'value': ', '.join(post['folders']) if post['folders'] else '(none)', 'short': True}
    ]
  }


def make_piazza_attachments(network, class_id, posts):
  return [make_piazza_attachment(network, class_id, post) for post in posts]
