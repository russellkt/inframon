# Zabbix Webhook Setup -- Push Alerts to OpenFang

## Overview

Configure Zabbix 7.0 to push trigger alerts to the inframon agent via OpenFang's webhook channel adapter. This replaces the external poller approach.

## Prerequisites

- Zabbix 7.0 server at 10.10.1.142
- OpenFang container running on bmic-infra network (10.10.100.2:8080)
- WEBHOOK_SECRET configured in both `.env` and Zabbix

## Step 1: Create Webhook Media Type

In Zabbix UI: **Administration > Media Types > Create**

| Field | Value |
|-------|-------|
| Name | OpenFang Inframon |
| Type | Webhook |

Add the following parameters:

| Parameter | Value |
|-----------|-------|
| HOST | `{HOST.HOST}` |
| SEVERITY | `{TRIGGER.SEVERITY}` |
| EVENT_ID | `{EVENT.ID}` |
| TRIGGER_NAME | `{TRIGGER.NAME}` |
| LAST_VALUE | `{ITEM.LASTVALUE}` |
| ENDPOINT | `http://10.10.100.2:8080/` |
| SECRET | *(your webhook secret value)* |

In the **Script** field, paste the following JavaScript:

```javascript
var Inframon = {
    params: {},

    setParams: function (params) {
        ['HOST', 'SEVERITY', 'EVENT_ID', 'TRIGGER_NAME', 'LAST_VALUE', 'ENDPOINT', 'SECRET'].forEach(function (field) {
            if (typeof params[field] === 'undefined' || params[field].trim() === '') {
                throw 'Missing required parameter: ' + field;
            }
            Inframon.params[field] = params[field];
        });
    },

    createSignature: function (body) {
        var mac = new HMAC('sha256', Inframon.params.SECRET);
        mac.update(body);
        return mac.digest('hex');
    },

    send: function () {
        var payload = JSON.stringify({
            host: Inframon.params.HOST,
            severity: Inframon.params.SEVERITY,
            event_id: Inframon.params.EVENT_ID,
            trigger_name: Inframon.params.TRIGGER_NAME,
            last_value: Inframon.params.LAST_VALUE
        });

        var signature = Inframon.createSignature(payload);

        var request = new HttpRequest();
        request.addHeader('Content-Type: application/json');
        request.addHeader('X-Signature-256: sha256=' + signature);

        var response = request.post(Inframon.params.ENDPOINT, payload);

        if (request.getStatus() < 200 || request.getStatus() >= 300) {
            throw 'HTTP request failed with status ' + request.getStatus() + ': ' + response;
        }

        return 'OK';
    }
};

try {
    var params = JSON.parse(value);
    Inframon.setParams(params);
    return Inframon.send();
} catch (error) {
    Zabbix.log(4, '[OpenFang Inframon Webhook] Error: ' + error);
    throw 'OpenFang webhook failed: ' + error;
}
```

## Step 2: Create Bot User

Navigate to **Administration > Users > Create** and configure:

1. **User tab**
   - Username: `inframon-bot`
   - Groups: add to a group with **No access to the frontend** (e.g., "No access to the frontend" built-in group)
   - Password: set any value (it will not be used)

2. **Media tab**
   - Click **Add**
   - Type: OpenFang Inframon
   - Send to: `inframon`
   - Enable for all severity levels: Not classified, Information, Warning, Average, High, Disaster

3. **Permissions tab**
   - Role: Super admin role (or a custom role with read access to the hosts you want alerts for)

## Step 3: Create Action

Navigate to **Alerts > Actions > Trigger Actions > Create**:

1. **Action tab**
   - Name: `Push to Inframon`

2. **Conditions tab**
   - Add condition: Trigger severity >= Warning

3. **Operations tab**
   - Click **Add** under Operations
   - Send to users: `inframon-bot`
   - Send only to: OpenFang Inframon

Optionally add a recovery operation with the same settings so OpenFang also receives resolved alerts.

## Step 4: Test

Test the webhook endpoint directly with curl:

```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"message":"test alert from setup verification"}'
```

To test with HMAC signing (matching what Zabbix will send):

```bash
SECRET="your-webhook-secret"
PAYLOAD='{"host":"test-host","severity":"3","event_id":"0","trigger_name":"Test trigger","last_value":"1"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -X POST http://10.10.100.2:8080/ \
  -H "Content-Type: application/json" \
  -H "X-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

In Zabbix, you can also test from **Administration > Media Types**, click the row for OpenFang Inframon, and use the **Test** button.

## Troubleshooting

- **Check OpenFang logs:**
  ```bash
  docker compose -f docker-compose.openfang.yml logs -f
  ```

- **Verify network connectivity:** The OpenFang container must be reachable from the Zabbix server and vice versa on the bmic-infra bridge network. From the Zabbix host:
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://10.10.100.2:8080/
  ```

- **Check Zabbix audit log:** Navigate to **Reports > Audit log** and filter by action "Execute" to see webhook delivery attempts and failures.

- **Webhook returns non-2xx:** Inspect the response body in the Zabbix audit log. Common causes:
  - Wrong ENDPOINT (check IP/port)
  - SECRET mismatch between `.env` and Zabbix parameter
  - OpenFang container not running or not listening on the expected port
