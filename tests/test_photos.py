import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('photos', ROOT / 'photos.py')
photos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(photos)


class PersonalThemeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        mapping = {
            'HOME': self.home, 'CONFIG': self.home / '.config/plugin',
            'STATE': self.home / '.local/state/plugin', 'CACHE': self.home / '.cache/plugin',
            'THEME': self.home / '.config/omarchy/themes/personal-theme',
            'BACKGROUNDS': self.home / '.config/omarchy/backgrounds/personal-theme',
            'CURRENT': self.home / '.local/state/omarchy/current',
            'MENU': self.home / '.config/omarchy/extensions/omarchy-menu.jsonc',
        }
        self.patches = [patch.object(photos, key, value) for key, value in mapping.items()]
        for p in self.patches: p.start()
        self.addCleanup(self.temporary.cleanup)
        for p in self.patches: self.addCleanup(p.stop)
        photos.CURRENT.mkdir(parents=True)
        photos.BACKGROUNDS.mkdir(parents=True)
        photos.THEME.mkdir(parents=True)
        photos.write(photos.STATE / 'lease.json', {'enabled': True, 'lease': 'new'})
        photos.write(photos.CONFIG / 'settings.json', photos.DEFAULTS)
        (photos.CURRENT / 'theme.name').write_text('personal-theme\n')
        self.first = photos.BACKGROUNDS / 'a photo.jpg'
        self.second = photos.BACKGROUNDS / 'another photo.jpg'
        self.first.write_bytes(b'first')
        self.second.write_bytes(b'second')
        (photos.CURRENT / 'background').symlink_to(self.first)

    def test_picker_result_is_applied_including_spaces(self):
        with patch.object(photos, 'run', return_value=str(self.second)) as command, patch.object(photos, 'apply_photo') as apply:
            photos.pick()
        apply.assert_called_once_with(str(self.second))
        self.assertEqual(command.call_args.args[0][:3], ['omarchy', 'menu', 'images'])

    def test_picker_cancel_does_not_apply(self):
        with patch.object(photos, 'run', return_value=''), patch.object(photos, 'apply_photo') as apply:
            photos.pick()
        apply.assert_not_called()

    def test_selection_outside_collection_is_rejected(self):
        with self.assertRaises(ValueError), patch.object(photos, 'run') as command:
            photos.apply_photo(self.home / 'outside.jpg')
        command.assert_not_called()

    def test_photo_selection_does_not_resume_paused_rotation(self):
        photos.update(paused=True)
        with patch.object(photos, 'run') as command:
            photos.apply_photo(self.second)
        self.assertTrue(photos.settings()['paused'])
        self.assertEqual(command.call_args.args[0], ['omarchy', 'theme', 'bg', 'set', self.second.resolve()])

    def test_regular_theme_never_rotates_or_recolors(self):
        (photos.CURRENT / 'theme.name').write_text('tokyo-night\n')
        photos.write(photos.STATE / 'rotation.json', {'active': True, 'at': 0})
        with patch.object(photos, 'run') as command, patch.object(photos, 'next_photo') as advance:
            photos.tick()
        advance.assert_not_called()
        command.assert_not_called()
        self.assertFalse(photos.status()['rotationDue'])

    def test_paused_rotation_is_not_due(self):
        photos.update(paused=True)
        photos.write(photos.STATE / 'rotation.json', {'active': True, 'at': 0})
        self.assertFalse(photos.status(now=100000)['rotationDue'])

    def test_disabled_plugin_has_no_due_work(self):
        photos.write(photos.STATE / 'lease.json', {'enabled': False})
        s = photos.status(now=100000)
        self.assertFalse(any(s[k] for k in ('rotationDue', 'colorDue', 'syncDue', 'transitionDue')))
        with patch.object(photos, 'run') as command:
            photos.tick()
            photos.sync()
        command.assert_not_called()

    def test_selecting_theme_resets_countdown(self):
        photos.write(photos.STATE / 'rotation.json', {'active': False, 'at': 0})
        with patch.object(photos, 'run'), patch.object(photos, 'next_photo') as advance:
            photos.tick()
        advance.assert_not_called()
        self.assertGreater(photos.read(photos.STATE / 'rotation.json')['at'], 0)

    def test_due_rotation_advances_once(self):
        photos.write(photos.STATE / 'rotation.json', {'active': True, 'at': 0})
        photos.update(adaptive=False)
        with patch.object(photos, 'next_photo') as advance:
            photos.tick()
        advance.assert_called_once()

    def test_other_theme_selected_during_generation_is_not_refreshed(self):
        photos.write(photos.STATE / 'rotation.json', {'active': True, 'at': 99999999999})
        def changed_theme(argv, **kwargs):
            if argv[0] == 'matugen': (photos.CURRENT / 'theme.name').write_text('tokyo-night\n')
            return ''
        with patch.object(photos, 'run', side_effect=changed_theme) as command:
            photos.tick()
        self.assertEqual(len(command.call_args_list), 1)

    def test_stale_service_shutdown_cannot_disable_new_service(self):
        with patch.object(photos, 'install_menu') as menu:
            photos.deactivate('old')
        self.assertTrue(photos.enabled())
        menu.assert_not_called()

    def test_prototype_migration_preserves_photos_source_and_pause(self):
        (photos.CONFIG / 'settings.json').unlink()
        source = self.home / '.config/omarchy-drive-wallpapers/source.json'
        photos.write(source, {'remote': 'existing-drive:', 'folder_id': 'example-folder-id'})
        paused = self.home / '.local/state/omarchy/personal-wallpaper.paused'
        paused.touch()
        old_photos = self.home / '.config/omarchy/backgrounds/matugen-auto'
        old_photos.mkdir(parents=True)
        (old_photos / 'old.jpg').write_bytes(b'personal original')
        photos.migrate()
        config = photos.settings()
        self.assertEqual(config['source'], 'drive')
        self.assertEqual(config['drive_remote'], 'existing-drive:')
        self.assertTrue(config['paused'])
        self.assertEqual((photos.BACKGROUNDS / 'old.jpg').read_bytes(), b'personal original')
        self.assertTrue((old_photos / 'old.jpg').exists())

    def test_disable_withdraws_only_plugin_menu_entries(self):
        photos.MENU.parent.mkdir(parents=True)
        photos.MENU.write_text('{"custom.notes":{"label":"Notes"}}')
        with patch.object(photos, 'run'):
            photos.install_menu()
            photos.deactivate('new')
        self.assertFalse(photos.enabled())
        self.assertEqual(photos.read(photos.MENU), {'custom.notes': {'label': 'Notes'}})

    def test_menu_is_under_appearance_and_preserves_unrelated_entries(self):
        photos.MENU.parent.mkdir(parents=True)
        photos.MENU.write_text('// custom menu\n{"custom.notes":{"label":"Notes","action":"notes"}}')
        with patch.object(photos, 'run'):
            photos.install_menu()
        values = photos.read(photos.MENU)
        self.assertIn('appearance.personal-theme.choose', values)
        self.assertEqual(values['custom.notes']['action'], 'notes')
        self.assertFalse(any(k.startswith('style.personal-') for k in values))

    def test_jsonc_urls_and_markup_are_data(self):
        result = photos.menu_json('''{
            // comment
            "custom": {"action":"https://example.com/path", "label":"<img src=x>",},
        }''')
        self.assertEqual(result['custom']['action'], 'https://example.com/path')
        self.assertEqual(result['custom']['label'], '<img src=x>')
        # Our shared tooltip has only translated, plugin-owned text.
        widget = (ROOT / 'BarWidget.qml').read_text()
        self.assertNotIn('snapshot.', widget)

    def test_publish_converts_heic_and_keeps_originals(self):
        source = self.home / 'source'
        source.mkdir()
        image = source / 'photo with spaces.png'
        subprocess.run(['magick', '-size', '20x10', 'xc:#426384', str(image)], check=True)
        heic = source / 'iPad.heic'
        subprocess.run(['magick', str(image), str(heic)], check=True, capture_output=True)
        photos.publish(source)
        items = photos.read(photos.STATE / 'library.json')
        self.assertEqual(len(items), 2)
        self.assertTrue(items['iPad.heic']['file'].endswith('.jpg'))
        self.assertTrue(heic.exists())
        self.assertTrue((photos.THEME / 'preview.png').is_file())
        original_target = photos.BACKGROUNDS / items['photo with spaces.png']['file']
        before = original_target.stat().st_mtime_ns
        photos.publish(source)
        self.assertEqual(original_target.stat().st_mtime_ns, before)

    def test_sync_error_preserves_previous_collection(self):
        photos.update(source='drive', drive_remote='test:', drive_folder='test-id')
        with patch.object(photos, 'run', side_effect=RuntimeError('rclone failed')):
            with self.assertRaises(RuntimeError): photos.sync()
        self.assertTrue(self.first.exists())
        self.assertEqual(photos.read(photos.STATE / 'sync.json')['error'], 'rclone failed')

    def test_invalid_config_is_rejected(self):
        with self.assertRaises(ValueError): photos.configure('interval', '-1')
        with self.assertRaises(ValueError): photos.configure('appearance', 'unknown')

    def test_light_mode_requests_matching_palette_without_resuming(self):
        photos.update(paused=True)
        with patch.object(photos, 'run') as command:
            photos.configure('appearance', 'light')
        self.assertEqual(photos.settings()['mode'], 'light')
        self.assertTrue(photos.settings()['adaptive'])
        self.assertTrue(photos.settings()['paused'])
        self.assertTrue(photos.status()['colorDue'])
        self.assertIn(['omarchy-shell', 'io.github.olivoil.personal-theme.service', 'refresh'],
                      [call.args[0] for call in command.call_args_list])

    def test_toggle_mode_round_trip(self):
        with patch.object(photos, 'run'):
            photos.toggle_mode()
            self.assertEqual(photos.settings()['mode'], 'light')
            photos.toggle_mode()
            self.assertEqual(photos.settings()['mode'], 'dark')

    def test_color_mode_is_accessible_from_main_plugin_menu(self):
        with patch.object(photos, 'run'): photos.install_menu()
        menu = photos.read(photos.MENU)
        self.assertIn('appearance.personal-theme.colors.light', menu)
        self.assertIn('appearance.personal-theme.colors.dark', menu)
        self.assertNotIn('appearance.personal-theme.settings.colors', menu)

    def test_photo_matching_passes_smart_mode_to_matugen(self):
        with patch.object(photos, 'run'):
            photos.configure('appearance', 'smart')
        self.assertEqual(photos.settings()['mode'], 'smart')
        with patch.object(photos, 'run') as command:
            photos.tick()
        matugen = [call.args[0] for call in command.call_args_list if call.args[0][0] == 'matugen'][0]
        self.assertEqual(matugen[matugen.index('--mode') + 1], 'smart')

    def test_toggle_from_auto_overrides_actual_displayed_mode(self):
        photos.update(mode='smart')
        (photos.THEME / 'colors.toml').write_text('mode = "dark"\n')
        with patch.object(photos, 'run'): photos.toggle_mode()
        self.assertEqual(photos.settings()['mode'], 'light')
        photos.update(mode='smart')
        (photos.THEME / 'colors.toml').write_text('mode = "light"\n')
        with patch.object(photos, 'run'): photos.toggle_mode()
        self.assertEqual(photos.settings()['mode'], 'dark')

    def test_auto_selection_and_resolved_mode_are_separate(self):
        photos.update(mode='smart')
        (photos.THEME / 'colors.toml').write_text('mode = "light"\n')
        state = photos.status()
        self.assertEqual(state['mode'], 'smart')
        self.assertEqual(state['resolvedMode'], 'light')

    def test_retained_service_repairs_menu_after_backend_update(self):
        photos.write(photos.STATE / 'menu-revision.json', {'revision': 'previous-version'})
        with patch.object(photos, 'run'):
            photos.refresh_menu_after_update()
        menu = photos.read(photos.MENU)
        self.assertIn('appearance.personal-theme.colors.auto', menu)
        with patch.object(photos, 'install_menu') as install:
            photos.refresh_menu_after_update()
        install.assert_not_called()

    def test_disabled_plugin_does_not_restore_menu(self):
        photos.write(photos.STATE / 'lease.json', {'enabled': False})
        with patch.object(photos, 'install_menu') as install:
            photos.refresh_menu_after_update()
        install.assert_not_called()


if __name__ == '__main__': unittest.main()
