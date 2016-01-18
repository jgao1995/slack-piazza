'''Common utility functions.'''
import re
import subprocess
from collections import namedtuple

import unittest

_POST_ID_PATTERN = re.compile(r'(?:@|post\s+|followup\s+to\s+|Piazza\s+)(\d+)',
                              flags=re.IGNORECASE)

_PIAZZA_LINK_PATTERN = 'https://www.piazza.com/class/{}?cid={}'

PiazzaPostAnnotation = namedtuple('PiazzaPostAnnotation', 'post_id start_index length num_index num_length')
PiazzaPost = namedtuple('PiazzaPost', 'title author created views tags')


def annotate_piazza_post_mentions(text):
  return [
    PiazzaPostAnnotation(post_id=int(match.group(1)), start_index=match.start(0), length=len(match.group(0)), 
                         num_index=match.start(1) - match.start(0), num_length=len(match.group(1))) 
      for match in _POST_ID_PATTERN.finditer(text)
  ]


def find_piazza_post_ids(text):
  return [annotation.post_id for annotation in annotate_piazza_post_mentions(text)]


def apply_annotations(annotations, text, func):
  offset = 0
  for annotation in sorted(annotations, key=lambda annot: annot.start_index):
    replacement = func(annotation, 
      text[annotation.start_index + offset:annotation.start_index + annotation.length + offset])
    text = "".join([
      text[:annotation.start_index + offset],
      replacement,
      text[annotation.start_index + annotation.length + offset:]
    ])
    offset += len(replacement) - annotation.length
  return text

def convert_html_to_markdown(text):
  p = subprocess.Popen(['pandoc', '-f', 'html', '-t', 'markdown'],
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
  # ugh python text encoding problems
  out, _ = p.communicate(text.encode('utf-8'))
  return out


def make_piazza_link(class_id, post_id):
  return _PIAZZA_LINK_PATTERN.format(class_id, post_id)


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
    'title_link': make_piazza_link(class_id, post['nr']),
    'text': content,
    'fields': [
      {'title': 'created', 'value': latest['created'], 'short': True},
      {'title': 'views', 'value': post['unique_views'], 'short': True},
      {'title': 'tags', 'value': ', '.join(post['folders']) if post['folders'] else '(none)', 'short': True}
    ]
  }


def make_piazza_attachments(network, class_id, posts):
  return [make_piazza_attachment(network, class_id, post) for post in posts]


class TestPiazzaTextExtraction(unittest.TestCase):
  '''Test cases for extracting piazza post information from text.'''
  def test_finds_a_mention(self):
    self.assertEqual(annotate_piazza_post_mentions('Someone needs to respond to @14'), 
      [PiazzaPostAnnotation(post_id=14, start_index=28, length=3, num_index=1, num_length=2)])
      
  def test_finds_multiple_mentions(self):
    self.assertEqual(annotate_piazza_post_mentions('Someone needs to respond to @14 and @151.'), 
      [
        PiazzaPostAnnotation(post_id=14, start_index=28, length=3, num_index=1, num_length=2),
        PiazzaPostAnnotation(post_id=151, start_index=36, length=4, num_index=1, num_length=3)
      ])
      
  def test_finds_text_mentions(self):
    self.assertEqual(annotate_piazza_post_mentions('What\'s with the followup to 1912'), 
    [PiazzaPostAnnotation(post_id=1912, start_index=16, length=16, num_index=12, num_length=4)])
    
  def test_finds_just_post_ids(self):
    self.assertEqual(find_piazza_post_ids('Here\'s some @11, @12, @13'), [11, 12, 13])
    
  def test_retains_duplicate_post_ids(self):
    self.assertEqual(find_piazza_post_ids('We\'re looking at @17 and @17 is hard'), [17, 17])

class TestTextReplacement(unittest.TestCase):
  '''Test cases for replacing text taken up by annotations'''
  def test_single_replacement(self):
    self.assertEqual(
      apply_annotations(
        [PiazzaPostAnnotation(post_id=19, start_index=28, length=3, num_index=1, num_length=2)],
        'Someone needs to respond to @19 asap.',
        lambda annot,text : ''.join(['<LINK|@', str(annot.post_id), '>'])),
      'Someone needs to respond to <LINK|@19> asap.')
      
  def test_multiple_replacements(self):
    self.assertEqual(
      apply_annotations(
        [
          PiazzaPostAnnotation(post_id=19, start_index=28, length=3, num_index=1, num_length=2),
          PiazzaPostAnnotation(post_id=17, start_index=62, length=14, num_index=12, num_length=2)
        ],
        'Someone needs to respond to @19 asap. Also have a look at the followup to 17',
        lambda annot,text : ''.join([
          '<LINK', str(annot.post_id), '|', text, '>'])),
      'Someone needs to respond to <LINK19|@19> asap. Also have a look at the <LINK17|followup to 17>')

if __name__ == '__main__':
  unittest.main()
