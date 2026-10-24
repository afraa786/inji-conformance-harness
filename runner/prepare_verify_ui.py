"""Prepare the real alpha Verify UI configuration and isolated browser CA trust."""
import json
from pathlib import Path
import shutil


def main():
    root = Path('local/verify-ui'); root.mkdir(parents=True, exist_ok=True)
    query = json.loads(Path('local/verify-request.json').read_text())['dcqlQuery']
    (root/'config.json').write_text(json.dumps({'verifiableClaims':[{
        'logo':'/assets/cert.png', 'name':'Conformance SD-JWT (TEST)', 'essential':True,
        'clientIdPrefix':'redirect_uri', 'purpose':'Synthetic conformance credential verification',
        'dcqlQuery':query}]},indent=2)+'\n')
    gateway=Path('configs/nginx.conf').read_text()
    before='''        server_name verify.test localhost;
        location / {'''
    after='''        server_name verify.test localhost;
        location / {
            set $frontend http://verify-ui:8000;
            proxy_pass $frontend;
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-Proto https;
        }
        location /v1/verify {'''
    if gateway.count(before)!=1:
        raise ValueError('Inspect gateway layout before preparing UI routing')
    (root/'nginx-gateway.conf').write_text(gateway.replace(before,after))
    browser=Path('local/browser-build'); browser.mkdir(parents=True,exist_ok=True)
    shutil.copy2('tools/browser/Dockerfile',browser/'Dockerfile')
    shutil.copy2('local/tls/ca.crt',browser/'ca.crt')
    print('Prepared tagged UI DCQL configuration and browser build context; no keys copied')


if __name__=='__main__':
    main()
