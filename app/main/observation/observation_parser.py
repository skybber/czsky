import re

from datetime import datetime
from dateutil import parser as date_parser

from app.models import Observation, ObservationItem, DeepskyObject
from app.commons import normalize_dso_name


OBS_ITEM_HEADER = r'## (.*)'

class ParseException(Exception):
    pass

class ParserContext(object):
    def __init__(self, lines):
        self.observation = Observation()
        self.lines = lines
        self.index = 0
        self.success_msgs = []
        self.warn_msgs = []
        self.error_msgs = []

    def get_line(self):
        return self.lines[self.index]
    def next_line(self):
        if self.index < len(self.lines):
            self.index += 1
    def is_end(self):
        return self.index == len(self.lines)
    def format_msg(self, msg):
        return 'line:' + str(self.index + 1) + ':' + msg
    def add_error(self, msg):
        self.error_msgs.append(self.format_msg(msg))
    def add_warn(self, msg):
        self.error_warn.append(self.format_msg(msg))

def _read_empty_lines(ctx):
    while not ctx.is_end():
        line = ctx.get_line()
        if len(line) > 0:
            return
        ctx.next_line();

def _read_line(ctx, expected=None, expected_descr = None, mandatory=False):
    if ctx.is_end():
        if expected and mandatory:
            raise ParseException('Unexpected end of document.Expected : ' + expected_descr if expected_descr else expected)
        return None # end of file
    match = re.fullmatch(expected, ctx.get_line())
    if not match and mandatory:
        raise ParseException('Unexpected text. Expected : ' + expected_descr if expected_descr else expected)
    if match:
        ctx.next_line()
    return match

def _read_until(ctx, expected):
    txt = ''
    while not ctx.is_end():
        if re.fullmatch(expected, ctx.get_line()):
            break
        txt += ctx.get_line() + '\n'
        ctx.next_line()
    return txt

def _read_line_gen(ctx, expected):
    m = _read_line(ctx, expected)
    while m:
        yield m
        m = _read_line(ctx, expected)

def add_global_var(ctx, var, value):
    if var == 'date':
        try:
            ctx.observation.date = date_parser.parse(value)
        except ValueError as e:
            ctx.add_error('Invalid format for date:' + value + ' Expected yyyy-mm-dd or yyyy/mm/dd.')
    elif var == 'location':
        ctx.observation.location_position = value
        # TODO: assign existing location
    elif var == 'seeing':
        pass
    else:
        m = re.fullmatch(r'(sqm\d+)', var)
        if m:
            pass

    pass

def _read_observation_title(ctx):
    _read_empty_lines(ctx)
    m = _read_line(ctx, expected=r'# (.*)', mandatory=True)
    ctx.observation.title = m.group(1)

def _read_header(ctx):
    _read_empty_lines(ctx)
    for m in _read_line_gen(ctx, expected=r'(\w+)\s*:\s*(.*)\s*'):
        add_global_var(ctx, m.group(1), m.group(2))

def _read_observation(ctx):
    _read_empty_lines(ctx)
    ctx.observation.notes = _read_until(ctx, expected=OBS_ITEM_HEADER)

def _parse_time(ctx, stime):
    m = re.match(r'\s*T\((\d\d?:\d\d)\)\s*:?\s*', stime)
    if not m:
        ctx.add_error('Observation time in format \'T(HH:MM)\' expected.')
        return None
    if not ctx.observation.date:
        return None
    return datetime.combine(ctx.observation.date, datetime.strptime(m.group(1),"%H:%M").time())

def _parse_observation_item_header(ctx, txt):
    parts = txt.split(':', 1)
    dso_names = parts[0].split(',')
    norm_names = []
    for name in dso_names:
        norm_names.append(normalize_dso_name(name))
    date_time = None
    if len(parts) > 1:
        date_time = _parse_time(ctx, parts[1])
        pass
    else:
        date_time = None
    return norm_names, date_time

def _read_observation_item(ctx):
    m = _read_line(ctx, expected=OBS_ITEM_HEADER)
    if m:
        deepsky_objects, date_time = _parse_observation_item_header(ctx, m.group(1))
        notes = _read_until(ctx, expected=OBS_ITEM_HEADER)
        observation_item = ObservationItem(date_time=date_time, txt_deepsky_objects=','.join(deepsky_objects), notes=notes)
        ctx.observation.observation_items.append(observation_item)
        for dso_name in deepsky_objects:
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                observation_item.deepsky_objects.append(dso)
            else:
                ctx.add_warn('Deepsky object \'' + dso_name + '\' not found')
        return True
    return False

def parse_observation(text):
    ctx = ParserContext(list(map(str.strip, text.strip().splitlines())))
    try:
        _read_observation_title(ctx)
        _read_header(ctx)
        _read_observation(ctx)
        while _read_observation_item(ctx):
            pass
    except ParseException as e:
        ctx.add_error(e.message)
    if len(ctx.error_msgs) > 0:
        ctx.observation = None
    return (ctx.observation, ctx.warn_msgs, ctx.error_msgs)
