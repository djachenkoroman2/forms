#!/usr/bin/env python3
"""Integration check in a real viewer: fill a PDF form in headless Firefox (PDF.js), save it with
PDF.js's own save routine, reopen the saved file and screenshot it. Uses WebDriver BiDi and a
temporary Firefox profile. Requires Firefox and the websocket-client package.

Usage: firefox_check.py FORM.pdf VALUES.json SAVED.pdf SCREENSHOT_PREFIX
VALUES.json maps field names to strings or booleans (checkboxes); the optional key "__typed__"
is a list of [field, keys] pairs typed with real key events instead of being set through DOM events.
Date fields become native date inputs in PDF.js, so type their digits (e.g. "07102026"); the
segment order follows the browser locale (day first in the ru locale).
"""
import base64
import itertools
import json
import subprocess
import sys
import shutil
import tempfile
import time
from pathlib import Path

import websocket

PORT = 9333


class Bidi:
    def __init__(self):
        for _ in range(60):
            try:
                self.ws = websocket.create_connection(f'ws://127.0.0.1:{PORT}/session', timeout=60, suppress_origin=True)
                break
            except OSError:
                time.sleep(0.5)
        self.ids = itertools.count(1)

    def call(self, method, **params):
        id_ = next(self.ids)
        self.ws.send(json.dumps({'id': id_, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == id_:
                if msg.get('type') == 'error':
                    raise RuntimeError(msg)
                return msg['result']


def evaluate(b, ctx, expr):
    r = b.call('script.evaluate', expression=expr, target={'context': ctx}, awaitPromise=True,
               resultOwnership='none')
    if r.get('type') == 'exception':
        raise RuntimeError(r['exceptionDetails']['text'])
    v = r['result']
    return v.get('value')


def wait_viewer(b, ctx):
    for _ in range(80):
        try:
            ok = evaluate(b, ctx, "(async () => { const a = window.PDFViewerApplication; if (!a || !a.pdfDocument) return false;"
                                  " return document.querySelectorAll('.annotationLayer input, .annotationLayer textarea').length; })()")
            if ok:
                return ok
        except RuntimeError:
            pass
        time.sleep(0.25)
    raise RuntimeError('viewer not ready')


def main(pdf, values_json, out_pdf, shot_prefix):
    values = json.loads(Path(values_json).read_text())
    profile = tempfile.mkdtemp(prefix='ffprof-')
    Path(profile, 'user.js').write_text('user_pref("pdfjs.disabled", false);\n'
                                        'user_pref("browser.shell.checkDefaultBrowser", false);\n')
    proc = subprocess.Popen(['firefox', '--headless', '--no-remote', '--profile', profile,
                             f'--remote-debugging-port={PORT}', '-remote-allow-system-access'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        b = Bidi()
        b.call('session.new', capabilities={})
        ctx = b.call('browsingContext.create', type='tab')['context']
        b.call('browsingContext.setViewport', context=ctx, viewport={'width': 1000, 'height': 1400})
        b.call('browsingContext.navigate', context=ctx, url=Path(pdf).resolve().as_uri(), wait='complete')
        print('inputs on open:', wait_viewer(b, ctx))
        evaluate(b, ctx, "(async () => { PDFViewerApplication.pdfViewer.currentScaleValue = 'page-width'; })()")
        # Render all pages so that every annotation layer exists.
        evaluate(b, ctx, """(async () => { const v = PDFViewerApplication.pdfViewer;
            for (let i = 1; i <= v.pagesCount; i++) { v.currentPageNumber = i; await new Promise(r => setTimeout(r, 400)); }
            v.currentPageNumber = 1; })()""")
        # Type one Cyrillic value with real key events, set the rest through DOM events.
        typed = values.pop('__typed__', [])
        if typed and isinstance(typed[0], str):
            typed = [typed]
        for name, text in typed:
            evaluate(b, ctx, f"(async () => {{ const e = document.querySelector('[name={json.dumps(name)}]'); e.focus();"
                             " await new Promise(r => setTimeout(r, 300)); })()")
            actions = [a for ch in text for a in ({'type': 'keyDown', 'value': ch}, {'type': 'keyUp', 'value': ch})]
            b.call('input.performActions', context=ctx, actions=[{'type': 'key', 'id': 'kb', 'actions': actions}])
            evaluate(b, ctx, f"(async () => {{ document.querySelector('[name={json.dumps(name)}]').blur();"
                             " await new Promise(r => setTimeout(r, 300)); })()")
        result = evaluate(b, ctx, """(async (values) => {
            const missing = [];
            for (const [name, value] of Object.entries(values)) {
                const e = document.querySelector(`[name="${name}"]`);
                if (!e) { missing.push(name); continue; }
                if (e.type === 'checkbox') { if (e.checked !== value) e.click(); }
                else { e.focus(); e.value = value; e.dispatchEvent(new Event('input', {bubbles: true}));
                       e.dispatchEvent(new Event('change', {bubbles: true})); e.blur(); }
            }
            return missing; })(""" + json.dumps(values) + ")")
        print('missing fields in DOM:', result)
        time.sleep(0.5)
        data = evaluate(b, ctx, """(async () => { const bytes = await PDFViewerApplication.pdfDocument.saveDocument();
            let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
            return btoa(s); })()""")
        Path(out_pdf).write_bytes(base64.b64decode(data))
        print('saved bytes:', len(base64.b64decode(data)))
        # Reopen the saved file and read values back from the viewer.
        old = ctx
        ctx = b.call('browsingContext.create', type='tab')['context']
        b.call('browsingContext.close', context=old, promptUnload=False)
        b.call('browsingContext.navigate', context=ctx, url=Path(out_pdf).resolve().as_uri(), wait='complete')
        wait_viewer(b, ctx)
        evaluate(b, ctx, "(async () => { PDFViewerApplication.pdfViewer.currentScaleValue = 'page-width'; await new Promise(r => setTimeout(r, 800)); })()")
        # Values as the reopened viewer shows them (render every page first).
        fields = evaluate(b, ctx, """(async () => { const v = PDFViewerApplication.pdfViewer;
            for (let i = 1; i <= v.pagesCount; i++) { v.currentPageNumber = i; await new Promise(r => setTimeout(r, 400)); }
            v.currentPageNumber = 1; const out = {};
            for (const e of document.querySelectorAll('.annotationLayer [name]'))
                out[e.name] = e.type === 'checkbox' ? e.checked : e.value;
            return JSON.stringify(out); })()""")
        Path(out_pdf).with_suffix('.fields.json').write_text(fields)
        shot = b.call('browsingContext.captureScreenshot', context=ctx)
        Path(shot_prefix + '-reopen.png').write_bytes(base64.b64decode(shot['data']))
        print('ua:', evaluate(b, ctx, 'navigator.userAgent'), '| pdf.js', evaluate(b, ctx, 'PDFViewerApplication.pdfjsLib?.version || window.pdfjsLib?.version || ""'))
        b.call('session.end')
    finally:
        proc.terminate()
        proc.wait(10)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == '__main__':
    main(*sys.argv[1:])
