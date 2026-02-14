# Hikvision ISAPI Image Control

A Home Assistant custom integration that exposes **every image and exposure setting** on Hikvision cameras as native HA entities — switches, sliders, and dropdowns you can automate.

No existing integration touches these settings. The core `hikvision` integration is read-only (streams + binary sensors). `hikvision_next` adds event switches and diagnostics but still no image control. This integration fills that gap.

## Why?

Most Hikvision cameras — especially ColorVu models — have no true auto exposure. Shutter speed and gain are fixed manual values, not adaptive limits. A single shutter speed that works at noon produces a black image at midnight.

This integration lets you automate exposure profiles from HA so you can switch settings based on time of day, sun elevation, or any other trigger — something the cameras simply can't do on their own.

## What It Exposes

Entities are **auto-discovered** from each camera's capabilities XML. Different camera models get different entities based on what they actually support. Common entities include:

| Entity | Type | Example |
|--------|------|---------|
| WDR | Select | Off, On, Auto |
| WDR Level | Slider | 0–100 |
| BLC Mode | Select | Off, Up, Down, Left, Right, Center, Auto |
| HLC | Switch | On/Off |
| HLC Level | Slider | 0–100 |
| Day/Night Mode | Select | Day, Night, Auto, Schedule |
| Shutter Speed | Select | 1/3 – 1/100000 (varies by model) |
| Gain | Slider | 0–100 |
| Brightness | Slider | 0–100 |
| Contrast | Slider | 0–100 |
| Saturation | Slider | 0–100 |
| Sharpness | Slider | 0–100 |
| Noise Reduction | Select | Off, Normal, Advanced |
| Defog | Select | Off, Auto, On |
| White Balance | Select | Auto 1, Auto 2, Manual, Locked, etc. |
| Supplement Light | Select | On, Off (white light or IR, per model) |
| Light Brightness | Slider | 0–100 |
| Image Flip | Switch | On/Off |
| Power Line Frequency | Select | 50 Hz, 60 Hz |

Additional entities appear on specific models: P-Iris controls (motorized zoom cameras), focus mode, scene mode, lens distortion correction (panoramic cameras), IR high/low brightness, and more.

## Conflict Resolution

Several camera features are mutually exclusive — the camera will reject changes if a conflicting feature is active. This integration handles it automatically:

- Enabling **WDR** while **HLC** or **BLC** is active → auto-disables the blocker first, then enables WDR
- Enabling **BLC** while **WDR** is active → auto-disables WDR first
- Enabling **HLC** while **WDR** is active → auto-disables WDR first
- **HLC** and **BLC** can coexist — no conflict

Just set what you want. If something is in the way, the integration disables it and retries — no manual juggling required.

## Supplement Light vs. Day/Night Mode

This is the most confusing part of Hikvision's system, so read this before automating your lights. There are three entities that work together:

1. **Supplement Light** (select) — Enables the light feature: "White Light" (on) or "Off". This does **not** physically turn the light on by itself.
2. **Day/Night Mode** (select) — Controls *when* the light actually activates.
3. **Light Brightness Mode** (select) — "Manual" uses your brightness slider value; "Auto" lets the camera decide.

The light only physically turns on when **both** Supplement Light is set to "White Light" **and** Day/Night Mode allows it:

| Day/Night Mode | Light behavior |
|---|---|
| **Day** | Light stays **off** regardless of other settings |
| **Night** | Light turns **on** (if Supplement Light = White Light and brightness > 0) |
| **Auto** | Camera uses its ambient light sensor to decide |

**Recommended setup for automations:**

Leave **Supplement Light** set to "White Light" and **Light Brightness Mode** set to "Manual" all the time. Then automate with just two controls:

- **Brightness slider** — set the intensity you want (0–100)
- **Day/Night Mode** — switch between "Night" and "Auto" (or "Day") to control when the light activates

This is simpler than toggling multiple entities, and it matches how the camera actually works.

**Important caveats:**

- **Day/Night Mode affects image quality**, not just the light. On most cameras it controls the IR cut filter and internal image processing. The "Night" setting genuinely looks better at night, so switching between "Night" at sunset and "Auto" at sunrise is a good approach.
- On **ColorVu cameras** (no IR), "Day/Night Mode" is misleading — there's no actual IR cut filter or black-and-white mode. It primarily controls the white supplement light trigger.
- **"Smart Supplement Light"** (the switch entity, if present) is an overexposure suppression feature — it auto-dims the light to reduce glare on nearby objects. It does **not** turn the light on or off.

## Tested Cameras

