"""Personal Theme's local worker. Matugen and rclone remain external tools."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG = HOME / '.config/omarchy-personal-theme'
STATE = HOME / '.local/state/omarchy-personal-theme'
CACHE = HOME / '.cache/omarchy-personal-theme'
THEME = HOME / '.config/omarchy/themes/personal-theme'
BACKGROUNDS = HOME / '.config/omarchy/backgrounds/personal-theme'
CURRENT = HOME / '.local/state/omarchy/current'
MENU = HOME / '.config/omarchy/extensions/omarchy-menu.jsonc'
CLI = ROOT / 'bin/personal-theme'
FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic', '.heif'}
DEFAULTS = {'source': 'local', 'folder': str(HOME / 'Pictures/Wallpapers'),
            'interval': 60, 'mode': 'dark', 'adaptive': True, 'paused': False,
            'drive_remote': '', 'drive_folder': '', 'sync_interval': 15}
CHILDREN = set()


def terminate_children(signum, frame):
    for child in list(CHILDREN):
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    raise SystemExit(128 + signum)


def read(path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def locked(name):
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / (name + '.lock')).open('w') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def run(argv, **kwargs):
    # Never pass filenames, remote IDs, or OAuth values through a shell.
    timeout = kwargs.pop('timeout', 120)
    child = subprocess.Popen([str(x) for x in argv], text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True, **kwargs)
    CHILDREN.add(child)
    try:
        stdout, stderr = child.communicate(timeout=timeout)
        if child.returncode:
            # Dialog cancellation is an ordinary no-op, not an error.
            if child.returncode == 1 and (str(argv[0]) == 'zenity' or list(argv[:3]) == ['omarchy', 'menu', 'input']):
                return ''
            raise RuntimeError(f'{Path(str(argv[0])).name} failed (exit {child.returncode})')
        return stdout.rstrip('\n')
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally: CHILDREN.discard(child)


def settings():
    return {**DEFAULTS, **read(CONFIG / 'settings.json')}


def update(**changes):
    with locked('settings'):
        value = settings()
        value.update(changes)
        write(CONFIG / 'settings.json', value)


def active():
    path = CURRENT / 'theme.name'
    return path.exists() and path.read_text().strip() == 'personal-theme'


def enabled():
    return bool(read(STATE / 'lease.json').get('enabled'))


def background():
    path = CURRENT / 'background'
    return path.resolve() if path.exists() else None


def library():
    return [p for p in sorted(BACKGROUNDS.iterdir()) if p.is_file() and p.suffix.lower() in FORMATS - {'.heic', '.heif'}] if BACKGROUNDS.exists() else []


def fingerprint(path, config):
    if not path or not path.is_file():
        return ''
    stat = path.stat()
    return f'{path}:{stat.st_size}:{stat.st_mtime_ns}:{config["mode"]}:{config["adaptive"]}'


def resolved_mode():
    palette = THEME / 'colors.toml'
    if palette.exists():
        mode = tomllib.loads(palette.read_text()).get('mode')
        if mode in ('light', 'dark'): return mode
    mode = settings()['mode']
    return mode if mode in ('light', 'dark') else 'dark'


def status(now=None):
    now = time.time() if now is None else now
    config = settings()
    rotation = read(STATE / 'rotation.json')
    sync = read(STATE / 'sync.json')
    color = read(STATE / 'color.json')
    selected = active()
    available = library()
    running = enabled()
    return {'enabled': running, 'active': selected, 'paused': config['paused'],
            'count': len(available), 'interval': config['interval'], 'mode': config['mode'],
            'resolvedMode': resolved_mode(),
            'adaptive': config['adaptive'], 'source': config['source'],
            'transitionDue': running and rotation.get('active') != selected,
            'rotationDue': running and selected and not config['paused'] and len(available) > 1
                and rotation.get('active', False)
                and now - rotation.get('at', now) >= config['interval'] * 60,
            'colorDue': running and selected and config['adaptive'] and bool(background())
                and color.get('fingerprint') != fingerprint(background(), config)
                and now - color.get('attempt', 0) >= 30,
            'syncDue': running and now - sync.get('attempt', 0) >= config['sync_interval'] * 60,
            'lastSync': sync.get('success'), 'syncError': sync.get('error', ''),
            'colorError': color.get('error', ''),
            'nextRotation': rotation.get('at', now) + config['interval'] * 60
                if running and selected and not config['paused'] else None}


def ensure_theme():
    THEME.mkdir(parents=True, exist_ok=True)
    (THEME / 'backgrounds').mkdir(exist_ok=True)
    BACKGROUNDS.mkdir(parents=True, exist_ok=True)
    palette = THEME / 'colors.toml'
    if not palette.exists():
        old = HOME / '.config/omarchy/themes/matugen-auto/colors.toml'
        stock = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy')) / 'themes/tokyo-night/colors.toml'
        shutil.copyfile(old if old.exists() else stock, palette)
    template = {'templates.personal_theme': {
        'input_path': str(ROOT / 'templates/colors.toml'), 'output_path': str(palette)}}
    CONFIG.mkdir(parents=True, exist_ok=True)
    (CONFIG / 'matugen.toml').write_text('[config]\n\n[templates.personal_theme]\n'
        + 'input_path = ' + json.dumps(template['templates.personal_theme']['input_path']) + '\n'
        + 'output_path = ' + json.dumps(str(palette)) + '\n')
    # Always provide a preview: Omarchy's visual theme picker requires it.
    if not (THEME / 'preview.png').exists():
        images = library()
        if images:
            make_preview(images[0])
        else:
            shutil.copyfile(ROOT / 'assets/preview.png', THEME / 'preview.png')


def make_preview(image):
    target = THEME / 'preview.png'
    expected = fingerprint(image, settings())
    if target.exists() and read(STATE / 'preview.json').get('fingerprint') == expected:
        return
    fd, temporary = tempfile.mkstemp(prefix='.preview-', suffix='.png', dir=THEME)
    os.close(fd)
    try:
        run(['magick', str(image) + '[0]', '-auto-orient', '-thumbnail', '960x600', temporary])
        os.replace(temporary, target)
        write(STATE / 'preview.json', {'fingerprint': expected})
    finally:
        Path(temporary).unlink(missing_ok=True)


def menu_json(text):
    # A small JSONC reader that respects comment markers inside strings/URLs.
    output, in_string, escape, i = [], False, False, 0
    while i < len(text):
        ch = text[i]
        if in_string:
            output.append(ch)
            if escape: escape = False
            elif ch == '\\': escape = True
            elif ch == '"': in_string = False
        elif ch == '"':
            in_string = True
            output.append(ch)
        elif text[i:i+2] == '//':
            i = text.find('\n', i)
            if i == -1: break
            output.append('\n')
        elif text[i:i+2] == '/*':
            end = text.find('*/', i+2)
            if end < 0: raise ValueError('Unclosed JSONC comment')
            i = end + 1
        elif ch == ',':
            ahead = i + 1
            while ahead < len(text) and text[ahead].isspace(): ahead += 1
            if ahead >= len(text) or text[ahead] not in '}]': output.append(ch)
        else: output.append(ch)
        i += 1
    return json.loads(''.join(output))


def install_menu(remove=False):
    with locked('menu'):
        original = MENU.read_text() if MENU.exists() else '{}'
        if MENU.exists() and not (STATE / 'menu-before.jsonc').exists():
            (STATE / 'menu-before.jsonc').write_text(original)
        entries = menu_json(original)
        prefixes = ('appearance.personal-theme', 'appearance.personal-photos', 'style.personal-photos')
        for key in list(entries):
            if any(key == p or key.startswith(p + '.') for p in prefixes):
                del entries[key]
        if not remove:
            base = 'appearance.personal-theme'
            executable = shlex.quote(str(CLI))
            entries[base] = {'icon': '', 'label': 'Personal Theme', 'aliases': ['personal-theme', 'personal-photos'],
                             'when': executable + ' enabled', 'description': 'Your photos, wallpapers, and matching colors'}
            def action(key, label, command, **extra):
                entries[base + '.' + key] = {'label': label, 'action': executable + ' ' + command, **extra}
            action('choose', 'Choose Photo', 'pick', icon='')
            action('next', 'Next Photo', 'next', icon='󰒭')
            action('pause', 'Pause Rotation', 'pause', when=executable + ' is-running', icon='󰏤')
            action('resume', 'Resume Rotation', 'resume', when=executable + ' is-paused', icon='󰐊')
            action('sync', 'Sync Photos Now', 'request-sync', icon='󰑐')
            action('status', 'Status', 'show-status', icon='󰋽')
            entries[base + '.settings'] = {'label': 'Settings', 'icon': ''}
            action('settings.folder', 'Use Local Folder', 'choose-folder')
            action('settings.drive', 'Connect Google Drive Folder', 'connect-drive')
            entries[base + '.settings.interval'] = {'label': 'Rotation Interval'}
            for minutes in (15, 30, 60, 120, 240):
                action(f'settings.interval.m{minutes}', f'Every {minutes} minutes', f'configure interval {minutes}',
                       checked=executable + f' matches interval {minutes}')
            entries[base + '.colors'] = {'label': 'Color Mode', 'icon': '󰔎'}
            action('colors.auto', 'Auto · Match Photo', 'configure appearance smart', checked=executable + ' matches appearance smart')
            action('colors.dark', 'Dark', 'configure appearance dark', checked=executable + ' matches appearance dark')
            action('colors.light', 'Light', 'configure appearance light', checked=executable + ' matches appearance light')
            action('colors.fixed', 'Wallpaper Only', 'configure appearance fixed', checked=executable + ' matches appearance fixed')
            action('settings.dependencies', 'Install Dependencies', 'install-dependencies')
        # Preserve existing JSONC comments and layout outside owned entries.
        # The original is backed up; unrelated entry values remain identical.
        write(MENU, entries)
    if shutil.which('omarchy'):
        run(['omarchy', 'menu', 'refresh'])


def migrate():
    if (CONFIG / 'settings.json').exists():
        return
    config = DEFAULTS.copy()
    old = HOME / '.config/omarchy-drive-wallpapers/source.json'
    if old.exists():
        source = read(old)
        config.update(source='drive', drive_remote=source['remote'], drive_folder=source['folder_id'])
    config['paused'] = (HOME / '.local/state/omarchy/personal-wallpaper.paused').exists()
    old_settings = HOME / '.config/omarchy-auto-theme/settings'
    if old_settings.exists():
        if re.search(r'^MODE=light\s*$', old_settings.read_text(), re.M): config['mode'] = 'light'
    write(CONFIG / 'settings.json', config)
    old_backgrounds = HOME / '.config/omarchy/backgrounds/matugen-auto'
    BACKGROUNDS.mkdir(parents=True, exist_ok=True)
    if old_backgrounds.exists():
        for image in old_backgrounds.iterdir():
            if image.is_file() and image.suffix.lower() in FORMATS:
                shutil.copy2(image, BACKGROUNDS / image.name)
    old_cache = HOME / '.cache/omarchy-drive-wallpapers'
    if old_cache.exists(): shutil.copytree(old_cache, CACHE, dirs_exist_ok=True)
    if (CACHE / 'published.json').exists():
        write(STATE / 'library.json', read(CACHE / 'published.json'))


def activate(lease):
    migrate()
    ensure_theme()
    with locked('lease'):
        write(STATE / 'lease.json', {'enabled': True, 'lease': lease})
        install_menu()


def deactivate(lease):
    with locked('lease'):
        current = read(STATE / 'lease.json')
        if current.get('lease') != lease: return
        write(STATE / 'lease.json', {'enabled': False, 'lease': lease})
        install_menu(remove=True)


def sync():
    with locked('sync'):
        if not enabled(): return
        config = settings()
        old_status = read(STATE / 'sync.json')
        progress = {**old_status, 'attempt': time.time(), 'error': ''}
        write(STATE / 'sync.json', progress)
        try:
            if config['source'] == 'drive':
                if not config['drive_remote'] or not config['drive_folder']:
                    raise ValueError('Connect a Google Drive folder in Settings.')
                source = CACHE / 'originals'
                source.mkdir(parents=True, exist_ok=True)
                run(['rclone', 'sync', config['drive_remote'], source,
                     '--drive-root-folder-id', config['drive_folder'],
                     '--include', '*.{jpg,jpeg,png,webp,gif,bmp,heic,heif}', '--ignore-case',
                     '--max-size', '100M', '--contimeout', '10s', '--timeout', '30s',
                     '--retries', '2', '--max-duration', '5m', '--log-level', 'ERROR'], timeout=360)
            else:
                source = Path(config['folder']).expanduser().resolve()
                if not source.is_dir(): raise ValueError('Choose an existing photo folder in Settings.')
                if source == BACKGROUNDS.resolve() or BACKGROUNDS.resolve() in source.parents:
                    raise ValueError('Choose a source folder outside the managed wallpaper collection.')
            publish(source)
            write(STATE / 'sync.json', {**progress, 'success': time.time(), 'error': ''})
        except Exception as error:
            write(STATE / 'sync.json', {**progress, 'error': str(error)[:300]})
            raise


def publish(source):
    previous = read(STATE / 'library.json')
    published = {}
    candidates, scanned = [], 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        scanned += len(dirs) + len(files)
        if scanned > 30000: raise ValueError('Choose a smaller photo folder (under 30,000 entries).')
        if len(Path(directory).relative_to(source).parts) >= 32: dirs[:] = []
        for filename in files:
            path = Path(directory) / filename
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in FORMATS:
                candidates.append(path)
                if len(candidates) > 10000: raise ValueError('Choose a folder with fewer than 10,000 photos.')
    candidates.sort()
    for image in candidates:
        if image.stat().st_size > 100 * 1024 * 1024: continue
        key = str(image.relative_to(source))
        suffix = '.jpg' if image.suffix.lower() in {'.heic', '.heif'} else image.suffix.lower()
        name = 'drive-' + hashlib.sha256(key.encode()).hexdigest()[:24] + suffix
        stat = image.stat()
        entry = {'fingerprint': [stat.st_size, stat.st_mtime_ns], 'file': name}
        target = BACKGROUNDS / name
        if previous.get(key) != entry or not target.is_file():
            fd, temporary = tempfile.mkstemp(prefix='.incoming-', suffix=suffix, dir=BACKGROUNDS)
            os.close(fd)
            try:
                if image.suffix.lower() in {'.heic', '.heif'}:
                    run(['magick', str(image) + '[0]', '-auto-orient', '-quality', '92', temporary], timeout=90)
                else: shutil.copyfile(image, temporary)
                os.replace(temporary, target)
            finally: Path(temporary).unlink(missing_ok=True)
        published[key] = entry
    if published: make_preview(BACKGROUNDS / next(iter(published.values()))['file'])
    # Never delete the image currently being displayed, even if removed upstream.
    retained = {entry['file'] for entry in published.values()}
    for entry in previous.values():
        name = entry['file']
        path = BACKGROUNDS / name
        if name not in retained and re.fullmatch(r'drive-[0-9a-f]{24}\.[a-z]+', name) and path != background():
            path.unlink(missing_ok=True)
    write(STATE / 'library.json', published)


def apply_photo(path):
    path = Path(path).expanduser().resolve()
    allowed = {p.resolve() for p in library()}
    if path not in allowed: raise ValueError('Choose a photo from the Personal Theme collection.')
    if not active(): run(['omarchy', 'theme', 'set', 'personal-theme'], env={**os.environ, 'OMARCHY_THEME_WAIT': '1'})
    run(['omarchy', 'theme', 'bg', 'set', path])
    write(STATE / 'rotation.json', {'active': True, 'at': time.time()})


def pick():
    if not library():
        notify('No photos yet. Choose a local folder or connect Drive under Settings.')
        return
    # The native picker returns a path. Applying it is the caller's responsibility.
    selected = run(['omarchy', 'menu', 'images', '--selected', str(background() or ''), BACKGROUNDS], timeout=86400)
    if selected: apply_photo(selected)


def next_photo():
    photos = [p for p in library() if p.resolve() != background()]
    if photos: apply_photo(random.choice(photos))


def tick():
    with locked('color'):
        if not enabled(): return
        config = settings()
        state = status()
        if state['transitionDue']:
            write(STATE / 'rotation.json', {'active': state['active'], 'at': time.time()})
        if not active(): return
        if state['rotationDue']: next_photo()
        path = background()
        expected = fingerprint(path, config)
        prior = read(STATE / 'color.json')
        if not config['adaptive'] or not expected or prior.get('fingerprint') == expected: return
        progress = {**prior, 'attempt': time.time(), 'error': ''}
        write(STATE / 'color.json', progress)
        generation = (CURRENT / 'theme.generation').read_text() if (CURRENT / 'theme.generation').exists() else ''
        try:
            run(['matugen', 'image', path, '--config', CONFIG / 'matugen.toml', '--mode', config['mode'], '--prefer', 'saturation'])
            current_generation = (CURRENT / 'theme.generation').read_text() if (CURRENT / 'theme.generation').exists() else ''
            if not enabled() or not active() or generation != current_generation or background() != path:
                return
            run(['omarchy', 'theme', 'refresh'], env={**os.environ, 'OMARCHY_THEME_WAIT': '1'})
            write(STATE / 'color.json', {'fingerprint': expected, 'attempt': 0, 'error': ''})
        except Exception as error:
            write(STATE / 'color.json', {**progress, 'error': str(error)[:300]})
            raise


def notify(message):
    # All callers pass our fixed copy, never photo names or network responses.
    if shutil.which('omarchy-notification-send'):
        subprocess.run(['omarchy-notification-send', 'Personal Theme', message], check=False)


def configure(key, value):
    if key == 'interval':
        value = int(value)
        if value not in (15, 30, 60, 120, 240): raise ValueError('Invalid rotation interval')
        update(interval=value)
        write(STATE / 'rotation.json', {'active': active(), 'at': time.time()})
    elif key == 'appearance':
        if value not in ('dark', 'light', 'smart', 'fixed'): raise ValueError('Invalid appearance')
        update(adaptive=value != 'fixed', **({'mode': value} if value != 'fixed' else {}))
        write(STATE / 'color.json', {})
    else: raise ValueError('Unknown setting')
    run(['omarchy', 'menu', 'refresh'])
    if enabled():
        run(['omarchy-shell', 'io.github.olivoil.personal-theme.service', 'refresh'])


def toggle_mode():
    current = resolved_mode() if settings()['mode'] == 'smart' else settings()['mode']
    configure('appearance', 'light' if current == 'dark' else 'dark')


def choose_folder():
    value = run(['zenity', '--file-selection', '--directory', '--title=Personal Theme: choose photo folder'])
    if value:
        update(source='local', folder=str(Path(value).expanduser().resolve()))
        request_sync()


def connect_drive():
    value = run(['omarchy', 'menu', 'input', 'Google Drive folder link'], timeout=86400)
    if not value: return
    match = re.fullmatch(r'(?:https://drive\.google\.com/drive/(?:u/\d+/)?folders/)?([A-Za-z0-9_-]{10,})(?:\?[^\s]*)?', value.strip())
    if not match: raise ValueError('Enter a Google Drive folder link or folder ID.')
    remotes = run(['rclone', 'listremotes']).splitlines()
    remote = settings()['drive_remote'] or 'personal-theme-drive:'
    if remote not in remotes:
        # Captured output can contain credentials; never print or log it.
        run(['rclone', 'config', 'create', remote.rstrip(':'), 'drive', 'scope', 'drive.readonly', 'config_is_local', 'true'], timeout=600)
    update(source='drive', drive_remote=remote, drive_folder=match.group(1))
    request_sync()


def request_sync():
    run(['omarchy-shell', 'io.github.olivoil.personal-theme.service', 'sync'])


def main():
    signal.signal(signal.SIGTERM, terminate_children)
    parser = argparse.ArgumentParser(description='Personal Theme for Omarchy')
    parser.add_argument('action', choices=['activate', 'deactivate', 'status', 'enabled', 'tick', 'sync', 'pick', 'set', 'next', 'pause', 'resume', 'is-paused', 'is-running', 'matches', 'configure', 'toggle-mode', 'choose-folder', 'connect-drive', 'request-sync', 'show-status', 'install-dependencies'])
    parser.add_argument('values', nargs='*')
    args = parser.parse_args()
    action, values = args.action, args.values
    try:
        if action == 'activate': activate(values[0])
        elif action == 'deactivate': deactivate(values[0])
        elif action == 'status': print(json.dumps(status()))
        elif action == 'enabled': sys.exit(0 if enabled() else 1)
        elif action == 'tick': tick()
        elif action == 'sync': sync()
        elif action == 'pick': pick()
        elif action == 'set': apply_photo(values[0])
        elif action == 'next': next_photo()
        elif action in ('pause', 'resume'):
            update(paused=action == 'pause')
            write(STATE / 'rotation.json', {'active': active(), 'at': time.time()})
            run(['omarchy', 'menu', 'refresh'])
        elif action in ('is-paused', 'is-running'):
            sys.exit(0 if settings()['paused'] == (action == 'is-paused') else 1)
        elif action == 'matches':
            config = settings()
            actual = str(config['interval']) if values[0] == 'interval' else (config['mode'] if config['adaptive'] else 'fixed')
            sys.exit(0 if actual == values[1] else 1)
        elif action == 'configure': configure(*values)
        elif action == 'toggle-mode': toggle_mode()
        elif action == 'choose-folder': choose_folder()
        elif action == 'connect-drive': connect_drive()
        elif action == 'request-sync': request_sync()
        elif action == 'show-status':
            s = status()
            message = f'{s["count"]} photos. Rotation ' + ('paused.' if s['paused'] else (f'every {s["interval"]} minutes.' if s['active'] else 'inactive on other themes.'))
            if s['syncError']: message += ' Photo sync needs attention; check the plugin log.'
            if s['colorError']: message += ' Color generation needs attention; check the plugin log.'
            notify(message)
        elif action == 'install-dependencies':
            subprocess.Popen(['omarchy-launch-floating-terminal-with-presentation', 'omarchy pkg add matugen rclone imagemagick zenity'])
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f'Personal Theme: {error}', file=sys.stderr)
        if action not in ('tick', 'sync', 'status', 'activate', 'deactivate'):
            notify('Action could not finish. Check the plugin log and source settings.')
        sys.exit(1)


if __name__ == '__main__': main()
