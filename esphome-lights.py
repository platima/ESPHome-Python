#!/home/luckfox/venv/bin/python
"""
esphome-lights.py — Control ESPHome smart lights via native API

Usage:
  esphome-lights.py --list                    # List all lights
  esphome-lights.py --status                  # Show on/off state of all lights
  esphome-lights.py --set <light-id> --on     # Turn on
  esphome-lights.py --set <light-id> --off    # Turn off
  esphome-lights.py --set <light-id> --brightness 75  # Set brightness (0-255)
  esphome-lights.py --set <light-id> --rgb 255,0,0  # Set RGB (r,g,b)
  
Device config via environment variables:
  Example: ESPHOME_LIGHTS_LIVING_ROOM="10.42.40.55:6053|encryption_key"
  
  Device format: ESPHOME_LIGHTS_<LOCATION>=<host>:<port>|<encryption_key>
  Location will be lowercased in commands.
  Port is usually 6053 (native ESPHome API).
  
  Example setup:
    export ESPHOME_LIGHTS_LIVING_ROOM="10.42.40.55:6053|J+YkHH7XC+4dQwWvPoF5kaz7tP4NY4HJNTL0QyZM1Rg="
    export ESPHOME_LIGHTS_BEDROOM="10.42.40.56:6053|another_key_here"
    
Flags:
  --bg, --background   Fire and forget (return immediately, don't wait for completion)
  --debug              Wait for completion and show detailed results (overrides --bg)
"""

import argparse
import os
import sys
import base64

# Load .env from workspace if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

def load_devices():
    """Load ESPHome devices from environment variables."""
    devices = {}
    for key, value in os.environ.items():
        if key.startswith('ESPHOME_LIGHTS_'):
            location = key[15:].lower()  # Strip prefix, lowercase
            try:
                host_port, api_key = value.split('|')
                host, port = host_port.rsplit(':', 1)
                devices[location] = {
                    'host': host,
                    'port': int(port),
                    'encryption_key': api_key
                }
            except (ValueError, IndexError):
                print(f"Warning: Invalid format for {key}, expected 'host:port|encryption_key'", file=sys.stderr)
    return devices

def connect_and_control(device, action, value=None):
    """Connect to ESPHome device via native API and control light."""
    try:
        import asyncio
        from aioesphomeapi import APIClient, APIConnectionError
    except ImportError:
        print("Error: aioesphomeapi library not found", file=sys.stderr)
        print("Install with: pip install aioesphomeapi", file=sys.stderr)
        return False
    
    async def run():
        try:
            client = APIClient(
                device['host'],
                device['port'],
                noise_psk=device['encryption_key'],
                password=""
            )
            
            await client.connect(login=True)
            
            # Get all entities and find the light or switch
            entities_list, services_list = await client.list_entities_services()
            
            control_key = None
            control_type = None
            
            # Prefer LightInfo for brightness/RGB, fall back to Switch for on/off
            for entity in entities_list:
                if entity.__class__.__name__ == 'LightInfo' and entity.object_id != 'status_led':
                    control_key = entity.key
                    control_type = 'light'
                    break
            
            if control_key is None:
                # Fall back to Switch entity (for smart plugs, etc)
                for entity in entities_list:
                    if entity.__class__.__name__ == 'SwitchInfo':
                        control_key = entity.key
                        control_type = 'switch'
                        break
            
            if control_key is None:
                print(f"Error: No light or switch entity found on device {device['host']}", file=sys.stderr)
                await client.disconnect()
                return False
            
            # Execute the requested action
            if action == 'on':
                if control_type == 'switch':
                    client.switch_command(control_key, state=True)
                else:
                    client.light_command(control_key, state=True)
                print(f"Turned ON")
                success = True
            
            elif action == 'off':
                if control_type == 'switch':
                    client.switch_command(control_key, state=False)
                else:
                    client.light_command(control_key, state=False)
                print(f"Turned OFF")
                success = True
            
            elif action == 'brightness':
                if control_type == 'switch':
                    print("Error: brightness not supported for switch entities", file=sys.stderr)
                    success = False
                elif value is None:
                    print("Error: brightness requires a value (0-255)", file=sys.stderr)
                    success = False
                else:
                    try:
                        brightness = int(value) / 255.0  # Convert to 0.0-1.0
                    except ValueError:
                        print(f"Error: brightness must be 0-255, got {value}", file=sys.stderr)
                        success = False
                    else:
                        client.light_command(control_key, brightness=brightness)
                        print(f"Brightness set to {value}")
                        success = True
            
            elif action == 'rgb':
                if control_type == 'switch':
                    print("Error: RGB not supported for switch entities", file=sys.stderr)
                    success = False
                elif value is None:
                    print("Error: rgb requires a value (r,g,b)", file=sys.stderr)
                    success = False
                else:
                    try:
                        r, g, b = map(int, value.split(','))
                        if not all(0 <= c <= 255 for c in [r, g, b]):
                            raise ValueError()
                    except ValueError:
                        print(f"Error: rgb must be r,g,b (0-255 each), got {value}", file=sys.stderr)
                        success = False
                    else:
                        client.light_command(
                            control_key,
                            rgb=(r / 255.0, g / 255.0, b / 255.0)
                        )
                        print(f"RGB set to ({r},{g},{b})")
                        success = True
            
            else:
                print(f"Error: unknown action '{action}'", file=sys.stderr)
                success = False
            
            await client.disconnect()
            return success
        
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return False
    
    # Run the async function
    try:
        result = asyncio.run(run())
        return result
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

