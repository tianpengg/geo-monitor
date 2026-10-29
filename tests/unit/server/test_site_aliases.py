import json

import pytest

from internal.server.services import inventory
from internal.storage.database import MIGRATIONS, Database


def save(admin, aliases, **fields):
    return admin.put('/api/site', json={'domain': 'example.com', 'aliases': aliases, **fields})


def test_alias_upgrade_preserves_site_directory_and_credentials(tmp_path):
    database = Database(tmp_path / 'legacy.sqlite3')
    database.migrate(MIGRATIONS[:-1])
    with database.transaction() as conn:
        conn.execute("INSERT INTO site(id,source_id,domain,timezone,token_hash) VALUES('s','c','example.com','UTC','hash')")
        conn.execute("INSERT INTO content_pages VALUES('s','example.com','/kept','title',1)")
    database.migrate()
    database.migrate()
    with database.read() as conn:
        site = dict(conn.execute('SELECT * FROM site').fetchone())
        assert (site['id'], site['source_id'], site['token_hash'], site['aliases']) == ('s', 'c', 'hash', '[]')
        assert conn.execute('SELECT title FROM content_pages').fetchone()[0] == 'title'
        assert conn.execute('PRAGMA user_version').fetchone()[0] == len(MIGRATIONS)


def test_alias_normalization_persistence_and_legacy_updates(admin, source):
    saved = save(admin, [' WWW.Example.COM. ', 'www.example.com', 'EXAMPLE.COM', '例子.测试']).json()
    assert saved['aliases'] == ['www.example.com', 'xn--fsqu00a.xn--0zwm56d']
    assert saved['id'] == source['site_id'] and saved['source_id'] == source['source_id']
    assert admin.get('/api/site').json() == saved
    with admin.app.state.database.read() as conn:
        before = dict(conn.execute('SELECT * FROM site').fetchone())
    updated = admin.put('/api/site', json={'domain': 'example.com', 'timezone': 'UTC'}).json()
    assert updated['aliases'] == saved['aliases']
    assert 'token_hash' not in updated
    with admin.app.state.database.read() as conn:
        assert conn.execute('SELECT token_hash FROM site').fetchone()[0] == before['token_hash']
    assert save(admin, []).json()['aliases'] == []
    save(admin, ['www.example.com']).raise_for_status()
    changed = admin.put('/api/site', json={'domain': 'other.example'}).json()
    assert changed['aliases'] == [] and changed['id'] == source['site_id']


@pytest.mark.parametrize('aliases', [
    ['https://www.example.com'], ['*.example.com'], ['www.example.com/page'],
    ['user@www.example.com'], ['www.example.com:443'], ['127.0.0.1'], ['::1'],
    ['localhost'], ['bad\n.example.com'], ['a' * 254], [None], 'www.example.com',
    ['.'.join(['例' * 32] * 7)],
    [f'alias{i}.example.com' for i in range(11)],
])
def test_invalid_aliases_rejected_atomically(admin, source, aliases):
    original = admin.get('/api/site').json()
    assert save(admin, aliases).status_code == 422
    assert admin.get('/api/site').json() == original


def test_alias_updates_require_login_and_csrf(admin, source):
    del admin.headers['X-CSRF-Token']
    assert save(admin, ['www.example.com']).status_code == 403
    assert admin.get('/api/site').json()['aliases'] == []
    admin.cookies.clear()
    assert save(admin, ['www.example.com']).status_code == 401
    assert admin.get('/api/site').status_code == 401


@pytest.mark.parametrize('format', ['json', 'xml', 'csv'])
def test_alias_import_matches_exact_hosts_and_deduplicates_paths(admin, source, format):
    save(admin, ['www.example.com']).raise_for_status()
    urls = ['https://example.com/a?q=1', 'https://www.example.com/a#part', 'https://www.example.com/b']
    text = json.dumps(urls) if format == 'json' else (
        '<urlset>' + ''.join(f'<url><loc>{url}</loc></url>' for url in urls) + '</urlset>'
        if format == 'xml' else 'url\n' + '\n'.join(urls)
    )
    result = admin.post('/api/inventory/import', json={'format': format, 'text': text})
    assert result.json() == {'accepted': 2, 'added': 2, 'updated': 0, 'total': 2}
    invalid = admin.post('/api/inventory/import', json={
        'format': 'json', 'text': '["/partial", "https://sub.www.example.com/outside"]',
    })
    assert invalid.status_code == 400 and '官网配置' in invalid.json()['detail']
    save(admin, []).raise_for_status()
    assert admin.get('/api/inventory').json()['total'] == 2
    assert admin.post('/api/inventory/import', json={
        'format': 'json', 'text': '["https://www.example.com/removed"]',
    }).status_code == 400


def test_stale_import_cannot_commit_after_alias_change(admin, source):
    stale = save(admin, ['www.example.com']).json()
    save(admin, []).raise_for_status()
    with pytest.raises(ValueError, match='配置已变更'):
        inventory.import_pages(admin.app.state.database, stale, '["https://www.example.com/stale"]', 'json')
    assert admin.get('/api/inventory').json()['total'] == 0
