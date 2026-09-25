# Hikvision ISAPI Image Control

A Home Assistant custom integration that exposes **every image and exposure setting** on Hikvision cameras as native HA entities-switches, sliders, and dropdowns you can automate.


***Heads up that this was almost entirely vibe-coded by a grumpy truck driver who can barely format a shell command working with a very patient Claude Code, who also wrote most of this README. ***

First, for any of this to work, you can't use this scene-switching stuff in the camera's UI. The reason for making this integration was getting away from the camera's internal scheduling, but heads up that you can't use both at the same time.

<img width="1185" height="383" alt="Screenshot 2026-02-15 at 14 06 15" src="https://github.com/user-attachments/assets/11d8b832-5887-4f9d-b8a3-744046949cb7" />


## Why?

Most Hikvision cameras, or at least the one's I've tried, have no true auto exposure that I can find. Shutter speed and gain are fixed manual values, not adaptive limits. A single shutter speed that works at midnight is blown out and unsable at noon.

This integration lets you automate exposure profiles, brigthness, contrast, etc. from HA so you can switch settings based on time of day, sun elevation, or the timer on your smart dishwasher-it's Home Assistant, you know the drill.


## What It Exposes

Entities are **auto-discovered** from each camera's capabilities XML. Different camera models get different entities based on what they actually support — fixed dome cameras and PTZ cameras in particular can expose quite different sets. Common entities include:

**Exposure & Iris**

| Entity | Type | Example |
|--------|------|---------|
| Iris Mode | Select | Auto, Manual, P-Iris, Iris Priority, Shutter Priority |
| P-Iris Mode | Select | Auto, Manual |
| P-Iris Level | Slider | 0–100 |
| Auto Iris Level | Slider | 0–100 |
| Iris Level | Select | *(varies by model — PTZ)* |
| Max/Min Iris Level | Slider | 0–100 (PTZ) |
| Shutter Speed | Select | 1/3 – 1/100000 (varies by model) |
| Max/Min Shutter Speed | Select | *(PTZ)* |
| Gain | Slider | 0–100 |
| Gain Limit | Slider | 0–100 (PTZ) |

**Backlight, Highlight & Wide Dynamic Range**

| Entity | Type | Example |
|--------|------|---------|
| WDR | Select | Off, On, Auto |
| WDR Level | Slider | 0–100 |
| BLC | Switch or Select | On/Off, or Off/Up/Down/Left/Right/Center/Region/Auto (varies by model) |
| BLC Mode | Select | Off, Up, Down, Left, Right, Center, Region, Auto |
| HLC | Switch | On/Off |
| HLC Level | Slider | 0–100 |

**Day/Night & IR**

| Entity | Type | Example |
|--------|------|---------|
| Day/Night Mode | Select | Day, Night, Auto, Schedule, Event Trigger |
| Day/Night Schedule Type | Select | Day, Night |
| Night-to-Day Sensitivity | Slider or Select | 0–7 (varies by model) |
| Night-to-Day Delay | Slider | 0–100 |
| IR Light Mode | Select | Auto *(more options vary by model)* |
| IR Light Brightness / Limit | Slider | 0–100 |

**Supplement Light**

| Entity | Type | Example |
|--------|------|---------|
| Supplement Light | Select | Off, White Light, IR (per model) |
| Supplement Light Mode | Select | Auto, Event Intelligence |
| Smart Supplement Light | Switch | On/Off |
| Smart Supplement Light Mode | Select | Auto, Manual |
| Smart Supplement Light Distance | Slider | 0–100 |
| Smart Supplement Light High/Low-Light Distance | Slider | 0–100 (PTZ) |
| Light Brightness / White Light Brightness / IR Brightness (and limits) | Slider | 0–100 |
| Event Intelligence Brightness Mode | Select | Auto, Manual |
| Event Intelligence White/IR Light Brightness | Slider | 0–100 (PTZ) |

**Image Quality**

