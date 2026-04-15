# Hikvision ISAPI Home Assistant Integration

Custom HA integration for granular image/exposure control of Hikvision cameras via ISAPI.

## Goal

Expose every useful image setting as a native HA entity (switch, number slider, select dropdown) so users can automate exposure, WDR, supplement light, noise reduction, etc. — things no existing integration touches.

## Why This Exists

- **HA core `hikvision`**: Legacy, read-only. Camera streams + binary sensors only. Zero device control.
- **`hikvision_next`** (HACS): Better (event switches, reboot, diagnostics) but still doesn't touch image/exposure settings.
- **Scrypted Hikvision plugin**: Exposes a supplement light switch, but it only works if the camera's settings are pre-configured a certain way in the web UI.

This integration fills the gap: full image tuning from HA, with prerequisite handling so commands actually work.

## Test Cameras

| Camera | Model | Address | Firmware | Type | Notes |
|--------|-------|---------|----------|------|-------|
| Test mule | DS-2CD2187G2-LSU | 192.168.8.130 | V5.7.19 (241207) | ColorVu 4K turret, fixed iris, white supplement light | On desk, safe to poke |
| Zoom/IR | PCI-D18Z2HS | 192.168.8.126 | V5.7.18 (240924) | Motorized zoom, IR, P-iris | On desk |
| Panoramic | DS-2CD2T87G2P-LSU/SL | 192.168.8.155 | V5.7.20 (251125) | Panoramic ColorVu bullet, wide-angle, fixed iris | Mounted, live |
| Turret 3MP | DS-2CD2387G2-LU | 192.168.8.127 | V5.7.19 (241207) | ColorVu 3MP turret, fixed iris, white supplement light | Mounted, live, extensively tuned |

- **Credentials (all):** admin / F13897921$ (except .127: admin / 13897921$)

## ISAPI Findings (2026-02-09)

### Entity Map (discovered from `/ISAPI/Image/channels/1/capabilities`)

#### Common Entities (all cameras tested)

| ISAPI Setting | English Name | Entity Type | Options / Range |
|---------------|-------------|-------------|-----------------|
| `WDR/mode` | WDR | select | Off (`close`), On (`open`), Auto |
| `WDR/WDRLevel` | WDR Level | number | 0–100 |
| `BLC/BLCMode` | BLC Mode | select | Off (`CLOSE`), Up, Down, Left, Right, Center, Region, Auto (linked: controls `BLC/enabled` automatically) |
| `HLC/enabled` | HLC | switch | On/Off |
| `HLC/HLCLevel` | HLC Level | number | 0–100 |
| `IrcutFilter/IrcutFilterType` | Day/Night Mode | select | Day, Night, Auto, Schedule |
| `IrcutFilter/nightToDayFilterLevel` | Night-to-Day Sensitivity | select | 0–7 (discrete `opt=`) |
| `IrcutFilter/nightToDayFilterTime` | Night-to-Day Delay | number | 5–120 (seconds) |
| `Exposure/ExposureType` | Iris Mode | select | varies by camera (see below) |
| `Exposure/OverexposeSuppress/enabled` | Smart Supplement Light | switch | On/Off |
| `Shutter/ShutterLevel` | Shutter Speed | select | varies (e.g., 1/3–1/100000, 22 values on ColorVu; 1/30–1/100000 on zoom/IR) |
| `Gain/GainLevel` | Gain | number | 0–100 |
| `Color/brightnessLevel` | Brightness | number | 0–100 |
| `Color/contrastLevel` | Contrast | number | 0–100 |
| `Color/saturationLevel` | Saturation | number | 0–100 |
| `Color/grayScale/grayScaleMode` | Color Space | select | Outdoor, Indoor |
| `Sharpness/SharpnessLevel` | Sharpness | number | 0–100 |
| `NoiseReduce/mode` | Noise Reduction | select | Off (`close`), Normal (`general`), Advanced |
| `NoiseReduce/GeneralMode/generalLevel` | Noise Reduction Level | number | 0–100 |
| `NoiseReduce/AdvancedMode/FrameNoiseReduceLevel` | Spatial NR Level | number | 0–100 |
| `NoiseReduce/AdvancedMode/InterFrameNoiseReduceLevel` | Temporal NR Level | number | 0–100 |
| `Dehaze/DehazeMode` | Defog | select | Off (`close`), Auto, On (`open`) |
| `Dehaze/DehazeLevel` | Defog Level | number | 0–100 |
| `WhiteBalance/WhiteBalanceStyle` | White Balance | select | Manual, Auto 1, Auto 2, Locked, Fluorescent, Incandescent, Warm Light, Natural Light |
| `WhiteBalance/WhiteBalanceRed` | White Balance Red | number | 0–100 |
| `WhiteBalance/WhiteBalanceBlue` | White Balance Blue | number | 0–100 |
| `ImageFlip/enabled` | Image Flip | switch | On/Off |
| `ImageFlip/ImageFlipStyle` | Flip Direction | select | Left-Right, Up-Down, Center |
| `powerLineFrequency/powerLineFrequencyMode` | Power Line Frequency | select | 50 Hz, 60 Hz |