| Model | Type | Notes |
|-------|------|-------|
| DS-2CD2187G2-LSU | ColorVu 4K turret | Fixed iris, white supplement light |
| DS-2CD2387G2-LU | ColorVu 3MP turret | Fixed iris, white supplement light |
| DS-2CD2T87G2P-LSU/SL | Panoramic ColorVu bullet | Wide-angle, lens distortion correction |
| PCI-D18Z2HS | Motorized zoom turret | IR, P-Iris, focus control |

Should work with any Hikvision camera that supports the `/ISAPI/Image/channels/1` endpoint (most modern models). If your camera works or doesn't, please open an issue.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) → **Custom repositories**
3. Add `https://github.com/JoshADC/hikvision_isapi` with category **Integration**
4. Click **Install**
5. Restart Home Assistant

### Manual

Copy the `custom_components/hikvision_isapi` folder to your Home Assistant `config/custom_components/` directory and restart.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Hikvision ISAPI Image Control**
3. Enter your camera's IP address, username, and password (admin credentials required)
4. Entities are auto-created based on your camera's capabilities

## Example Automations

### Day/Night Exposure Profiles

Switch shutter speed and gain at sunset/sunrise for cameras without auto exposure:

```yaml
automation:
  - alias: "Camera Night Exposure"
    trigger:
      - platform: numeric_state
        entity_id: sun.sun
        attribute: elevation
        below: -2
    action:
      - service: select.select_option
        target:
          entity_id: select.ds_2cd2187g2_lsu_shutter_speed
        data:
          option: "1/30"
      - service: number.set_value
        target:
          entity_id: number.ds_2cd2187g2_lsu_gain
        data:
          value: 60

  - alias: "Camera Day Exposure"
    trigger:
      - platform: numeric_state
        entity_id: sun.sun
        attribute: elevation
        above: 2
    action:
      - service: select.select_option
        target:
          entity_id: select.ds_2cd2187g2_lsu_shutter_speed
        data:
          option: "1/150"
      - service: number.set_value
        target:
          entity_id: number.ds_2cd2187g2_lsu_gain
        data:
          value: 20
```

### Day/Night Mode Switching

Switch Day/Night Mode at sunrise/sunset. "Night" mode looks better at night and reliably activates the supplement light; "Auto" lets the camera handle daytime transitions:

```yaml
automation:
  - alias: "Camera Sunset Mode"
    trigger:
      - platform: numeric_state
        entity_id: sun.sun
        attribute: elevation
        below: -2
    action:
      - service: select.select_option
        target:
          entity_id: select.ds_2cd2387g2_lu_day_night_mode
        data:
          option: "Night"

  - alias: "Camera Sunrise Mode"
    trigger:
      - platform: numeric_state
        entity_id: sun.sun
        attribute: elevation
        above: 2
    action:
      - service: select.select_option
        target:
          entity_id: select.ds_2cd2387g2_lu_day_night_mode
        data:
          option: "Auto"
```

### Motion Alert → Supplement Light Blast

Crank the light to full brightness on a motion or person detection event, then drop it back down. Works with any NVR or motion sensor — Frigate, Scrypted, SecuritySpy, or a simple binary sensor. Assumes Supplement Light is set to "White Light", Brightness Mode is "Manual", and Day/Night Mode is "Night" or "Auto" in dark conditions (see [Supplement Light vs. Day/Night Mode](#supplement-light-vs-daynight-mode)):

```yaml
automation:
  - alias: "Blast Light on Person Detection"
    trigger:
      # Use whatever trigger your NVR provides — MQTT, binary sensor, etc.
      - platform: state
        entity_id: binary_sensor.your_camera_person_detected
        to: "on"
    action:
      - service: number.set_value
        target:
          entity_id: number.ds_2cd2387g2_lu_light_brightness
        data:
          value: 100
      - delay: "00:00:30"
      - service: number.set_value
        target:
          entity_id: number.ds_2cd2387g2_lu_light_brightness
        data:
          value: 30
```

## Technical Details

- **Protocol:** ISAPI over HTTP with digest authentication
- **Polling:** Current values polled every 30 seconds (configurable in future release)
- **Write method:** Read-modify-write with raw XML string manipulation (ElementTree re-serialization mangles Hikvision's repeated xmlns declarations, causing the camera to reject PUTs)
- **Conflict resolution:** Two-step sequential PUTs — camera validates against current state, not the PUT body

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Hangzhou Hikvision Digital Technology Co., Ltd. "Hikvision" and "ISAPI" are trademarks of their respective owners. Use at your own risk.