def get_status(devices):
    """Query and print on/off state of all configured devices."""
    if not devices:
        print("No ESPHome lights configured (set ESPHOME_LIGHTS_* env vars)")
        return False

    try:
        import asyncio
        from aioesphomeapi import APIClient
    except ImportError:
        print("Error: aioesphomeapi library not found", file=sys.stderr)
        return False

    async def check_one(name, cfg):
        try:
            client = APIClient(cfg['host'], cfg['port'], noise_psk=cfg['encryption_key'], password="")
            await asyncio.wait_for(client.connect(login=True), timeout=5)
            entities_list, _ = await client.list_entities_services()

            states = {}
            done = asyncio.Event()

            # Collect relevant entity keys
            switch_keys = {e.key for e in entities_list if e.__class__.__name__ == 'SwitchInfo'}
            light_keys  = {e.key for e in entities_list
                           if e.__class__.__name__ == 'LightInfo'
                           and getattr(e, 'object_id', '') != 'status_led'}

            def on_state(state):
                cls = state.__class__.__name__
                if cls == 'SwitchState' and state.key in switch_keys:
                    states['switch'] = state.state
                    done.set()
                elif cls == 'LightState' and state.key in light_keys:
                    states['light'] = state.state
                    done.set()

            client.subscribe_states(on_state)
            try:
                await asyncio.wait_for(done.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
            await client.disconnect()

            if 'switch' in states:
                return name, 'ON' if states['switch'] else 'OFF'
            elif 'light' in states:
                return name, 'ON' if states['light'] else 'OFF'
            else:
                return name, 'unknown'
        except Exception as e:
            return name, f'error ({e})'

    async def run_all():
        tasks = [check_one(n, c) for n, c in sorted(devices.items())]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_all())
    for name, state in results:
        print(f"  {name:20} {state}")
    return True

def list_lights(devices):
    """List all configured lights."""
    if not devices:
        print("No ESPHome lights configured (set ESPHOME_LIGHTS_* env vars)")
        return False
    
    print("Configured ESPHome lights:")
    for location, config in sorted(devices.items()):
        print(f"  {location:20} -> {config['host']}:{config['port']}")
    
    return True

if __name__ == '__main__':
    devices = load_devices()
    
    parser = argparse.ArgumentParser(description='Control ESPHome smart lights via native API')
    parser.add_argument('--list', action='store_true', help='List all configured lights')
    parser.add_argument('--status', action='store_true', help='Show on/off state of all lights')
    parser.add_argument('--set', help='Light ID to control')
    parser.add_argument('--on', action='store_true', help='Turn on')
    parser.add_argument('--off', action='store_true', help='Turn off')
    parser.add_argument('--brightness', type=str, help='Set brightness (0-255)')
    parser.add_argument('--rgb', type=str, help='Set RGB color (r,g,b)')
    parser.add_argument('--bg', '--background', action='store_true', help='Fire and forget (return immediately)')
    parser.add_argument('--debug', action='store_true', help='Wait for completion (overrides --bg)')
    
    args = parser.parse_args()
    
    if args.list:
        success = list_lights(devices)
    elif args.status:
        success = get_status(devices)
    elif args.set:
        location = args.set.lower()
        if location not in devices:
            print(f"Error: Light '{location}' not found. Available: {', '.join(devices.keys())}", file=sys.stderr)
            success = False
        else:
            # If background mode and not debug, use subprocess to detach
            if args.bg and not args.debug:
                import subprocess
                # Re-run this script in background without --bg flag
                cmd = [sys.executable, __file__]
                for var in sys.argv[1:]:
                    if var not in ('--bg', '--background'):
                        cmd.append(var)
                
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print(f"Command sent")
                success = True
            else:
                # Synchronous mode
                if args.on:
                    success = connect_and_control(devices[location], 'on')
                elif args.off:
                    success = connect_and_control(devices[location], 'off')
                elif args.brightness:
                    success = connect_and_control(devices[location], 'brightness', args.brightness)
                elif args.rgb:
                    success = connect_and_control(devices[location], 'rgb', args.rgb)
                else:
                    print("Error: --set requires --on, --off, --brightness, or --rgb", file=sys.stderr)
                    success = False
    else:
        parser.print_help()
        success = False
    
    sys.exit(0 if success else 1)