#### ColorVu-Only Entities (white supplement light cameras)

| ISAPI Setting | English Name | Entity Type | Options / Range |
|---------------|-------------|-------------|-----------------|
| `SupplementLight/supplementLightMode` | Supplement Light | select | On (`colorVuWhiteLight`), Off (`close`) |
| `SupplementLight/whiteLightBrightness` | Light Brightness | number | 0–100 |
| `SupplementLight/mixedLightBrightnessRegulatMode` | Light Brightness Mode | select | Auto, Manual |

#### IR Camera-Only Entities (e.g., PCI-D18Z2HS)

| ISAPI Setting | English Name | Entity Type | Options / Range |
|---------------|-------------|-------------|-----------------|
| `SupplementLight/supplementLightMode` | Supplement Light | select | IR (`irLight`), Off (`close`) |
| `SupplementLight/highIrLightBrightness` | IR High Brightness | number | 0–100 |
| `SupplementLight/lowIrLightBrightness` | IR Low Brightness | number | 0–100 |

#### P-Iris / Motorized Lens Entities (e.g., PCI-D18Z2HS)

| ISAPI Setting | English Name | Entity Type | Options / Range |
|---------------|-------------|-------------|-----------------|
| `Exposure/autoIrisLevel` | Auto Iris Level | number | 0–100 |
| `Exposure/pIris/pIrisType` | P-Iris Mode | select | Auto, Manual |
| `Exposure/pIris/IrisLevel` | P-Iris Level | number | 1–100 |
| `Scene/mode` | Scene Mode | select | Outdoor, Indoor |
| `FocusConfiguration/focusStyle` | Focus Mode | select | Auto, Manual, Semi-automatic |

#### Panoramic Camera-Only Entities (e.g., DS-2CD2T87G2P-LSU/SL)

| ISAPI Setting | English Name | Entity Type | Options / Range |
|---------------|-------------|-------------|-----------------|
| `LensDistortionCorrection/enabled` | Lens Distortion Correction | switch | On only (`opt="true"`) |
| `LensDistortionCorrection/accurateLevel` | Correction Level | number | 0–100 |

### Key Findings from Multi-Camera Probing (2026-02-10)

#### "Smart Supplement Light" = `OverexposeSuppress/enabled`

Confirmed via toggle test on .155 (DS-2CD2T87G2P-LSU/SL). The Hikvision web UI shows this as "Smart Supplement Light" with tooltip "The function can help reduce overexposure caused by the white supplement light." In ISAPI, it's `Exposure/OverexposeSuppress/enabled`. Present on all cameras tested. We label it "Smart Supplement Light" in the integration to match the UI.

#### `ExposureType` = Iris Mode, NOT Exposure Control

`Exposure/ExposureType` controls the **iris**, not overall exposure. On the PCI-D18Z2HS (motorized zoom with P-iris), it has options `auto, manual, pIris-General` — these control iris behavior while shutter and gain remain independent manual controls. On fixed-iris ColorVu cameras, it's stuck at `manual` (the only option) because there is no iris to control. Should be labeled "Iris Mode" and hidden on cameras where it only has one option.

#### No Camera Has True Auto Exposure

None of the four cameras tested offer automatic shutter+gain adjustment. Shutter speed and gain are always fixed manual values — not upper limits. Setting shutter to 1/100000 and gain to 0 results in a black image. This is the core motivation for the integration: automating exposure profile switches (e.g., sunset → 1/120 shutter + higher gain, sunrise → 1/150 shutter + lower gain) since the cameras won't do it themselves.

#### Anti-Banding: Flag Exists, Endpoint Doesn't Work

