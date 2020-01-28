import asyncore
import logging
import hashlib
import os
import time
import json
import glob
from datetime import datetime
from smtp import InboxServer
from httpd import HttpServer, HTTPRequest

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
log = logging.getLogger(__name__)


def get_main():
    return """<html><head><title>Title goes here.</title></head>
    <body><form action='/d'>Recipient:<input name=email type=text/><input type='submit'/></form>
    </body></html>"""


def get_email(qs):
    eml = qs.get('e', '')
    if not eml:
        return None
    eml = eml.pop()
    msg = qs.get('m', '')
    if not msg:
        return None
    msg = msg.pop()

    h = hashlib.md5(eml.encode('utf-8')).hexdigest()

    item = open(os.path.join(os.path.dirname(__file__), 'data', h, 'new', msg+'.eml'), 'r').read()
    return '<a href="/d?email=' + eml + '">Back</a><pre>' + item + '</pre>'


def get_box(qs):
    eml = qs.get('email', '')
    if not eml:
        return None

    eml = eml.pop()
    h = hashlib.md5(eml.encode('utf-8')).hexdigest()
    lst = []
    for f in glob.glob(os.path.join(os.path.dirname(__file__), 'data', h, 'new', '*.hdr')):
        j = json.loads(open(f, 'r').read())
        j['p'] = os.path.splitext(os.path.basename(f))[0]
        j['a'] = '/q?e=%s&m=%s' % (eml, j['p'])
        j['t'] = datetime.fromtimestamp(int(float(j['p'])))
        lst.append(j)
    lst = sorted(lst, key=lambda rec: rec.get('p'))
    trs = []
    for r in lst:
        trs.append("<td><a href='%(a)s'>%(subject)s</a></td><td>%(from)s</td><td><a href='%(a)s'>%(t)s</a></td><td>%(to)s</td>" % r)
    return """ <a href="/">Back</a>
    <table border='1'>
    <tr><th>Subject</th><th>From</th><th>Time</th><th>To</th></tr>
    <tr>%s</tr>
    </table>
    """ % '</tr><tr>'.join(trs)


class Inboxer(HTTPRequest):
    def do_GET(s):
        if s.path == "/":
            body = get_main()
        elif s.path == "/d":
            body = get_box(s.query_string)
        elif s.path == "/q":
            body = get_email(s.query_string)
        else:
            body = None

        if body is None:
            s.send_error(404, "Not found")
            return

        body = body.encode('utf-8')

        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.send_header("Content-length", str(len(body)))
        s.end_headers()

        s.wfile.write(body)
        pass

    @staticmethod
    def handle_smtp(to, sender, subject, body):
        for t in to:
            h = hashlib.md5(t.encode('utf-8')).hexdigest()
            dr = os.path.join(os.path.dirname(__file__), 'data', h, 'new')
            os.path.join(os.path.dirname(__file__), 'data', h, 'ext')
            os.makedirs(dr, exist_ok=True)
            fl = "%s" % time.time()
            with open(os.path.join(dr, fl + ".eml"), 'w+') as f:
                f.write(body.decode('utf-8'))
            with open(os.path.join(dr, fl + ".hdr"), 'w+') as f:
                f.write(json.dumps({
                    'to': t,
                    'from': sender,
                    'subject': subject
                }))
        log.info('{}->{} [{}]'.format(to, sender, subject))

    @staticmethod
    def serve(smtp_port=2525, http_port=8080, address=None):

        log.info('Starting SMTP server at {0}:{1}'.format(address, smtp_port))
        InboxServer(Inboxer.handle_smtp, (address, smtp_port), None)
        log.info('Starting HTTP server at {0}:{1}'.format(address, http_port))
        HttpServer((address, http_port, ), Inboxer)

        try:
            asyncore.loop()
        except KeyboardInterrupt:
            log.info('Cleaning up')


if __name__ == '__main__':
    Inboxer.serve(address='0.0.0.0', smtp_port=2525, http_port=8080)
