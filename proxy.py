"""
http://hostname:port/p/(URL to be proxied, minus protocol)
Largely copied from: http://gear11.com/2013/12/python-proxy-server/
"""
from flask import Flask, request, abort

import json
import re
import requests
import logging

app = Flask(__name__.split('.')[0])
logging.basicConfig(level=logging.INFO)
APPROVED_HOSTS = set(["newapi.brandwatch.com"])
LOG = logging.getLogger("proxy")
MENTIONS_CALL_REGEX = re.compile("newapi.brandwatch.com/projects/([0-9]*)/data/mentions")


@app.route('/p/<path:url>')
def proxy(url):
    r = get_source_rsp(url)
    if (r.status_code != 200):
        abort(r.status_code)
    response_json = r.json()
    project_id = get_project_id_if_mentions_call(url)
    if project_id:
        add_subcategory_names(project_id, response_json)
    return json.dumps(response_json)


def add_subcategory_names(project_id, response_json):
    sub_categories = get_subcategories(project_id)

    for mention in response_json['results']:
        new_subcategories = []
        for sub_category_id in mention['categories']:
            new_subcategories.append(sub_categories[sub_category_id])

        mention['categories'] = new_subcategories

def get_project_id_if_mentions_call(url):
    url_match = MENTIONS_CALL_REGEX.search(url)
    if url_match:
        return url_match.groups(0)
    return None


def get_subcategories(project_id):
    c = requests.get('http://newapi.brandwatch.com/projects/' +
                     project_id[0] +
                     '/categories' + '?' + 'access_token=' +
                     request.args.get('access_token'),
                     allow_redirects=False)
    categories_from_json = c.json()['results']

    subcategories = {}

    for category in categories_from_json:
        for subcategory in category['children']:
            subcategories[subcategory['id']] = subcategory['name']

    return subcategories


def get_source_rsp(url):
        url = 'http://%s' % url
        LOG.info("Fetching %s", url)
        if not is_approved(url):
            LOG.warn("URL is not approved: %s", url)
            abort(403)
        proxy_ref = proxy_ref_info(request)
        headers = {"Referer": "http://%s/%s" %
                   (proxy_ref[0], proxy_ref[1])} if proxy_ref else {}
        return requests.get(url,
                            params=request.args,
                            headers=headers,
                            allow_redirects=False)


def is_approved(url):
    host = split_url(url)[1]
    return host in APPROVED_HOSTS


def split_url(url):
    proto, rest = url.split(':', 1)
    rest = rest[2:].split('/', 1)
    host, uri = (rest[0], rest[1]) if len(rest) == 2 else (rest[0], "")
    return (proto, host, uri)


def proxy_ref_info(request):
    ref = request.headers.get('referer')
    if ref:
        _, _, uri = split_url(ref)
        if uri.find("/") < 0:
            return None
        first, rest = uri.split("/", 1)
        if first in "pd":
            parts = rest.split("/", 1)
            r = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")
            LOG.info("Referred by proxy host, uri: %s, %s", r[0], r[1])
            return r
    return None

if __name__ == '__main__':
    app.run(port=5001)
