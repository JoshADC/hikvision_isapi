## Dropdown values: existing cameras are unchanged

This release adds multi-language support. To make translated dropdowns
possible, **new cameras** use the camera's own value as the state of each
dropdown (`select` entity), like `close` or `colorVuWhiteLight`, instead
of an English word like `Off` or `White Light`. Home Assistant shows those
values in your language.

**Cameras you already have keep the English words.** On update, each
existing camera is set to **Keep old dropdown values**, so automations,
scripts and templates that use `option: "Off"` and similar keep working.
Nothing needs to change.

When you're ready for translated dropdowns on an existing camera: the
integration entry → **Configure** → turn off **Keep old dropdown values**.
After that, any automation that sets or checks an old English word on that
camera's dropdowns must use the new value instead. Developer Tools →
States shows each dropdown's current value.

Values that are numbers, like shutter speed `1/120`, are the same either
way. `switch.` and `number.` entities are not affected.

## What's new / changed

- **Multi-language support** for entity names and select dropdown
  options, via Home Assistant's standard `translation_key` mechanism.
  Available languages: English, French, Chinese (Simplified), Chinese
  (Traditional).
- **Expanded camera support**: many additional settings discovered and
  named from a PTZ camera models (image stabilization, digital slow
  shutter, focus limiting, zoom limits, IR light controls, event
  intelligence lighting, and more), in addition to the original fixed
  dome camera settings.
- **New: automatic translation coverage checks.** If your camera reports
  a setting this integration doesn't have a name or translation for yet,
  it now shows up as a Repairs notice (Settings → System → Repairs) in
  addition to the log — no need to dig through logs to notice it.
- **New: optional camera name when adding a camera.** It becomes the
  device name and the start of every entity ID, e.g. `Porch` gives
  `select.porch_shutter_speed`. Leave it blank for the old model + IP
  naming. Existing cameras are not renamed.
- Bug fix: a blocking-I/O warning during the translation coverage check.

## Upgrade notes

- Existing entity IDs, unique IDs, entity names, and entity history are
  unaffected.
- Rolling back to v1.3.0 still works.
- If you're not sure whether an automation is affected, check its
  current option value in Developer Tools → States before and after
  upgrading, or open an issue and we can help confirm the right value.

## Closes following PR & Issues

- PR #10 [feat] add support for multi-language @baylanger
- Issue #6 Could you support Chinese language? @kou147258
- Issue #11 Allow customizable entity_id naming @baylanger
