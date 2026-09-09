"""Browser contract tests with local assets and deterministic API/WS fixtures."""
import copy
import json
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


def overview():
    now = datetime(2026, 9, 8, 10, 30, tzinfo=timezone.utc)
    return {
        'car': {'id': 1, 'number': '00123456', 'revision': 0}, 'context_error': None,
        'totals': {'total': 1248, 'by_class': {'25kg':820,'50kg':420,'empty':8}, 'weight_kg':41500},
        'recent': {'events':[{'id':n,'car_id':1,'counted_at':now.isoformat(),'class':'25kg'} for n in range(6,0,-1)], 'next_cursor':1},
        'series': {'buckets':[{'at':(now-timedelta(minutes=29-i)).isoformat(),'count':i%5} for i in range(30)]},
        'database_at': now.isoformat(),
        'runtime': {'status':{'state':'online','label':'Online','reason':'Waiting for bags','camera':'Connected','detector':'Running','tracker':'Running','updated_at':now.isoformat()},
                    'data':{'run_id':'test-run','alerts':[], 'last_detection':{'track_id':10,'observed_at':now.isoformat(),'class':'50kg','state':'Waiting for handover','thumbnail':None}}},
    }


@pytest.fixture
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def screen(browser, request):
    context = browser.new_context(viewport={'width':1366,'height':768}, locale='en-GB',
                                  timezone_id=getattr(request, 'param', 'Asia/Almaty'))
    page = context.new_page()
    data = overview()
    wires = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request):
        path = request.request.url.split('http://dashboard.test')[-1].split('?')[0]
        if path == '/api/v1/dashboard/snapshot':
            request.fulfill(json=data)
        elif path == '/api/v1/events':
            request.fulfill(json={'events':data['recent']['events'],'next_cursor':None})
        elif path == '/api/v1/auth/login':
            request.fulfill(json={'access_token':'test-token'})
        elif path == '/api/v1/wagons/1':
            edit = request.request.post_data_json
            if edit['revision'] != data['car']['revision']:
                request.fulfill(status=409,json={'detail':{'current':data['car']}})
            else:
                data['car']['number'] = edit['number'].strip()
                data['car']['revision'] += 1
                request.fulfill(json=data['car'])
        elif path == '/api/v1/video/stream':
            request.fulfill(status=503,body='unavailable')
        else:
            asset = ROOT / 'frontend' / ('index.html' if path == '/' else path.lstrip('/'))
            request.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(asset)[0] or 'text/plain')
    context.route('http://dashboard.test/**', route)
    def wire(ws):
        wires.append(ws)
        ws.send(json.dumps({'type':'snapshot','sequence':1,'data':data}))
    context.route_web_socket('**/api/v1/dashboard/live', wire)
    page.goto('http://dashboard.test/')
    expect(page.locator('#count')).to_have_text('1,248')
    yield page, data, wires, errors
    context.close()


@pytest.mark.parametrize('screen', ['Asia/Almaty', 'America/New_York'], indirect=True)
def test_layout_clock_history_and_stable_document(screen):
    page, data, wires, errors = screen
    page.evaluate('window.documentIdentity = document.documentElement')
    assert page.title() == 'Bag Counter'
    expected = '15:30:00' if page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone') == 'Asia/Almaty' else '06:30:00'
    expect(page.locator('#detection-time')).to_have_text(expected)
    expect(page.locator('#events tr').first).to_contain_text(expected)
    viewports = [(1366,768),(1500,950),(1920,950),(1920,1080)]
    viewports += [(width,height) for width in (1499,1500,1920)
                  for height in (949,950,951,999,1000,1001)]
    for width,height in viewports:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), page.evaluate('document.documentElement.scrollHeight')
        last_row = page.locator('#events tr').last.bounding_box()
        table = page.locator('.table-wrap').bounding_box()
        assert last_row['y'] + last_row['height'] <= table['y'] + table['height'] + 1
        for selector in ('#count', '#car-number', '#camera-status', '#detector-status',
                         '#tracker-status', '#detection-state', '#chart', '#video-container', '.alert-strip'):
            expect(page.locator(selector)).to_be_in_viewport(ratio=1)
        assert page.locator('#count').evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') >= 64
    page.set_viewport_size({'width':1920,'height':1080})
    assert page.locator('#count').evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') == 86
    page.screenshot(path='/tmp/bag-dashboard-desktop.png', full_page=True)
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    expect(page.locator('#count')).to_have_text('1,248')
    assert page.evaluate('window.documentIdentity === document.documentElement')
    page.locator('#history').click()
    expect(page.locator('#history-events tr')).to_have_count(6)
    drawer = page.locator('#history-dialog').bounding_box()
    assert drawer['x'] + drawer['width'] == page.viewport_size['width']
    page.locator('#history-dialog .close-dialog').click()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors


