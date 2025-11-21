# NetBox Rendered Configuration Retrieval

This document explains how to properly retrieve rendered device configurations from NetBox using the API and pynetbox library.

## Overview

NetBox provides configuration rendering capabilities through config templates. The ZTP tool retrieves these rendered configurations to provision network devices.

## Configuration Rendering in NetBox

### What is Configuration Rendering?

NetBox's configuration rendering feature (introduced in v3.5) allows you to:
1. Create Jinja2 templates for device configurations
2. Use config context data as variables in templates
3. Render device-specific configurations dynamically
4. Access rendered configs via API

### How It Works

```
Config Template (Jinja2) + Config Context Data (Variables) = Rendered Configuration
```

Example:
- **Template**: `hostname {{ device.name }}`
- **Config Context**: `{"device": {"name": "router-01"}}`
- **Rendered Output**: `hostname router-01`

## API Access Methods

### Method 1: Using pynetbox (Recommended)

```python
import pynetbox

# Initialize NetBox client
nb = pynetbox.api('https://netbox.example.com', token='your-token')

# Get device
device = nb.dcim.devices.get(name='device-name')

# Render configuration (requires pynetbox v7.2.0+)
rendered = device.render_config.create()

# Access configuration content
if hasattr(rendered, 'content'):
    config = rendered.content
else:
    config = rendered.get('content')  # If dict is returned
```

**Important Notes:**
- Uses `render_config.create()` (POST method, not GET)
- Requires pynetbox version 7.2.0 or higher
- API token must have **write permissions**
- Token must have **add permissions** on DCIM > Device object type

### Method 2: Direct REST API Call

```python
import requests

url = "https://netbox.example.com"
token = "your-api-token"
device_id = 12345

headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/json"
}

# POST request to render-config endpoint
response = requests.post(
    f"{url}/api/dcim/devices/{device_id}/render-config/",
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    config = data.get('content')
```

**API Endpoint:**
```
POST /api/dcim/devices/{id}/render-config/
```

### Method 3: Using Config Context (Fallback)

If the API token doesn't have render-config permissions, you can check if the rendered config is stored in config_context:

```python
# Get device with config_context
response = requests.get(
    f"{url}/api/dcim/devices/?name={device_name}",
    headers=headers
)

if response.status_code == 200:
    devices = response.json().get('results', [])
    if devices:
        config_context = devices[0].get('config_context', {})

        # Check for rendered config in context
        if 'rendered_config' in config_context:
            config = config_context['rendered_config']
```

## Permission Requirements

### API Token Permissions

To access the render-config endpoint, the API token needs:

1. **Write Enabled**: Token must be set to "Write Enabled"
2. **Object Permissions**: Add permissions on DCIM > Device object type
3. **User Permissions**: Associated user must have rights to view devices

### Troubleshooting 403 Forbidden

If you get a 403 Forbidden response:

```
GET /api/dcim/devices/{id}/render-config/ -> 403 Forbidden
```

**Causes:**
- Using GET instead of POST (incorrect HTTP method)
- API token doesn't have write permissions
- User doesn't have add permissions on Device object type
- Token is read-only

**Solutions:**
1. Change HTTP method from GET to POST
2. Enable "Write" on the API token in NetBox
3. Grant user "Add" permission for DCIM > Device object
4. Use an admin token for testing

## Implementation in ZTP Tool

### Current Implementation (ztp/netbox_client.py)

```python
def get_device_config(self, device_name: str) -> str:
    """Retrieve configuration with multiple fallback options."""

    device = self.get_device(device_name)
    config = None

    # Option 1: Try rendered config from template (POST method)
    try:
        rendered = device.render_config.create()
        if rendered and hasattr(rendered, 'content'):
            config = rendered.content
        elif rendered:
            config = rendered.get('content') if isinstance(rendered, dict) else str(rendered)
    except AttributeError:
        # Fallback to direct API POST if method unavailable
        response = self.nb.http_session.post(
            f"{self.url}/api/dcim/devices/{device.id}/render-config/"
        )
        if response.status_code == 200:
            data = response.json()
            config = data.get('content')

    # Option 2: Config context with 'startup_config' or 'configuration'
    if not config and device.config_context:
        config = device.config_context.get('startup_config') or \
                 device.config_context.get('configuration')

    # Option 3: Custom fields
    if not config and device.custom_fields:
        config = device.custom_fields.get('startup_config') or \
                 device.custom_fields.get('configuration')

    # Option 4: Local context data
    if not config and hasattr(device, 'local_context_data'):
        config = device.local_context_data.get('configuration')

    if not config:
        raise ConfigurationNotFoundError(f"No config for {device_name}")

    return config
```

### Priority Order

