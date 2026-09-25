## ⚠️ Breaking Change: `select` entity values

This release adds multi-language support. As part of that, **any `select`
entity from this integration now exposes the camera's raw value as its
state, instead of a translated English word.**

Before, a select's value (not just its displayed label) was already
translated — e.g. `Off`, `On`, `White Light`. Automations, scripts, and
templates that used `option: "Off"` or compared `states('select.xxx')`
to one of these words were reading and writing that translated value
directly.

Now, the select's actual value is the camera's own raw setting — e.g.
`close`, `open`, `colorVuWhiteLight`. Home Assistant translates that raw
value into a friendly, localized label for display, but the value your
automations see and set is the raw one.

**This means:** if you have an automation, script, or template that sends
or checks an option like `"Off"`, `"On"`, `"White Light"`, `"Auto"`, etc.
on one of this integration's dropdown (`select.`) entities, it will break
after upgrading and needs to be updated to use the new raw value instead.

This is the correct, necessary trade-off to make translation possible —
Home Assistant expects an entity's value to be stable and
language-independent, with translation handled as a display concern on
top of it — but it does mean a one-time update is needed for existing
automations.

**Not affected:** `switch.` entities (BLC, HLC, Image Flip, etc.) and
`number.` entities (Brightness, Gain, WDR Level, etc.) — neither of these
was ever translated at the value level, only `select.` entities were.

### How to check if you're affected

1. Settings → Automations & Scenes — review any automation with a
   trigger/condition/action on a `select.` entity from this integration.
2. Developer Tools → States — filter by `select.` and this integration's
   device to see each entity's current raw value.
3. Update any hardcoded option strings to match the new raw values shown
   there.

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
- Bug fixes found and fixed during this work: a blocking-I/O warning.
  coverage check.

## Upgrade notes

- Existing entity IDs, unique IDs, and entity history are unaffected —
  only the underlying select values changed, not how entities are
  identified.
- If you're not sure whether an automation is affected, check its
  current option value in Developer Tools → States before and after
  upgrading, or open an issue and we can help confirm the right value.

## Closes following PR & Issues

- PR #10 [feat] add support for multi-language @baylanger
- Issue #6 Could you support Chinese language? @kou147258