def test_edit_survives_updates_conflict_and_save(screen):
    page, data, wires, errors = screen
    page.locator('#edit-car').click()
    page.locator('#car-input').fill('00987654')
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    expect(page.locator('#car-input')).to_have_value('00987654')
    expect(page.locator('#car-input')).to_be_focused()
    page.locator('#username').fill('operator')
    page.locator('#password').fill('test-password')
    data['car']['revision'] += 1
    page.locator('#save-car').click()
    expect(page.locator('#car-error')).to_contain_text('Car information changed')
    expect(page.locator('#car-input')).to_have_value('00987654')
    page.locator('#save-car').click()
    expect(page.locator('#car-dialog')).not_to_be_visible()
    expect(page.locator('#car-number')).to_have_text('00987654')
    expect(page.locator('#count')).to_have_text('1,248')
    assert data['car']['id'] == 1 and not errors


def test_state_updates_duplicates_alerts_and_preview_failure(screen):
    page, data, wires, errors = screen
    data['runtime']['status'].update(state='offline',label='Offline',detector='Stopped',tracker='Stopped',reason='Bag processing interrupted')
    data['runtime']['data']['alerts']=[{'code':'processing','message':'Bag processing interrupted','active':True,'last_at':data['database_at'],'count':4,'severity':'error'}]
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    expect(page.locator('#status')).to_have_text('Offline')
    expect(page.locator('#alert-title')).to_have_text('Bag processing interrupted')
    bad = copy.deepcopy(data)
    bad['totals']['total'] = 9999
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':bad}))
    expect(page.locator('#count')).to_have_text('1,248')
    page.locator('#start-video').click()
    expect(page.locator('#video-placeholder strong')).to_have_text('Camera preview unavailable')
    page.locator('#expand-video').click()
    page.wait_for_function('document.fullscreenElement?.id === "video-container"')
    page.evaluate('document.exitFullscreen()')
    page.locator('#show-alerts').click()
    expect(page.locator('.alert-entry')).to_have_count(1)
    expect(page.locator('.alert-entry')).to_contain_text('4 occurrences')
    assert not errors


def test_empty_context_unknown_detection_and_recovered_alert(screen):
    page, data, wires, errors = screen
    data.update(car=None, context_error='no_active_car', series={'buckets':[]},
                recent={'events':[], 'next_cursor':None})
    data['runtime']['data']['last_detection'] = None
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    expect(page.locator('#count')).to_have_text('—')
    expect(page.locator('#edit-car')).to_be_disabled()
    expect(page.locator('#alert-title')).to_have_text('No active car')
    expect(page.locator('#events')).to_have_text('No saved counts yet')
    expect(page.locator('#chart')).to_contain_text('No count history available')
    expect(page.locator('#detection-class')).to_have_text('No detection yet')
    data['runtime']['data'].update(last_detection={'class':None,'thumbnail':None},
        alerts=[{'code':'camera','message':'Camera signal interrupted','active':False,
                 'last_at':data['database_at'],'count':10,'severity':'warning'}])
    wires[0].send(json.dumps({'type':'snapshot','sequence':3,'data':data}))
    expect(page.locator('#detection-class')).to_have_text('Unknown')
    expect(page.locator('#thumbnail-empty')).to_have_text('No image')
    page.locator('#show-alerts').click()
    expect(page.locator('[data-incident="counting:camera"]')).to_contain_text('Recovered')
    expect(page.locator('#detection-state')).to_have_text('Unconfirmed')
    assert not errors


def test_communication_episodes_recover_independently_and_survive_snapshots(screen):
    page, data, wires, errors = screen
    # Hold reconnect timers so transport recovery can be checked independently.
    page.clock.install()
    page.clock.pause_at(datetime.now(timezone.utc) + timedelta(seconds=1))
    page.locator('#show-alerts').click()
    wires[0].close()
    ws = page.locator('[data-incident="communication:websocket"]')
    expect(ws).to_contain_text('Active')
    page.evaluate('poll()')  # a successful HTTP refresh cannot recover WebSocket
    expect(ws).to_contain_text('Active')
    expect(page.locator('#status')).to_have_text('Online')
    expect(ws).to_contain_text('First ')
    expect(ws).to_contain_text('Last ')
    data['runtime']['status'].update(state='unavailable', label='Status unavailable')
    page.evaluate('poll()')
    bridge = page.locator('[data-incident="communication:redis"]')
    expect(bridge).to_contain_text('Active')
    page.clock.run_for(3100)  # valid snapshot on the reconnected WebSocket
    expect(ws).to_contain_text('Recovered')
    expect(bridge).to_contain_text('Active')
    page.route('**/api/v1/dashboard/snapshot', lambda route: route.abort())
    page.evaluate('poll()')
    http = page.locator('[data-incident="communication:http"]')
    expect(http).to_contain_text('Active')
    data['runtime']['status'].update(state='online', label='Online')
    wires[-1].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    expect(bridge).to_contain_text('Recovered')
    expect(http).to_contain_text('Active')  # WebSocket success cannot recover HTTP
    expect(page.locator('#status')).to_have_text('Online')
    page.unroute('**/api/v1/dashboard/snapshot')
    page.evaluate('poll()')
    expect(http).to_contain_text('Recovered')
    expect(page.locator('#alert-title')).to_have_text('No active warnings')
    # A CV run change replaces runtime observations, preserving communication history.
    data['runtime']['data'].update(run_id='new-run', last_detection=None)
    wires[-1].send(json.dumps({'type':'snapshot','sequence':3,'data':data}))
    expect(page.locator('#detection-class')).to_have_text('No detection yet')
    expect(page.locator('.alert-entry')).to_have_count(3)
    expect(ws).to_contain_text('Recovered')
    wires[-1].close()
    expect(ws).to_have_count(2)
    expect(ws.filter(has_text='Active')).to_have_count(1)
    expect(page.locator('#count')).to_have_text('1,248')
    assert not errors