| Entity | Type | Example |
|--------|------|---------|
| Brightness | Slider | 0–100 |
| Contrast | Slider | 0–100 |
| Saturation | Slider | 0–100 |
| Sharpness | Slider | 0–100 |
| Color Space | Select | Auto, Color, Black & White |
| White Balance | Select | Auto 1, Auto 2, Manual, Locked, Sodium Lamp, Auto Trace, etc. |
| White Balance Red/Blue | Slider | 0–100 |
| Noise Reduction | Select | Off, Normal, Advanced |
| Spatial / Temporal NR Level | Slider | 0–100 |
| Smart Noise Reduction Level | Slider | 0–100 (PTZ) |
| Defog | Select | Off, Auto, Manual, On |
| Defog Level | Slider | 0–100 |
| Lens Distortion Correction | Switch | On/Off |
| Correction Level | Slider | 0–100 |
| Image Flip | Switch | On/Off |
| Flip Direction | Select | Center, Up-Down, Left-Right |

**Focus & PTZ-Specific**

| Entity | Type | Example |
|--------|------|---------|
| Focus Mode | Select | Auto, Manual, Semi-automatic |
| Focus Distance Mode | Select | Compatible *(more options vary by model)* |
| Focus Limit Mode | Select | *(varies by model)* |
| Zoom Limit Ratio | Select | *(varies by model)* |
| Image Stabilization (EIS) | Switch | On/Off |
| Digital Slow Shutter (DSS) | Switch | On/Off |
| Digital Slow Shutter Level | Select | ×1.25, ×1.5, ×2, ×3, ×4, ×6, ×8, Auto |
| Image Freeze | Switch | On/Off |
| Proportional Pan | Switch | On/Off |
| Lens Initialization | Switch | On/Off |

**Other**

| Entity | Type | Example |
|--------|------|---------|
| Scene Mode | Select | Outdoor, Indoor |
| Power Line Frequency | Select | 50 Hz, 60 Hz |
| Capture Mode | Select | Off, 1920×1080@30fps *(varies by model)* |
| Image Loss Detection | Switch | On/Off |

Several rows say "(varies by model)", see section "Translation coverage gaps warning"

Additional entities appear on specific models: P-Iris controls (motorized zoom cameras), focus mode, scene mode, lens distortion correction (panoramic cameras), IR high/low brightness, and more.

## Conflict Resolution

Several camera features are mutually exclusive-the camera will reject changes if a conflicting feature is active. This integration handles it automatically:

- Enabling **WDR** while **HLC** or **BLC** is active → auto-disables the blocker first, then enables WDR
- Enabling **BLC** while **WDR** is active → auto-disables WDR first
- Enabling **HLC** while **WDR** is active → auto-disables WDR first
- **HLC** and **BLC** can coexist — no conflict

Just set what you want. If something is in the way, the integration disables it and retries-no manual juggling required.

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

I think this is how they work anyway, it confuses me every time I mess with it. Play with the settings and see what works for you.

**Recommended setup for automations:**

Leave **Supplement Light** set to "White Light" and **Light Brightness Mode** set to "Manual" all the time. Then automate with just two controls:

- **Brightness slider** — set the intensity you want (0–100)
- **Day/Night Mode** — switch between "Night" and "Auto" (or "Day") to control when the light activates

This is simpler than toggling multiple entities, and it matches how the camera actually works.

**Important caveats:**

- **Day/Night Mode affects image quality**, not just the light. On most cameras it controls the IR cut filter and internal image processing. The "Night" setting genuinely looks better at night, so switching between "Night" at sunset and "Auto" at sunrise is what's been working for me.

- **"Smart Supplement Light"** (the switch entity, if present) is an overexposure suppression feature — it auto-dims the light to reduce glare on nearby objects. It does **not** turn the light on or off. This frustrated me to no end, there's even a note in the camera UI explaining this, but I missed it for a long time. I have one of these cameras looking straight down a wall, and this setting does seem to keep the image from blowing out when the light first turns on.

## Tested Cameras

