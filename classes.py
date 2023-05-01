#!/usr/bin/env python3

import re
from datetime import datetime as dt
from functools import reduce
from operator import add
from math import floor
from .lexer import get_todos, ATIMESTAMP, ITIMESTAMP

ORG_TIME_FORMAT = '%Y-%m-%d %a %H:%M'

class Cookie:
    def __init__(self, text):
        if re.search(r'%', text):
            self._cookie_type = 'percent'
            match = re.search(r'\[(.+)%\]', text)
            if match:
                self._m = int(match.group(1))
            else:
                self._m = 0
            self._n = 100
        elif re.search(r'/', text):
            self._cookie_type = 'progress'
            match = re.search(r'\[(.*)/(.*)\]', text)
            m = int(match.group(1)) if match.group(1) != '' else 0
            n = int(match.group(2)) if match.group(2) != '' else 0
            self._m, self._n = m, n
        else:
            self._cookie_type = None
            self._m = 0
            self._n = 0
        if self._m > self._n:
            raise ValueError(f'Meaningless cookie value: {m}/{n}')

    @property
    def cookie_type(self):
        return self._cookie_type

    @cookie_type.setter
    def cookie_type(self, new_type):
        if new_type != self.cookie_type:
            if new_type == 'percent':
                self._m = int(self.m/self.n * 100)
                self._n = 100
            elif new_type == 'progress':
                pass
            else:
                raise ValueError(f'Unknown cookie type {new_type}')
            self._cookie_type = new_type

    @property
    def m(self):
        return self._m

    @m.setter
    def m(self, value):
        if not isinstance(value, int):
            raise ValueError(f'Cookie progress can only be an integer, {value} passed.')
        elif value > self.n:
            raise ValueError(f"Can't have cookie progress set to {value} > {self.n}")
        else:
            self._m = value

    @property
    def n(self):
        return self._n

    @n.setter
    def n(self, value):
        if not isinstance(value, int):
            raise ValueError(f'Cookie final value can only be an integer, {value} passed.')
        elif value < self.m:
            raise ValueError(f"Can't have cookie final value set to {value} < {self.m}")
        else:
            self._n = value

    def __repr__(self):
        return f'[{self.m}/{self.n}]' if self.cookie_type == 'progress' else f'[{self.m}%]'
            
class Priority:
    allowed_values = ['A', 'B', 'C']
    def _parse_priority(self, p):
        match = re.search("^\[#(.)\]", p)
        return match.group(1) if match else p

    def __init__(self, priority_text):
        p = self._parse_priority(priority_text)
        self.priority = p

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        if value in self.allowed_values:
            self._priority = value
        else:
            raise ValueError(f"Priority must be one of {self.allowed_values}; {value} passed")

    def _raise(self):
        idx = self.allowed_values.index(self.priority)
        self.priority = self.allowed_values[(idx + 1) % len(self.allowed_values)]

    def _lower(self):
        idx = self.allowed_values.index(self.priority)
        self.priority = self.allowed_values[(idx - 1) % len(self.allowed_values)]

    def __repr__(self):
        return f'[#{self.priority}]'
        
    
            
