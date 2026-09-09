import subprocess
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = ('docker-compose.yml', 'docker-compose-2CPU.yml', 'docker-compose-4CPU.yml')


def credential_environment(name, inputs):
    """Expand the actual Compose credential expressions with isolated test inputs.

    These nested :- expressions use the same unset/empty fallback semantics in
    Compose and bash. This static wiring check is not a built Compose acceptance.
    """
    environment = yaml.safe_load((ROOT/name).read_text())['services']['edge-cv']['environment']
    result = {}
    for key, legacy, fallback in [('API_ADMIN_USER', 'ADMIN_USERNAME', 'admin'),
                                  ('API_ADMIN_PASS', 'ADMIN_PASSWORD', 'changeme')]:
        expression = next(item.split('=', 1)[1] for item in environment if item.startswith(key+'='))
        assert expression == '${'+key+':-${'+legacy+':-'+fallback+'}}'
        result[key] = subprocess.run(['bash', '-c', 'printf %s "'+expression+'"'],
            env={'PATH':os.defpath, **inputs}, capture_output=True, text=True, check=True).stdout
    assert not any(item.startswith(('ADMIN_USERNAME=', 'ADMIN_PASSWORD=')) for item in environment)
    return result


def test_compose_credential_fallbacks():
    for name in COMPOSE_FILES:
        for inputs in ({}, {'API_ADMIN_USER':'', 'API_ADMIN_PASS':'',
                            'ADMIN_USERNAME':'', 'ADMIN_PASSWORD':''}):
            assert credential_environment(name, inputs) == {'API_ADMIN_USER':'admin', 'API_ADMIN_PASS':'changeme'}


def test_entrypoint_dispatches_supplied_roles():
    for role in ('worker', 'beat'):
        result = subprocess.run(['bash', str(ROOT/'entrypoint.sh'), '/bin/echo', role], capture_output=True, text=True, check=True)
        assert result.stdout.strip() == role
        assert 'Starting CV' not in result.stdout


def test_compose_roles_and_local_assets():
    for name in ('docker-compose.yml','docker-compose-2CPU.yml','docker-compose-4CPU.yml'):
        services = yaml.safe_load((ROOT/name).read_text())['services']
        assert services['dashboard']['build']['dockerfile'] == 'Dockerfile.operator'
        assert ' worker ' in services['celery-worker']['command']
        assert ' beat ' in services['celery-beat']['command']
        assert 'inspect ping' in services['celery-worker']['healthcheck']['test'][1]
        assert services['celery-beat']['healthcheck']['disable']
    assert 'server dashboard:80;' in (ROOT/'nginx.conf').read_text()
    assert 'location /ws/' in (ROOT/'nginx.conf').read_text()
    assert 'location /api/' in (ROOT/'nginx.conf').read_text()
    for asset in ('index.html','styles.css','app.js'):
        assert 'https://fonts.' not in (ROOT/'frontend'/asset).read_text()