| Model | Type | Notes |
|-------|------|-------|
| DS-2CD2187G2-LSU | ColorVu 4K dome | Fixed iris, white supplement light |
| DS-2CD2387G2-LU and DS-2CD2387G2-LSU/SL | ColorVu 4K turret | Fixed iris, white supplement light |
| DS-2CD2T87G2P-LSU/SL | Panoramic ColorVu bullet | Wide-angle, lens distortion correction |
| PCI-D18Z2HS | Motorized zoom dome | IR, P-Iris, focus control |

Should work with any Hikvision camera that supports the `/ISAPI/Image/channels/1` endpoint (most modern models). If your camera doesn't work, holler at me, I'll see what we can track down.

## Languages

The integration's entity names, dropdown options, and setup dialog are translatable. Available so far:

- English (`en`) — default/fallback
- French (`fr`)
- Chinese, Simplified (`zh-Hans`)
- Chinese, Traditional (`zh-Hant`)

Home Assistant picks the file that matches your profile's language setting (**Settings → General → Language**, or your per-user profile language) automatically — nothing to configure in the integration itself. If your language isn't listed, it falls back to English.

### Contributing a translation

1. Copy `custom_components/hikvision_isapi/translations/en.json` to `<language_code>.json` in the same folder, using a [BCP 47](https://developers.home-assistant.io/docs/translations/) language tag (e.g., `de.json`, `es.json`, `pt-BR.json`).

   **Important:** the filename must exactly match a tag from Home Assistant's own list of supported languages — the same list used to populate the language dropdown in a user's profile settings. A tag can be valid BCP 47 and still not work here if HA itself doesn't recognize it (e.g. use `zh-Hans`/`zh-Hant`, not `zh-CN`/`zh-HK` — Home Assistant only ships the former). If in doubt, check what your own Settings → your profile → Language dropdown actually offers.
2. Translate the values on the right-hand side only — never change the keys on the left, or Home Assistant won't be able to match them up.
3. Under `"entity" → "select" → <key> → "state"`, only the *values* need translating — the raw keys (`"close"`, `"auto"`, etc.) are the literal values the camera reports and must stay as-is.
4. Open a PR. If you're not sure a translated string reads naturally, leave a note in the PR — happy to get a second opinion before merging.

### "Translation coverage gaps" warning

Different Hikvision camera models and firmware versions don't all report the same settings the same way — a setting that's a slider (`number`) on one model can be a dropdown (`select`) on another, and the same setting can even live at a differently-cased ISAPI path. When that happens, an entity or a select option can end up with no matching translation entry.

`Zoom Limit Ratio`, `Focus Limit Mode` and `Capture Mode` : We only got a name but never the real option values from a coverage log.

That's harmless: an entity with no translation still gets a readable, generated English name (e.g. "Focus Distance Mode") instead of no name at all, and an untranslated select option just shows its raw camera value. But it's still a **gap worth reporting** — a generated or raw fallback isn't a substitute for a proper name or translation, and it's easy to overlook one quietly showing up in English inside an otherwise fully-translated dashboard.

If you see a log entry in `System -> Logs` like this after setting up the integration:

```
Translation coverage gaps for this camera (harmless — raw values are shown
until these are added to strings.json / translations/en.json):
- Exposure/PIris/Type  (translation_key: exposure_piris_type)  → no entry under entity.select.exposure_piris_type in strings.json; ...
```

it means your camera reported something under a path this integration hasn't seen before — even if the entity itself looks fine in the UI. Please open an issue (or a PR) with that log line and, if possible, the actual option values shown in Home Assistant's entity settings — that's exactly what's needed to add proper naming and translations for your camera model.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) → **Custom repositories**
3. Add `https://github.com/JoshADC/hikvision_isapi` with category **Integration**
4. Click **Install**
5. Restart Home Assistant

### Beta: multi-language support (v1.4.0b1)