class Headline:
    _todo_keywords = {**get_todos()['todo_states'], **get_todos()['done_states']}
    _todo_states = list(get_todos()['todo_states'].values())
    _done_states = list(get_todos()['done_states'].values())
    def __init__(self, level, comment=False, todo=None, priority=None, title="", cookie=None, tags=None):
        self._level = len(re.sub(r'\s+', '', level))
        self._comment = comment
        self._todo = todo
        self._priority = Priority(priority) if priority else None
        self.title = title
        self._cookie = cookie if cookie is None else Cookie(cookie)
        self.tags = tags

    @property
    def done(self):
        return self.is_done()

    @done.setter
    def done(self, _):
        raise AttributeError("Can't set the 'done' attribute")

    def is_done(self):
        if self.todo in self._done_states:
            return True
        elif self.todo is None or self.todo in self._todo_states:
            return False
        else:
            raise ValueError(f"Uncategorized todo state {self.todo}")


    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        if not isinstance(value, int):
            raise ValueError(f"Can only set headline level to an integer value, {value} passed.")
        delta = value - self.level
        self._level = value

    def promote(self, n=1):
        level = self.level - n
        self.level = max(level, 1)

    def demote(self, n=1):
        self.level += n

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        if not isinstance(value, bool):
            raise ValueError('The "comment" property must be a boolean!')
        self._comment = value

    def toggle_comment(self):
        self.comment = not(self.comment)

    def comment_out(self):
        self.comment = True

    def uncomment(self):
        self.comment = False

    @property
    def todo(self):
        return self._todo

    @todo.setter
    def todo(self, value):
        if value not in self._todo_states and value not in self._done_states and value is not None:
            possible_states = set.union(self._todo_states, self._done_states)
            raise ValueError(f"Todo keyword has to be one of {','.join(possible_states)}, {value} passed.")
        else:
            self._todo = value
            self.done = self.is_done()

    @property
    def cookie(self):
        return self._cookie

    @cookie.setter
    def cookie(self, value):
        if not isinstance(value, Cookie):
            raise ValueError("Can only set cookie to an instance of the Cookie class.")
        else:
            self._cookie = value

    def raise_priority(self):
        self.priority._raise()

    def lower_priority(self):
        self.priority._lower()

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        self._priority = Priority(value) if value else None

    def __repr__(self):
        priority = f'{self.priority} ' if self.priority else ""
        comment = "COMMENT " if self.comment else ""
        todo = f"{self.todo} " if self.todo else ""
        cookie = str(self.cookie) if self.cookie else ""
        tags = f"    :{':'.join(self.tags)}:" if self.tags else ""
        return f"{'*' * self.level} {todo}{comment}{priority}{self.title} {cookie}{tags}"


class Scheduling:
    _closed = None
    _scheduled = None
    _deadline = None
    class Keyword:
        def __init__(self, attr):
            self.attr = '_' + attr
        def __get__(self, obj, keyword):
            return getattr(obj, self.attr)
        def __set__(self, obj, value):
            if value is None:
                setattr(obj, self.attr, None)
            elif isinstance(value, TimeStamp):
                if self.attr == '_closed':
                    value.active = False
                    value.end_time = value.repeater = value.deadline_warn = None
                if self.attr == '_scheduled' or self.attr == '_deadline':
                    value.active = True
                if self.attr != '_deadline':
                    value.deadline_warn = None
                setattr(obj, self.attr, value)
            else:
                raise TypeError(f"The timestamp value for a Scheduling keyword must be an instance of the TimeStamp class.")
    valid_keywords = ['closed', 'scheduled', 'deadline']
    def __init__(self, keyword=None, timestamp=None):
        if keyword is not None and timestamp is not None:
            canonical_keyword = re.sub(r':\s*$', '', keyword).lower()
            if canonical_keyword not in self.valid_keywords:
                raise ValueError(f'Scheduling keyword must be one of {self.valid_keywords}, got {canonical_keyword}')
            else:
                if isinstance(timestamp, TimeStamp):
                    setattr(self, canonical_keyword, timestamp)
                else:
                    raise TypeError("The timestamp value for a Scheduling keyword must be an instance of the TimeStamp class")

    def __add__(self, other):
        for keyword in self.valid_keywords:
            if getattr(self, keyword) and getattr(other, keyword):
                raise ValueError(f"Can't merge two Scheduling types when both of them have the {keyword} property set.") 
            else:
                result = Scheduling()
                for keyword in self.valid_keywords:
                    setattr(result, keyword, getattr(self, keyword) or getattr(other, keyword) or None)
                return result

    CLOSED = closed = Keyword('closed')
    SCHEDULED = scheduled = Keyword('scheduled')
    DEADLINE = deadline = Keyword('deadline')

    def __repr__(self):
        data = [f'{keyword.upper()}: {getattr(self, keyword)}' for keyword in self.valid_keywords if getattr(self, keyword) is not None]
        return ' '.join(data)
        

