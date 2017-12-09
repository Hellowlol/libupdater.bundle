import os
import re
import subprocess

PREFIX = '/video/libraryupdater'
NAME = 'Library Updater'
ART = 'art-default.jpg'
ICON = 'icon-default.png'
PMS_URL = 'http://127.0.0.1:32400/library/sections/'


def longest_common_substring(s1, s2):
    # https://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Longest_common_substring#Python_2
    m = [[0] * (1 + len(s2)) for i in xrange(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in xrange(1, 1 + len(s1)):
        for y in xrange(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest: x_longest]


def find_section(path):
    """ helper to find the section for a location."""
    Log.Debug('Section was omitted from the call, lets see if we can find it.')
    secs = []
    sections = XML.ElementFromURL(PMS_URL).xpath('//Directory')
    for section in sections:
        location = section.xpath('Location/@path')
        key = section.get('key')

        d = {'location': location,
             'key': key,
             'locmatches': 0,
             'title': section.get('title')
        }

        loc_match = []

        abc = longest_common_substring(path, ' '.join(location))
        if abc:
            loc_match.append(len(abc))

        d['locmatches'] = max(loc_match)

        secs.append(d)

    secs.sort(key=lambda k: k['locmatches'], reverse=True)
    Log.Debug(secs)

    if secs:
        # Made sure this does not point to more then one sections.
        if [k.get('loc_match') for k in secs].count(secs[0]['locmatches']) > 1:
            Log.Debug('Root exist on more then one library, pass a library section')
        return secs[0]['key']
    else:
        return ''



def quotes_args(args):
    if os.name == 'nt':
        return subprocess.list2cmdline(args)
    else:
        from pipes import quote
        return ' '.join(quote(a) for a in args)


@route(PREFIX + '/scanner', )
def scanner(
        # This does not exist in the cli but its alot more user friendly imo
        path=None,
        # Actions
        refresh=None,
        analyze=None,
        index=None,
        scan=None,
        analyze_deeply=None,
        info=None,
        list=None,
        generate=None,
        tree=None,
        # Items to which actions apply
        section=None,
        item=None,
        directory=None,
        file=None,
        # Modifiers to actions
        force=None,
        no_thumbs=None,
        chapter_thumbs_only=None,
        thumboffset=None,
        artoffset=None,
        **kwargs):
    """ Mimic the scanner cli. This is intended to be used by programs.

        Some methods to the cli are not added by purpose.

    """
    Log.Debug('Calling scanner')

    args = []

    if Prefs['scanner_path'] == '':
        if os.name == 'nt':
            scannerpath = r'C:\Program Files (x86)\Plex\Plex Media Server\Plex Media Scanner.exe'
        else:
            scannerpath = os.path.join(
                os.path.expanduser('~'),
                'Library/Application Support/Plex Media Server/Plex Media Scanner')
    else:
        scannerpath = Prefs['scanner_path']

    Log.Debug('scannerpath was %s' % scannerpath)

    truty = [True, 'True', 'true', 1, '1']
    falsy = [False, 'False', 'false', 0, '0']

    # Actions first.
    if refresh in truty:
        args.append('--refresh')

    if analyze in truty:
        args.append('--analyze')

    if index in truty:
        args.append('--index')

    if analyze_deeply in truty:
        args.append('--analyze-deeply')

    if info in truty:
        args.append('--info')

    if scan in truty:
        args.append('--scan')

    # Loads of stuff is missing here but scan is is the only one i care about
    # actions apply.
    if section is None:
        sec = find_section(path)
        args.append('--section')
        args.append(sec)
    else:
        args.append('--section')
        args.append(section)

    if item is not None:
        args.append('--item')
        args.append(item)

    if file is not None:
        args.append('--file')
        args.append(file)

    if directory is not None:
        args.append('--directory')
        args.append(directory)

    if file is None and directory is None and path is not None:
        if os.path.isdir(path):
            args.append('--directory')
        elif os.path.isfile(path):
            args.append('--file')

        args.append(path)

    # Flags
    if force in truty:
        args.append('--force')

    if no_thumbs in truty:
        args.append('no-thumbs')

    if chapter_thumbs_only in truty:
        args.append('chapter-thumbs-only')

    if thumboffset is not None:
        args.append('--thumbOffset')
        args.append(thumboffset)

    if artoffset is not None:
        args.append('--artOffset')
        args.append(artoffset)

    if args:
        args.insert(0, scannerpath)

    def start_scanner(cmd=None):
        # For some reason runtime.py does not pass args to threading.thread...
        resp = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        Log.Debug(resp)
        return

    args_string = quotes_args(args)

    Log.Debug('Cmd passed to subprocess is: %s' % args_string)
    Thread.Create(start_scanner, cmd=args_string)

    return ObjectContainer(message='Working')


def Start():
    HTTP.CacheTime = 0


@handler(PREFIX, NAME, thumb=ICON, art=ART)
def MainMenu():
    Log.Debug('Creating main menu')

    oc = ObjectContainer(no_cache=True)
    all_keys = []

    oc.add(DirectoryObject(title='Manual scan', key=Callback(manualmenu)))

    try:
        sections = XML.ElementFromURL(PMS_URL).xpath('//Directory')
        for section in sections:
            key = section.get('key')
            title = section.get('title')
            Log.Debug('Added %s to main menu.' % title)

            oc.add(
                DirectoryObject(
                    key=Callback(UpdateType, title=title, key=[key]),
                    title='Update section %s' % title))

            all_keys.append(key)
    except:
        pass

    if len(all_keys):
        oc.add(
            DirectoryObject(
                key=Callback(UpdateType, title='All sections', key=all_keys),
                title='Update all sections'))

    oc.add(PrefsObject(title='Preferences', thumb=R('icon-prefs.png')))

    return oc


@route(PREFIX + '/manualmenu')
def manualmenu(*args, **kwargs):
    oc = ObjectContainer(title2='Manual scan')

    if 'action' in kwargs:
        Log.Debug('Action in kwargs %s' % kwargs.get('action'))
        action = kwargs.get('action')

    elif Prefs['action']:
        Log.Debug('Action in Prefs %s' % Prefs['action'])
        action = Prefs['action']

    elif 'action' in Dict:
        Log.Debug('Action in Dict %s' % Dict['action'])
        action_apply = Dict['action']

    if 'action_apply' in kwargs:
        Log.Debug('action_apply in kwargs %s' % kwargs.get('action_apply'))
        action_apply = kwargs.get('action')

    elif Prefs['action_apply']:
        Log.Debug('action_apply in Prefs %s' % Prefs['action_apply'])
        action_apply = Prefs['action']

    elif 'action_apply' in Dict:
        Log.Debug('action_apply in Dict %s' % Dict['action_apply'])
        action_apply = Dict['action_apply']

    if 'path' in kwargs:
        Log.Debug('path in kwargs %s' % kwargs.get('path'))
        path = kwargs.get('path')

    elif Prefs['path']:
        Log.Debug('path in Prefs %s' % Prefs['path'])
        path = Prefs['path']

    elif 'path' in Dict:
        Log.Debug('path in Dict %s' % Dict['path'])
        path = Dict['path']

    kw = {'path': path}

    # Map actions
    if action == 'scan':
        kw['scan'] = True
    elif action == 'refresh':
        kw['refresh'] = True
    elif action == 'analyze':
        kw['analyze'] = True

    # Map action modifiers.
    if action_apply == 'file':
        kw['file'] = True
    elif action_apply == 'directory':
        kw['directory'] = True
    elif action_apply == 'section':
        kw['section'] = True
    elif action_apply == 'item':
        kw['item'] = True

    Log.Debug(kw)

    oc.add(
        DirectoryObject(
            title='Edit prefs and click this.', key=Callback(scanner, **kw)))

    return oc


@route(PREFIX + '/type', key=int)
def UpdateType(title, key):

    oc = ObjectContainer(title2=title)

    oc.add(
        DirectoryObject(
            key=Callback(UpdateSection, title=title, key=key), title='Scan'))
    oc.add(
        DirectoryObject(
            key=Callback(UpdateSection, title=title, key=key, analyze=True),
            title='Analyze Media'))
    oc.add(
        DirectoryObject(
            key=Callback(UpdateSection, title=title, key=key, force=True),
            title='Force Metadata Refresh'))

    return oc


@route(PREFIX + '/section', key=int, force=bool, analyze=bool)
def UpdateSection(title, key, force=False, analyze=False):

    for section in key:
        if analyze:
            url = PMS_URL + section + '/analyze'
            method = "PUT"
        else:
            method = "GET"
            url = PMS_URL + section + '/refresh'

            if force:
                url += '?force=1'

        Thread.Create(Update, url=url, method=method)

    if title == 'All sections':
        return ObjectContainer(header=title, message='All sections will be updated!')
    elif len(key) > 1:
        return ObjectContainer(header=title, message='All chosen sections will be updated!')
    else:
        return ObjectContainer(header=title, message='Section "' + title + '" will be updated!')


@route(PREFIX + '/update')
def Update(url, method):
    HTTP.Request(url, cacheTime=0, method=method)
    return