The .127 camera reports `isSupportAntiBandingParams=true` in capabilities, but the actual endpoint returns `Invalid Operation`. The web UI exposes it as a simple on/off toggle. Even when enabled, rolling flicker/banding can be bad at night with certain shutter speeds. Not reliably controllable via ISAPI.

#### Capabilities Vary Significantly by Camera Model

| Feature | .130 (ColorVu 4K) | .126 (Zoom/IR) | .155 (Panoramic) | .127 (ColorVu 3MP) |
|---|---|---|---|---|
| Iris Mode | manual only | auto/manual/pIris | manual only | manual only |
| Shutter range | 1/3–1/100000 | 1/30–1/100000 | 1/3–1/100000 | 1/3–1/100000 |
| Supplement Light | white (ColorVu) | IR (high/low) | white (ColorVu) | white (ColorVu) |
| Focus control | no | auto/manual/semi | no | no |
| Scene mode | no | outdoor/indoor | no | no |
| Lens correction | no | no | on + level | no |
| P-Iris | no | yes | no | no |
| Anti-banding flag | no | no | no | yes (broken) |
| IrcutFilter Schedule | no | yes | yes | yes |

This validates the dynamic entity creation approach — the capabilities XML is self-describing and we generate entities from it.

### Naming Translation (Hikvision Chinese-to-English)

