# manage_account.py
import json
import urllib3
import certifi
import http.client
import json
# ___main loop___

if __name__ == '__main__':
    mailsac_key = r'k_D3e8P42iBMr8E870ac75i9AbQ4BV8WB8'
    http_urllib3 = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where()
    )

    # curl --header "Mailsac-Key: k_eoj1mn7x5y61w0egs25j6xrv" https://mailsac.com/api/me

    headers = {
        'Mailsac-Key': mailsac_key,
        'content-type': "application/json",
    }
    response = http_urllib3.request(
        "GET", "https://mailsac.com/api/addresses", headers=headers)

    print(response.data)

    conn = http.client.HTTPSConnection("mailsac.com")

    conn.request("GET", "/api/addresses", headers=headers)

    res = conn.getresponse()
    data = res.read()

    print(data.decode("utf-8"))

    test_emails = ['sndev001@mailsac.com',
                   'sndev002@mailsac.com', 'sndev003@mailsac.com']
    new_addresses = {}
    for new_address in test_emails:
        payload = "/api/addresses/{}".format(new_address)
        conn.request("GET", payload, headers=headers)

        res = conn.getresponse()
        data = res.read()

        new_addresses[new_address] = {
            'encrypted_inbox': json.loads(data.decode("utf-8"))['encryptedInbox']
        }

        new_addresses[new_address] = {
            'encrypted_inbox': json.loads(data.decode("utf-8"))['encryptedInbox']
        }

    print(new_addresses)

    # create address
    url = "/api/addresses/{}".format(test_emails[0])

    payload = {
        "info": test_emails[0].split('@')[0],
        "forward": "",
        "enablews": False,
        "webhook": "",
        "webhookSlack": "",
        "webhookSlackToFrom": True
    }
    payload = "{\"info\":\"string\",\"forward\":\"\",\"enablews\":false,\"webhook\":\"\",\"webhookSlack\":\"\",\"webhookSlackToFrom\":true}"

    conn.request("POST", url, payload, headers=headers)

    res = conn.getresponse()
    data = res.read()