class TimeStamp:
    def __init__(self, timestamp_str):
        is_active = re.search(ATIMESTAMP, timestamp_str)
        is_inactive = re.search(ITIMESTAMP, timestamp_str)
        self._active = True if is_active else False
        match = is_active if self._active else is_inactive
        date, day_of_week, start_time, end_time, repeater, deadline_warn = match.groups()
        self._start_time = self._to_datetime([date, day_of_week, start_time])
        if end_time:
            end_time = re.sub(r'^-', '', end_time)
            self._end_time = self._to_datetime([date, day_of_week, end_time]) 
        else:
            self._end_time = None
        self._repeater = repeater
        self._deadline_warn = deadline_warn

    def _to_datetime(self, date_components):
        if date_components[-1] is None:
            dt_format = ' '.join(ORG_TIME_FORMAT.split(' ')[:-1])
            date_components = date_components[:-1]
        else:
            dt_format = ORG_TIME_FORMAT
        return dt.strptime(' '.join(date_components), dt_format)
    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        if isinstance(value, str):
            t = dt.strptime(' '.join([self.start_time.strftime(' '.join(ORG_TIME_FORMAT.split(' ')[0:2])), value]), ORG_TIME_FORMAT)
        elif isinstance(value, dt):
            if value.year != self.end_time.year or value.month != self.end_time.month or value.day != self.end_time.day:
                raise ValueError('The start time for a timestamp must have the same date as the end time')
            else:
                t = value
        else:
            raise TypeError(f"Can't set timestamp start time from value of type {type(value)}!")
        if t > self.end_time:
            raise ValueError("Start time must be before end time")
        else:
            self._start_time = t

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        if isinstance(value, bool):
            self._active = value
        else:
            raise TypeError("The active property of timestamps needs to be a Boolean.")

    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        if value is None:
            self._end_time = None
            t = None
        elif isinstance(value, str):
            t = dt.strptime(' '.join([self.end_time.strftime(' '.join(ORG_TIME_FORMAT.split(' ')[0:2])), value]), ORG_TIME_FORMAT)
        elif isinstance(value, dt):
            if value.year != self.start_time.year or value.month != self.start_time.month or value.day != self.start_time.day:
                raise ValueError('The end time for a timestamp must have the same date as the start time')
            else:
                t = value
        else:
            raise TypeError(f"Can't set timestamp end time from value of type {type(value)}!")
        if t and t < self.start_time:
            raise ValueError("End time must be after start time.")
        elif t:
            self._end_time = t

    @property
    def repeater(self):
        return self._repeater

    @repeater.setter
    def repeater(self, value):
        if value is None:
            self._repeater = None
        elif re.search(r'^[.+]?\+[0-9]+[hdwmy]', value):
            self._repeater = value
        else:
            raise ValueError(f"Repeaters must start with .+, ++ or +, followed by an integer and one of h, d, w, m or y. Can't work with {value}.")

    @property
    def deadline_warn(self):
        return self._deadline_warn

    @deadline_warn.setter
    def deadline_warn(self, value):
        if value is None:
            self._deadline_warn = None
        elif re.search(r'^-[0-9]+[hdwmy]', value):
            self._deadline_warn = value
        else:
            raise ValueError(f"Special deadline warnings must start with -, followed by an integer and one of h, d, w, m or y. Can't work with {value}.")
    def __repr__(self):
        ldelim = '<' if self.active else '['
        rdelim = '>' if self.active else ']'
        timestamp = self.start_time.strftime(ORG_TIME_FORMAT)
        if self.end_time:
            timestamp += f'-{self.end_time.strftime("%H-%M")}'
        if self.repeater:
            timestamp += f' {self.repeater}'    
        if self.deadline_warn:
            timestamp += f' {self.deadline_warn}'
        return ldelim + timestamp + rdelim

class Drawer:
    def __init__(self, drawer_string):
        self.name = re.sub(r':', '', drawer_string.split('\n')[0])
        self.contents = drawer_string.strip().split('\n')[1:-1]
    def __repr__(self):
        contents = "\n".join(self.contents)
        return f''':{self.name}:
{contents}
:END:
'''    
        
