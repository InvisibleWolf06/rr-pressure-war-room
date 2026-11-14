import json, sys
t = open('work/dash_template.html').read()
d = json.load(open('out/dashboard_data.json')); w = json.load(open('out/worms.json'))
enc = lambda o: json.dumps(o, separators=(',', ':')).replace('</', '<\\/')
import base64
img = 'data:image/jpeg;base64,' + base64.b64encode(open('work/img/stadium.jpg','rb').read()).decode()
html = t.replace('__STADIUM__', img).replace('__DATA__', enc(d)).replace('__WORMS__', enc(w))
open('rr_war_room.html', 'w').write(html)
# local test copy with bundled plotly (CDN not reachable from this sandbox)
import plotly, os
js = open(os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')).read()
open('/tmp/rr_test.html', 'w').write(html.replace('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>', '<script>' + js + '</script>'))
print(len(html) / 1e6, 'MB')
