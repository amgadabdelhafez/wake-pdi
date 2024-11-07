#!/usr/bin/env python
# encoding: utf-8
import json
from flask import Flask
app = Flask(__name__)


@app.route('/test')
def index():
    return json.dumps({'name': 'alice',
                       'email': 'alice@wonder-land.com'})


app.run(host='0.0.0.0', port=80)