class Heading:
    def __init__(self, headline, contents):
        self._headline = headline
        self._scheduling, self._drawers, self.body = contents
        self._children = None
        self._parent = None
        self._sibling = None
        if self.body:
            self.timestamps = [TimeStamp(t[0]) for t in re.findall(fr'({ATIMESTAMP}|{ITIMESTAMP})', self.body)]
        if self._drawers:
            properties_drawer = [d for d in self._drawers if d.name == 'PROPERTIES']
            if properties_drawer:
                self._properties = self._get_properties_dict(properties_drawer[0].contents)
            else:
                self._properties = dict()
        else:
            self._properties = dict()

    def _parse_clock_line(self, line):
        from .lexer import t_DATE, t_DAYOFWEEK, elapsed_time_regex
        itimestamp = fr'\[{t_DATE} {t_DAYOFWEEK} {elapsed_time_regex()}\]'
        m = re.search(fr'CLOCK:\s*({itimestamp})(?:--({itimestamp}))?', line)
        start_time = re.sub(r'[\[\]]', '', m.group(1))
        if m.group(2):
            end_time = re.sub(r'[\[\]]', '', m.group(2))
        else:
            end_time = None
        return Clocking(start_time, end_time)

    def _get_clocking_info(self):
        if not self.drawers:
            return []
        logbook = [d for d in self.drawers if d.name == 'LOGBOOK']
        if logbook:
            return [self._parse_clock_line(l) for l in logbook[0].contents if re.search(r'^\s*CLOCK:', l)]
        else:
            return []

    def _get_properties_dict(self, contents):
        return {k: v for (k, v) in [re.search(r':([^:]+):\s+(.*)', line).groups()
                                    for line in contents]} 

    def _get_properties_string(self):
        return "\n".join([f":{k}:{' '*7}{v}" for k, v in self.properties.items()])

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, val):
        if type(val) is not dict:
            raise TypeError("Heading properties must be given in the form of a dict")
        else:
            for key in val:
                self._properties[key] = val[key]


    def clocking(self, include_children=False):
        own_clocking = self._get_clocking_info()
        if include_children and self.children != []:
            return own_clocking + reduce(add, [c._get_clocking_info() for c in self.children])
        else:
            return own_clocking

    @property
    def headline(self):
        return self._headline

    @headline.setter
    def headline(self, value):
        if not isinstance(value, Headline):
            raise TypeError(f"Org headline must be of type {Headline}. Can't work with {type(value)}.")
        else:
            self._headline = value

    @property
    def scheduling(self):
        return self._scheduling

    @scheduling.setter
    def scheduling(self, value):
        if value is None:
            self._scheduling = None
        elif not isinstance(value, Scheduling):
            raise TypeError(f"Scheduling information must be of type {Scheduling}. Can't work with {type(value)}.")
        else:
            self._scheduling = value

    @property
    def drawers(self):
        updated_properties_drawer = Drawer(f""":PROPERTIES:
{self._get_properties_string()}
:END:""") 
        if self._drawers:
            if self._drawers[0].name == 'PROPERTIES':
                self._drawers = [updated_properties_drawer] + self._drawers[1:]
        elif self.properties:
            self._drawers = [updated_properties_drawer]
        return self._drawers

    @drawers.setter
    def drawers(self, value):
        types = {type(d) for d in value if type(d) is not Drawer}
        if value is None:
            self._drawers = None
        elif types:
            raise TypeError(f"Drawer information must be of type {Drawer}. Found these value types instead: {' '.join(types)}.")
        else:
            self._drawers = value

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self, value):
        if value is not None:
            types = {type(d) for d in value if type(d) is not Heading}
        if value is None:
            self._children = None
        elif types:
            raise TypeError(f"Child headings must all be of type {Heading}. Found these value types instead: {' '.join(types)}.")
        else:
            self._children = value

    def add_child(self, heading, new=False):
        if not isinstance(heading, Heading):
            raise TypeError(f"Child heading must be of type {Heading}. Can't work with {type(heading)}!")
        if new:
            if self.children:
                self.children.append(heading)
            else:
                self.children = [heading]
        else:
            if self.children:
                if heading.sibling:
                    try:
                        idx = self.children.index(heading.sibling) 
                        self.children = self.children[:idx + 1] + [heading] + self.children[idx+1:]
                    except ValueError:
                        raise ValueError("Incorrect promotion: grand parent doesn't have original parent in children!")
                else:
                    self.children = [heading] + self.children    
            else:
                self.children = [heading]

    def remove_child(self, child):
        if self.children:
            self.children = [c for c in self.children if c is not child]

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        if value is None:
            self._parent = None
        elif not isinstance(value, Heading):
            raise TypeError(f"Parent heading must be of type {Heading}. Can't work with {type(value)}.")
        else:
            self._parent = value

    @property
    def sibling(self):
        return self._sibling

    @sibling.setter
    def sibling(self, value):
        if value is None:
            self._sibling = None
        elif not isinstance(value, Heading):
            raise TypeError(f"Sibling heading must be of type {Heading}. Can't work with {type(value)}.")
        else:
            self._sibling = value

    @property
    def level(self):
        return self.headline.level

    @level.setter
    def level(self, value):
        self.headline.level = value

    def promote(self):
        if self.children:
            raise TypeError('Incorrect promotion: heading has children that would be orphaned. Did you mean promote_tree?')
        self.headline.promote()
        self.sibling = self.parent
        idx = self.sibling.children.index(self)
        next_siblings = self.sibling.children[idx + 1:]
        if next_siblings:
            next_siblings[0].sibling = None
            for s in next_siblings:
                s.parent = self
        self.children = next_siblings
        self.sibling.remove_child(self)
        for s in next_siblings:
            self.sibling.remove_child(s)
        self.parent = self.parent.parent
        self.parent.add_child(self)
        
    def promote_tree(self):
        children = self.children
        self.promote()
        if children:
            for child in children:
                child.promote_tree()

    def demote(self):
        if not self.sibling:
            raise ValueError('Incorrect demotion: heading has no sibling to adopt it.')
        self.headline.demote()
        idx = self.parent.children.index(self)
        try:
            next_sibling = self.parent.children[idx + 1]
            next_sibling.sibling = self.sibling
        except IndexError:
            pass
        self.parent.remove_child(self)
        self.parent = self.sibling
        if self.parent.children:
            self.sibling = self.parent.children[-1]
        else:
            self.sibling = None
        self.parent.add_child(self)
        if self.children:
            self.children[0].sibling = self
            for child in self.children:
                child.parent = self.parent
                self.parent.add_child(child)
        self.children = None

    def demote_tree(self):
        children = self.children
        self.demote()
        if children:
            for child in children:
                child.demote_tree()

        
    def __repr__(self):
        scheduling = str(self.scheduling) + "\n" if self.scheduling else ""
        drawers = str(self.drawers) + "\n" if self.drawers else ""
        body = (str(self.body) + "\n" if self.body else "")
        if len(body) > 80:
            body = body[:77].strip() + "...\n"
        newline = '\n' if scheduling or drawers or body else ''
        children = ''.join([c.__repr__() for c in self.children]) if self.children else ''

        return f'{self.headline}{newline}{scheduling}{drawers}{body}{children}'