1. **Rendered config template** (via render_config.create() POST)
2. Config context with 'startup_config' or 'configuration' keys
3. Custom fields with 'startup_config' or 'configuration' keys
4. Local context data with 'configuration' key

## NetBox Setup Requirements

### For Config Template Rendering

1. **Create Config Template**
   - Go to: Extras > Config Templates
   - Add Jinja2 template content
   - Assign data source if needed

2. **Assign Template to Device**
   - Go to: DCIM > Devices > [Your Device]
   - Click "Render Config" tab
   - Select config template
   - Assign data file (optional)

3. **Configure Config Context**
   - Go to: Extras > Config Contexts
   - Add variables for template rendering
   - Assign to devices/sites/roles as needed

4. **Set API Token Permissions**
   - Go to: Admin > Users > Tokens
   - Enable "Write" permission
   - Ensure user has Device add permissions

## Common Issues and Solutions

### Issue: 'DetailEndpoint' object is not callable

**Error:**
```
'DetailEndpoint' object is not callable
```

**Cause:**
Using `device.render_config()` instead of `device.render_config.create()`

**Solution:**
```python
# Wrong
rendered = device.render_config()

# Correct
rendered = device.render_config.create()
```

### Issue: 403 Forbidden on render-config endpoint

**Error:**
```
GET /api/dcim/devices/11745/render-config/ -> 403 Forbidden
```

**Causes & Solutions:**

1. **Wrong HTTP method**: Change GET to POST
2. **Missing write permission**: Enable write on API token
3. **Missing object permission**: Grant add permission on Device object
4. **Read-only token**: Create new token with write enabled

### Issue: No 'content' field in response

**Error:**
```
Rendered config response has no 'content' field
```

**Cause:**
Template not assigned to device or rendering failed

**Solution:**
- Check device has config template assigned
- Verify config context data is correct
- Test rendering in NetBox UI first
- Check NetBox logs for template errors

## Testing Configuration Retrieval

### Test Script

```python
import pynetbox
import sys

# Configuration
NETBOX_URL = "https://netbox.example.com"
NETBOX_TOKEN = "your-api-token"
DEVICE_NAME = "test-device"

# Initialize
nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

# Get device
print(f"Getting device: {DEVICE_NAME}")
device = nb.dcim.devices.get(name=DEVICE_NAME)
if not device:
    print(f"Device {DEVICE_NAME} not found")
    sys.exit(1)

print(f"Found device: {device.name} (ID: {device.id})")

# Try to render config
try:
    print("Attempting to render configuration...")
    rendered = device.render_config.create()

    if hasattr(rendered, 'content'):
        config = rendered.content
        print(f"Success! Retrieved {len(config)} characters")
        print(f"Preview: {config[:200]}...")
    else:
        print(f"Unexpected response format: {type(rendered)}")

except Exception as e:
    print(f"Error: {e}")
    print(f"Error type: {type(e).__name__}")
```

### Expected Output

**Success:**
```
Getting device: test-device
Found device: test-device (ID: 12345)
Attempting to render configuration...
Success! Retrieved 5432 characters
Preview: no service pad
no platform punt-keepalive disable-kernel-core
no ip domain lookup
...
```

**Permission Error:**
```
Error: The server returned a 403 status code
Error type: RequestError
```

## References

### Official Documentation
- [NetBox Configuration Rendering](https://netboxlabs.com/docs/netbox/features/configuration-rendering/)
- [NetBox API Documentation](https://demo.netbox.dev/api/docs/)

### Related Projects
- [netbox-config-diff plugin](https://github.com/miaow2/netbox-config-diff) - Reference implementation
- [pynetbox GitHub](https://github.com/netbox-community/pynetbox) - Official Python client

### NetBox Community
- [Issue #14634](https://github.com/netbox-community/netbox/issues/14634) - API access to render-config permissions
- [Discussion #13800](https://github.com/netbox-community/netbox/discussions/13800) - Fetch rendered config via pynetbox

## Version Compatibility

| NetBox Version | Config Rendering | render_config API | pynetbox Version |
|----------------|------------------|-------------------|------------------|
| < 3.5          | ❌ Not available | ❌                | Any              |
| 3.5 - 3.7      | ✅ Available     | ✅                | 7.2.0+           |
| 4.0+           | ✅ Available     | ✅                | 7.2.0+           |

## Summary

**Key Takeaways:**
1. Use POST method, not GET, for render-config endpoint
2. Use `device.render_config.create()` in pynetbox
3. API token needs write permissions
4. Requires pynetbox v7.2.0 or higher
5. Always have fallback methods (config_context, custom_fields, local_context_data)

**Best Practice:**
Implement multiple retrieval methods in priority order, with rendered config as the primary source and manual config storage as fallback options.