A beta with French, Simplified Chinese, and Traditional Chinese translations is available as a [pre-release](https://github.com/JoshADC/hikvision_isapi/releases/tag/v1.4.0b1). It's opt-in only: in HACS, open the integration → ⋮ → **Redownload** → turn on **Show beta versions** → pick `v1.4.0b1`. Note the breaking change in the release notes — dropdowns now report the camera's raw values (e.g. `close` instead of `Off`), so automations that set or compare dropdown values need updating. Feedback goes in [#10](https://github.com/JoshADC/hikvision_isapi/pull/10) or [#6](https://github.com/JoshADC/hikvision_isapi/issues/6).

### Manual

Copy the `custom_components/hikvision_isapi` folder to your Home Assistant `config/custom_components/` directory and restart.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Hikvision ISAPI Image Control**
3. Enter your camera's IP address, username, and password (admin credentials required)
4. Entities are auto-created based on your camera's capabilities

To change the IP or credentials later, use the three-dot menu on the integration entry → **Reconfigure**.

## Troubleshooting

If writes fail with a `lowPrivilege` / permission-denied error in the HA logs, the camera user needs write privileges in the camera's web UI. Hikvision is picky about per-user permissions — even "admin"-style accounts sometimes lack the Remote: Parameters/Configuration bit. Log into the camera's web UI, edit the user, and make sure remote configuration privileges are enabled.

## Example Automations

### Day/Night Exposure Profiles

Switch shutter speed at sunset/sunrise for cameras without auto exposure: (This is an actual automation I made entirely in the UI)

```yaml
alias: HK127 ISAPI
description: Manage HK .127 lighting based on sunrise times
triggers:
  - event: sunset
    trigger: sun
    id: sunset
  - trigger: sun
    event: sunrise
    id: sunrise
conditions: []
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: sunset
        sequence:
          - action: select.select_option
            metadata: {}
            target:
              entity_id: select.ds_2cd2387g2_lu_192_168_8_127_shutter_speed
            data:
              option: 1/120
          - data:
              message: HK .127 Sunset
              data:
                sound: 3rdParty_Failure_Haptic.caf
            action: notify.mobile_app_jdc_iphone_15_pro
      - conditions:
          - condition: trigger
            id: sunrise
        sequence:
          - action: select.select_option
            metadata: {}
            target:
              entity_id: select.ds_2cd2387g2_lu_192_168_8_127_shutter_speed
            data:
              option: 1/150
          - data:
              message: HK .127 Sunrise
              data:
                sound: 3rdParty_Failure_Haptic.caf
            action: notify.mobile_app_jdc_iphone_15_pro
mode: single
```

### Motion Alert → Supplement Light Blast

Crank the light to full brightness on a motion or person detection event, then drop it back down. Works with any NVR or motion sensor — Frigate, Scrypted, SecuritySpy, or a simple binary sensor. Assumes Supplement Light is set to "White Light", Brightness Mode is "Manual", and Day/Night Mode is "Night" or "Auto" in dark conditions (see [Supplement Light vs. Day/Night Mode](#supplement-light-vs-daynight-mode)): (Sample automation by Claude)

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

### Lux-Driven Exposure (Community)

[@baylanger](https://github.com/baylanger) built a full Home Assistant package that drives exposure continuously from an ambient light sensor, rather than switching between fixed profiles at sunset/sunrise. It computes gain and shutter speed from live lux readings on a log curve, and handles the day/night flip with a separate threshold in each direction so passing clouds don't cause flapping. It also sequences its writes around the mutually-exclusive feature rules described above.

**[hikvision_isapi-lux-automation](https://github.com/baylanger/hikvision_isapi-lux-automation)**

Built against a DS-2CD2385G1-I with an Aeotec multisensor mounted indoors, pointed out a window facing the same direction as the camera. The lux sensor is swappable without editing YAML; the camera-side entity IDs need editing for your own camera.

## Technical Details

- **Protocol:** ISAPI over HTTP with digest authentication (automatic fallback to basic auth for old cameras like the DS-2CD8464F-EI that don't support digest)
- **Polling:** Current values polled every 30 seconds (configurable in future release)
- **Write method:** Read-modify-write with raw XML string manipulation (ElementTree re-serialization mangles Hikvision's repeated xmlns declarations, causing the camera to reject PUTs)
- **Conflict resolution:** Two-step sequential PUTs — camera validates against current state, not the PUT body

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Hangzhou Hikvision Digital Technology Co., Ltd. "Hikvision" and "ISAPI" are trademarks of their respective owners. Use at your own risk.