def test_incidents_coalesce_bound_history_and_keep_active_context(screen):
    page, data, wires, errors = screen
    page.clock.install()
    page.clock.pause_at(datetime.now(timezone.utc) + timedelta(seconds=1))
    page.locator('#show-alerts').click()
    data['runtime']['data']['alerts'] = [{
        'code':'persistence', 'active':True, 'first_at':data['database_at'],
        'last_at':data['database_at'], 'count':3, 'severity':'error',
        'message':'rtsp://private:secret@camera /private/db traceback secret'}]
    page.evaluate('(data) => render(data)', data)
    warning = page.locator('[data-incident="counting:persistence"]')
    expect(warning).to_contain_text('3 occurrences')
    page.route('**/api/v1/dashboard/snapshot', lambda route: route.abort())
    page.evaluate('poll()')
    page.evaluate('poll()')
    expect(page.locator('[data-incident="communication:http"]')).to_have_count(1)
    expect(page.locator('[data-incident="communication:http"]')).to_contain_text('2 occurrences')
    page.unroute('**/api/v1/dashboard/snapshot')
    page.evaluate('poll()')
    # Exercise many independent outages through the real HTTP polling path.
    for _ in range(22):
        page.route('**/api/v1/dashboard/snapshot', lambda route: route.abort())
        page.evaluate('poll()')
        page.unroute('**/api/v1/dashboard/snapshot')
        page.evaluate('poll()')
    expect(page.locator('.alert-entry')).to_have_count(20)
    expect(warning).to_contain_text('Active')  # evict recovered episodes first
    expect(warning).to_contain_text('3 occurrences')  # snapshots are not new failures
    assert 'secret' not in page.locator('#alert-list').inner_text()
    assert 'traceback' not in page.locator('#alert-list').inner_text()
    assert not errors


def test_camera_warning_merges_and_unknown_runtime_does_not_claim_recovery(screen):
    page, data, wires, errors = screen
    page.locator('#show-alerts').click()
    data['runtime']['status'].update(camera='Unavailable', reason='Counting interrupted: camera unavailable')
    report = {'code':'camera', 'active':True, 'first_at':data['database_at'],
              'last_at':data['database_at'], 'count':4}
    data['runtime']['data']['alerts'] = [report]
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    camera = page.locator('[data-incident="counting:camera"]')
    expect(camera).to_have_count(1)  # runtime alert and derived camera status merge
    expect(camera).to_contain_text('4 occurrences')
    missing = copy.deepcopy(data)
    missing['runtime'].update(data=None, status={
        'state':'offline', 'label':'Offline', 'camera':'Unknown', 'detector':'Stopped',
        'tracker':'Stopped', 'reason':'Counting service is not reporting'})
    wires[0].send(json.dumps({'type':'snapshot','sequence':3,'data':missing}))
    expect(page.locator('#status')).to_have_text('Offline')
    expect(camera).to_contain_text('Active')
    report['active'] = False
    data['runtime']['status'].update(camera='Connected', reason='Waiting for bags')
    wires[0].send(json.dumps({'type':'snapshot','sequence':4,'data':data}))
    expect(camera).to_contain_text('Recovered')
    expect(page.locator('#alert-title')).to_have_text('No active warnings')
    assert not errors


def test_server_clock_adjustment_does_not_freeze_saved_counts(screen):
    page, data, wires, errors = screen
    data['database_at'] = '2026-09-08T09:30:00+00:00'
    data['totals']['total'] = 1249
    wires[0].send(json.dumps({'type':'snapshot','sequence':2,'data':data}))
    # Reject a briefly reordered response, but never pin totals forever to wall time.
    expect(page.locator('#count')).to_have_text('1,248')
    expect(page.locator('#count')).to_have_text('1,249', timeout=11000)
    assert not errors