Throughout ISAPI, Hikvision uses Chinese software conventions. We translate to plain English:
- `open` / `close` → **On** / **Off** (e.g., WDR mode `open` = WDR On)
- `general` → **Normal** (noise reduction)
- `colorVuWhiteLight` → **On** or **White Light** (supplement light)
- `auto1` / `auto2` → **Auto 1** / **Auto 2** (white balance — Hikvision's own distinction)
- `daylightLamp` → **Fluorescent**
- `incandescentlight` → **Incandescent**
- `warmlight` → **Warm Light**
- `naturallight` → **Natural Light**

### Mutual Exclusivity (Tested)

The camera rejects conflicting settings with machine-readable error codes:

| Action | While Active | Result | Error Code |
|--------|-------------|--------|------------|
| Enable HLC | WDR on | **Rejected** | `WDRNotDisable` |
| Enable BLC | WDR on | **Rejected** | `MutexWithWDR` |
| Enable WDR | HLC on | **Rejected** | `HLCNotDisable` |
| Enable WDR | BLC on | **Rejected** | `BLCNotDisable` |
| Enable BLC | HLC on | **Accepted** | — |

**Summary:** WDR conflicts with both HLC and BLC (bidirectional). HLC and BLC can coexist.

**Strategy:** When a user enables a setting, the integration checks for conflicts, auto-disables the blocker in a **separate PUT first**, then retries the original change. Combined PUTs are rejected — the camera validates against current state, not the PUT body. All affected entity states update in HA after the coordinator refreshes.

### Supplement Light Behavior (ColorVu Cameras)

The supplement light is a **two-layer system**:

1. **Config layer** (`supplementLightMode`, `whiteLightBrightness`, `mixedLightBrightnessRegulatMode`) — sets *intent*: "when the light activates, use these settings"
2. **Trigger layer** (`IrcutFilterType` / Day/Night Mode) — controls whether the light is physically on

**Tested behavior:**
- Day/Night Mode = **Night** + Supplement Light = On + Brightness > 0 → **light physically ON**
- Day/Night Mode = **Day** + any supplement config → **light physically OFF**
- Day/Night Mode = **Auto** → camera decides based on ambient light sensor
- Changing Day/Night Mode does NOT reset the supplement light config
- Changing supplement light config does NOT change Day/Night Mode

**For automation (e.g., Frigate alert → blast light for 30 seconds):**
1. Pre-configure: Supplement Light = On, Brightness Mode = Manual, Brightness = 100
2. Light ON: Set Day/Night Mode = Night
3. Light OFF: Set Day/Night Mode = Auto (or Day)

**Important:** On ColorVu cameras (no IR), "Day/Night Mode" is misleading — there is no actual IR cut filter or B&W mode. It's effectively just the trigger for the white supplement light.

### VCA / Third Stream Relationship (Tested)

- **VCA = `close`** → third stream (channel 103, 1080p) available
- **VCA = `smart`** (Smart Event) → third stream disappears from channel listing
- **VCA = `facesnap`** → not tested yet
- VCA options from capabilities: `smart, facesnap, close`
- Changing VCA requires a camera reboot

Scrypted's Hikvision plugin auto-enables this third stream (likely sets VCA to `close`). We probably don't need to manage this ourselves, but should expose it as a select entity for users who want to toggle it from HA. Should warn that changing this requires a reboot.

## Architecture

```
custom_components/hikvision_isapi/
├── __init__.py              # Integration setup, platforms
├── manifest.json            # Integration metadata
├── config_flow.py           # Config flow (IP, user, pass, digest auth validation)
├── coordinator.py           # DataUpdateCoordinator — polls ISAPI for current values
├── isapi_client.py          # Async HTTP client (httpx, digest auth, XML parse/build)
├── capabilities.py          # Parse capabilities XML → entity descriptors (type, options, range)
├── prerequisites.py         # Mutual exclusivity engine — knows what to disable before enabling
├── entity.py                # Base entity class
├── switch.py                # true/false toggles (HLC, BLC, overexposure suppress, etc.)
├── number.py                # min/max sliders (brightness, gain, sharpness, levels, etc.)
├── select.py                # opt="a,b,c" dropdowns (WDR mode, shutter, white balance, etc.)
├── strings.json             # UI strings
└── translations/en.json     # English translations
```

### Key Design Decisions

1. **Dynamic entity creation** — capabilities XML is self-describing (`opt=` for selects, `min/max` for sliders, `opt="true,false"` for switches). We parse it and generate entities automatically. Different camera models get different entities based on what they actually support.

2. **Prerequisite engine** — rather than hardcoding conflict rules, we can either:
   - (a) Maintain a tested conflict table (safer, predictable)
   - (b) Try-fail-retry: attempt the command, if we get `WDRNotDisable` etc., auto-disable the blocker and retry
   - (c) Both: use the known table, fall back to try-fail-retry for unknown conflicts
   - **Decision: (c)** — belt and suspenders.

3. **Honest entity exposure** — each ISAPI setting maps 1:1 to an HA entity. No "smart" compound switches that hide behavior. Users see exactly what's happening and build automations however they want.

4. **English translations** — all Hikvision Chinese conventions (`open`/`close`, `general`, etc.) translated to plain English in the UI. The underlying ISAPI values are internal only.

5. **Scope: image controls only** — no streaming, storage, events, or NVR features. Assumes users have Frigate or another NVR for that.

6. **Polling, not events** — image settings rarely change externally. Poll every 30–60s (configurable). No alert stream needed.

7. **HACS distribution** — build for public release from the start. Support multiple camera models, good error handling, clear documentation.

## Build Phases

### Phase 1: ISAPI Client + Discovery — DONE (2026-02-10)
- Async HTTP client with digest auth (httpx)
- Capabilities XML parser → list of entity descriptors
- Test script: connect to camera, print "here are all the entities this camera would expose"
- Tested against all 4 cameras: .130 (33 entities), .126 (40), .155 (30), .127 (34)
- **Note:** Homebrew Python 3.12–3.14 on macOS has a network entitlement issue (sockets fail with "No route to host"). System Python 3.9.6 and curl work fine. Not an issue inside HAOS.

### Phase 2: HA Integration Shell — DONE (2026-02-10)
- Config flow (IP, credentials, validate connection via `/ISAPI/System/deviceInfo`)
- DataUpdateCoordinator (poll `/ISAPI/Image/channels/1` for current values every 30s)
- Dynamic entity creation from capabilities XML
- Deployed to HAOS, confirmed working: entities appear, camera UI changes reflected in HA
- **Fixed (v1.1.0):** `httpx.AsyncClient()` creation triggers a blocking `load_verify_locations` call on the event loop. Fixed by wrapping in `asyncio.to_thread()`.

### Phase 3: Write-Back — DONE (2026-02-11)
- Entity set methods (switch toggle, number slider, select dropdown) all wired up
- Prerequisite engine built: known conflict table + try-fail-retry for unknown conflicts
- Optimistic updates + coordinator refresh after write
- Tested on .126 (PCI-D18Z2HS): all switches, numbers, selects write successfully
- WDR/HLC/BLC mutual exclusivity works bidirectionally (auto-disables the other)

#### The PUT Problem (solved 2026-02-11)

The camera requires the **FULL** `ImageChannel` XML document on every PUT. Python's ElementTree mangles XML namespaces when re-serializing (strips repeated `xmlns` declarations on child elements), causing the camera to reject with `deviceError`.

**Fix:** Raw string manipulation in `isapi_client.py`:
1. GET raw bytes from camera
2. Parse with ET **read-only** to find current values
3. `_raw_replace()` — regex find-and-replace scoped within parent XML block (e.g., changes `BLC/enabled` without touching `HLC/enabled`)
4. PUT the barely-modified raw string back (preserving exact XML format)

#### Sequential Prerequisites (discovered 2026-02-11)

The camera validates conflicts against its **current state**, not the PUT body. A combined PUT (disable HLC + enable WDR in one request) is still rejected with `HLCNotDisable`. The fix is two sequential PUTs:
1. PUT to disable the blocker (e.g., HLC off)
2. PUT to enable the target (e.g., WDR on)

Updated `prerequisites.py` to use this two-step approach.

#### BLC Linked Mode Pattern (solved 2026-02-11)

On cameras where BLC has both `enabled` (true/false) and `BLCMode` (CLOSE/UP/DOWN/LEFT/RIGHT/CENTER/Region/AUTO), the camera UI presents them as a single dropdown where "Off" = `BLCMode=CLOSE`. Two problems solved:

1. **Merged entity model** — `capabilities.py` auto-detects the enabled+mode pattern (parent has both an `enabled` switch and a mode select with a CLOSE/close option). The switch is removed and the select takes ownership of both fields, matching the camera UI's single-dropdown behavior. Uses `linked_enabled_path` and `off_value` on EntityDescriptor.

2. **Absent mode tag** — When BLC is disabled, `<BLCMode>` disappears entirely from the camera's current values XML. `put_setting_with_enable()` in `isapi_client.py` handles inserting the tag (via `_raw_insert_after()`) when enabling, and `current_option` in `select.py` always checks the linked enabled flag to determine off state rather than relying on the (possibly stale) mode value.

#### MutexWithWDR Bidirectional Resolution (solved 2026-02-11)

`MutexWithWDR` is returned both when enabling something while WDR is active AND when enabling WDR while BLC/HLC is active. The resolution is context-aware: if the target path IS `WDR/mode`, the resolution disables BLC and HLC (the actual blockers) instead of trying to disable WDR (which is already off).

#### No Lux Measurement via ISAPI (confirmed 2026-02-11)

Probed ~40 endpoints on .126 — no ambient light/lux reading exposed. The cameras have an internal light sensor (evidenced by adjustable `nightToDayFilterLevel`), but the raw reading stays internal. `IrcutFilterType` shows the **configured mode** (auto/day/night), not the current detected state, so it can't be used as a day/night trigger when set to auto. Best automation triggers for exposure switching: HA `sun.sun` elevation or external lux sensor.

### Phase 4: Polish & Release
- Entity categories (config vs diagnostic)
- Icons per entity type
- Options flow for poll interval
- VCA select entity (with reboot warning)
- ~~Fix blocking `load_verify_locations` warning~~ — Fixed in v1.1.0
- ~~Clearer error message when camera user lacks write privileges~~ — Fixed in v1.1.1 (HTTP 403 now surfaces a permission hint pointing users to the camera's web UI; diagnosed from issue #2)
- ~~Reconfigure flow for existing entries~~ — Added in v1.2.0 (three-dot menu → Reconfigure lets users change host/credentials without delete+re-add; MAC-match safety check prevents repointing an entry at a different camera)
- Disable single-option selects by default
- HACS repo structure, README, documentation
- Sample automations (day/night exposure profiles, Frigate alert → supplement light blast)
- Test with additional camera models

## Development Notes

### Deployment to HAOS

```bash
# From Mac, deploy individual files (rsync fails due to pycache permissions):
ssh haos 'sudo tee /config/custom_components/hikvision_isapi/FILE.py > /dev/null' < custom_components/hikvision_isapi/FILE.py

# Or deploy all files at once:
for f in custom_components/hikvision_isapi/*.py; do
  ssh haos "sudo tee /config/custom_components/hikvision_isapi/$(basename $f) > /dev/null" < "$f"
done

# Restart HA:
ssh haos 'sudo docker restart homeassistant'

# Check logs:
ssh haos 'sudo docker logs homeassistant 2>&1 | grep -i "hikvision\|isapi" | tail -50'
```

### Homebrew Python Network Issue (macOS only)

All Homebrew-installed Python versions (3.12, 3.13, 3.14) fail to open sockets to local IPs on macOS with `[Errno 65] No route to host`. System Python (`/usr/bin/python3`, 3.9.6) works fine. This is a macOS network entitlement issue with Homebrew binaries. The test_discovery.py script works around this by shelling out to curl. Not an issue inside HAOS/Docker.