class Clocking:
    def __init__(self, start_time, end_time=None):
        self._start_time = dt.strptime(start_time, ORG_TIME_FORMAT)
        if end_time is not None:
            self._end_time = dt.strptime(end_time, ORG_TIME_FORMAT)
        else:
            self._end_time = None
        self._duration = None

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        try:
            datetime_obj = dt.strptime(value, ORG_TIME_FORMAT)
            self._start_time = datetime_obj
        except ValueError:
            raise ValueError(f"Time string {value} doesn't match expected org time format {ORG_TIME_FORMAT}")
        
    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        if value is None:
            self._end_time = value
        else:
            try:
                datetime_obj = dt.strptime(value, ORG_TIME_FORMAT)
                self._end_time = datetime_obj
            except ValueError:
                raise ValueError(f"Time string {value} doesn't match expected org time format {ORG_TIME_FORMAT}")
        
    def _display_delta(self, time_delta):
        total_seconds = time_delta.days * 24 * 3600 + time_delta.seconds
        m, s = total_seconds/60, total_seconds%60
        if s > 30: m += 1
        h, m = m/60, m%60
        d, h = h/24, h%24
        days, hours, minutes = [floor(x) for x in (d, h, m)]
        if days == 0:
            return f'{hours}:{minutes:02d}'
        else:
            return f'{days}d {hours}:{minutes:02d}'

    @property
    def duration(self):
        if self.end_time is None:
            return self._display_delta(dt.now() - self.start_time)
        else:
            return self._display_delta(self.end_time - self.start_time)

    @duration.setter
    def duration(self, _):
        raise TypeError("Can't set the duration for a clocking object! Set the start and/or end time instead.")

    def __repr__(self):
        if self.end_time is None:
            return f'[{self.start_time.strftime(ORG_TIME_FORMAT)}]'
        else:
            return f'[{self.start_time.strftime(ORG_TIME_FORMAT)}]--[{self.end_time.strftime(ORG_TIME_FORMAT)}] =>  {self.duration}'
        
