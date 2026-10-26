"""Create an explicit source-only build kit; never archive the working tree."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'main.py', 'fucker.py', 'utils.py', 'logger.py', 'ObjDict.py', 'zd_utils.py',
    'push.py', 'sign.py', 'profile_lock.py', 'windows_entry.py', 'meta.json',
    'requirements.txt', 'requirements-build-windows.txt', 'fuckZHS.spec', 'LICENSE', '.gitignore',
    'scripts/build_windows.ps1', 'scripts/prepare_windows_source.py',
    'share_gui.py', 'share_worker.py', 'share_policy.py', 'share_protocol.py',
    'tests/test_share_gui.py', 'tests/test_share_policy.py', 'tests/test_share_protocol.py',
    'packaging/windows/README.txt', 'tests/test_fedora_safety.py',
    'tests/test_profile_lock.py', 'docs/WINDOWS_BUILD.md',
    '.github/workflows/build-windows.yml',
)


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / 'fuckZHS-Windows-build-kit.zip'
    # Compare in memory only; never put local secrets in the archive or audit log.
    secrets = []
    for key_path in (ROOT/'key', ROOT/'profiles/nagi/key'):
        if key_path.is_file():
            value = key_path.read_bytes().strip()
            if value:
                secrets.append(value)
    sources = {name: (ROOT/name).read_bytes() for name in FILES}
    for name, data in sources.items():
        if any(secret in data for secret in secrets):
            raise RuntimeError(f'Privacy audit failed for {name}; archive not created')
    manifest = '\n'.join(f'{hashlib.sha256(data).hexdigest()}  {name}'
                         for name, data in sources.items()) + '\n'
    prefix = 'fuckZHS-Windows-build/'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in sources.items():
            bundle.writestr(prefix + name, data)
        bundle.writestr(prefix + 'MANIFEST.sha256', manifest)
    with zipfile.ZipFile(archive) as bundle:
        expected = {prefix+name for name in FILES} | {prefix+'MANIFEST.sha256'}
        if set(bundle.namelist()) != expected or bundle.testzip() is not None:
            raise RuntimeError('Archive integrity or allowlist validation failed')
    audit = {
        'artifact': archive.name,
        'status': 'PASS',
        'source_files': len(FILES),
        'explicit_allowlist_only': True,
        'profiles_config_cookies_logs_and_qr_excluded': True,
        'local_key_values_absent': True,
        'windows_exe_built': False,
        'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    (output/'windows-build-audit.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
