# Bosch eBike Flow Integration for Home Assistant [Fork]

<!--
> [!NOTE]  
> Highlights information that users should take into account, even when skimming.

> [!TIP]
> Optional information to help a user be more successful.

> [!IMPORTANT]  
> Crucial information necessary for users to succeed.

> [!WARNING]  
> Critical content demanding immediate user attention due to potential risks.

> [!CAUTION]
> Negative potential consequences of an action.
-->

[![hacs_badge][hacsbadge]][hacs] [![hainstall][hainstallbadge]][hainstall] [![Wero][werobadge]][wero] [![Revolut][revolutbadge]][revolut] [![PayPal][paypalbadge]][paypal] [![github][ghsbadge]][ghs] [![BuyMeCoffee][buymecoffeebadge]][buymecoffee]


Monitor and control your Bosch eBike directly from Home Assistant! Track battery level, charging status, range estimates, and create smart charging automations.

> [!IMPORTANT]
> ## Minimum requirements:
> In minimum this integration requires:
> - __Bosch eBike Flow__ app (Gen 4 systems)
>
> This integration __will NOT work__ with the _older_ __Bosch eBike Connect__ app (Gen 3 and below).
>
> ### Additional requirements when you want to have ___live___ battery & energy information:
> - a __ConnectModule__ hardware installed on your bike (sold separately, (~€100-150)
> - an active __Bosch eBike Flow+__ subscription (~€30-50/year)
> 
> __Only__ when you have this additional hardware and an active Flow+ subscription, then the integration __can access your _live_ battery & energy data__. Only after you have installed this additional hardware on your eBike, live-battery-data will be sent from your bike to the Bosch backend systems.

## Sample Panel
![Bosch eBike](https://raw.githubusercontent.com/marq24/ha-bosch-ebike-flow/refs/heads/main/images/screenshot.png)

## Features

### 📈 Basic Sensors<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_without additional hardware & subscription_
- __Total Distance/Odometer__ – Total distance cycled<br/>(the integration will also import history data from your previous activities)
- __Charge Cycles__ – Number of full charge cycles completed
- __Lifetime Energy__ – Total energy delivered over the bike's lifetime
- __Battery Capacity__ – Total battery capacity
- __BASIC Reachable Range__ – Estimated range per riding mode
- Component Details – Serial numbers and product info
- Software Versions – Track firmware versions of all components

### 📊 Extended Sensors / 🚴 Advanced Sensors<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_with additional hardware & subscription_
- __Battery Level__ – Real-time battery percentage (SOC))
- __Battery Remaining Energy__ – Available energy in Watt-hours
- __Battery Charging__ – Active charging status
- __Live Reachable Range__ – Estimated range per riding mode (when bike is online)

### ⚡ Smart Features (Basic)
- Cloud-based polling every 5 minutes
- OAuth2 authentication with Bosch eBike Flow
- Multi-bike support (if you have multiple eBikes)

### ⚡ Smart Features<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_with additional hardware & subscription_
- Real-time updates while charging

---

## Requirements
### Software

- 📱 __Bosch eBike Flow__ app installed and working
- 🏠 __Home Assistant__ 2025.1.0 or newer
- 🌐 Internet connection for cloud API access

### Hardware

__A compatible Bosch Systems (Gen 4 Only) eBike__. This integration __ONLY__ works with the Generation 4 of the Bosch eBike Systems, that are using the Bosch Flow-MobileApp. Compatible systems are:

- ✅ Performance Line CX (Gen 4)
- ✅ Performance Line (Gen 4)
- ✅ Cargo Line (Gen 4)
- ✅ Any Gen 4 system with ConnectModule installed

__Not Compatible:__

- ❌ Gen 3 and older Bosch systems (use Bosch eBike Connect app)
- ❌ Non-Bosch eBike systems
- ❌ Bosch systems without ConnectModule hardware

### Additional optional requirements<br/>(for live battery & energy data)
When you want to make use of the _optional_ extended __battery sensor data__ (like SOC), __then there are additional requirements:__

#### Required Hardware (Additional Purchase)

- 🔌 __Bosch ConnectModule__ - Required hardware that connects your bike to the cloud
    - __Cost:__ ~€100-150 (depending on region)
    - __NOT included__ with most bikes by default
    - Must be purchased separately and installed on your bike
    - Available from Bosch dealers or online retailers

#### Required Subscription (Recurring Cost)

- 💳 __Bosch eBike Flow+ Subscription__
    - __Cost:__ ~€30-50/year (varies by region)
    - Required for cloud connectivity and remote features
    - Subscribe through the Bosch eBike Flow app

---

## Installation

### Preparation (optional)
Even if it's optional, it's highly recommended to install [HACS](https://hacs.xyz) (Home Assistant Community Store) to install this integration.

> [!TIP]
> The IMHO simplest way to install this integration is via the two blue buttons below ('_OPEN HACS REPOSITORY ON MY HA_' and '_ADD INTEGRATION TO MY HA_').

### Option 1: Via HACS (Recommended)
[![Open your Home Assistant instance and adding repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=marq24&repository=ha-bosch-ebike-flow&category=integration) 
1. __Add Custom Repository:__
   - Open HACS in Home Assistant
   - Click the 3 dots in the top right
   - Select "Custom repositories"
   - Add URL: `https://github.com/marq24/ha-bosch-ebike-flow`
   - Category: `Integration`
   - Click "Add"
> [!IMPORTANT]
> This is a HACS __custom integration__ — not a Home Assistant __Add-on__. Don't try to add this repository as an add-on in Home Assistant.
>

2. __Install Integration:__
   - Search for "Bosch eBike Flow" in HACS
   - Click "Download"
   - Restart Home Assistant

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=bosch_ebike)

3. __Configure:__
   - Go to Settings → Devices & Services
   - Click "+ ADD INTEGRATION"
   - Search for "Bosch eBike Flow"
   - Follow the OAuth login flow with your Bosch eBike Flow credentials as it's described in the _Configuration - OAuth Setup_ Section

### Option 2: Manual Installation

1. Copy the `custom_components/bosch_ebike` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services

---

## Configuration

### OAuth Setup

> [!IMPORTANT]
> You __MUST__ use a desktop/laptop browser (not a phone/tablet) for initial integration setup for your bike.

The integration uses OAuth2 for secure authentication:

1. Click "Add Integration" and select "Bosch eBike Flow"
2. __Copy the authorization URL__ (or click on it directly – but make sure to open it in a new browser tab)
3. __Paste it in a new browser tab__ on your computer
4. Now __enable__ the __browser developer tools (F12)__ for the new tab/browser window. This must be done before you are entering your login credentials.
5. Log in with your __Bosch eBike Flow__ app credentials.<br>__Please note, that the login screen from Bosch will not complete – you will not be forwarded to a different page__ after you entered the password and pressed _enter_.Basically, you are stuck there by purpose, since you now must manually capture the generated authorization code (generated by the Bosch backend). So after you entered your password, the next step is:
5. Find in the 'network'-tab of the browser developer tools the final authorization request (that is failing by purpose).<br/><br>
    - In the network-tab you will find a line (in red) like (example): <br>
      __<div style="color: #E74C3C;">oauth2redirect?state=akY...&code=dd6...5f8</div>__<br>
      This is the request you are looking for, right-click on this line and select from the menu (submenu) _Copy URL_.<br/><br/>
    - The full URL you are copying should look like this (example): <br/>
     __onebikeapp-ios://com.bosch.ebike.onebikeapp/oauth2redirect?state=akY...&code=dd6...5f8__<br/><br/>
6. Paste the complete copied URL (including the code) back into the Home Assistant setup dialog.
7. Select which bike to monitor (if you have multiple)

__📖 [Detailed Step-by-Step Authentication Guide](AUTHENTICATION_GUIDE.md)__ - Includes screenshots and troubleshooting!

---
## Miscellaneous

### Multiple Bikes

If you have multiple eBikes registered in the Bosch eBike Flow app:

- Add the integration once for each bike
- Each bike will appear as a separate device in Home Assistant

### Understanding Sensor Updates

#### Update Behavior

The ConnectModule updates the Bosch Cloud API when:

- ✅ Bike is __charging__ (plugged in)
- ✅ Bike is __powered on__
- ✅ __Alarm is triggered__ by motion

When the bike is unplugged, powered off, and stationary, the ConnectModule goes into low-power mode and stops sending updates to the Bosch backend (and therefore also this integration will not receive any updated data).

#### What This Means

- 📊 __While charging:__ Sensors update every 5 minutes with current data
- 🔋 __Perfect for:__ Monitoring charge sessions and creating smart charging automations
- ⚠️ __Limited when:__ Bike is stored unplugged and powered off

For detailed sensor reliability information, see [SENSOR_RELIABILITY.md](SENSOR_RELIABILITY.md).

### Example Automations

#### Smart Charging: Stop at 80%

Preserve battery health by stopping the charge at 80%:

```yaml
automation:
  - alias: "eBike: Stop charging at 80%"
    description: "Turn off smart plug when bike reaches 80% to preserve battery"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bfe_[your_frame]_battery_level
      above: 80
    condition:
      - condition: state
        entity_id: binary_sensor.bfe_[your_frame]_battery_charging
      state: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.bike_charger_plug
      - service: notify.mobile_app
        data:
          title: "🔋 eBike Charging Paused"
          message: "Battery at {{ states('sensor.bfe_[your_frame]_battery_level') }}% - charging stopped to preserve battery health"
```

#### Notification: Charging Complete

Get notified when your bike is fully charged:

```yaml
automation:
  - alias: "eBike: Notify when fully charged"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bfe_[your_frame]_battery_level
        above: 99
      - platform: state
        entity_id: binary_sensor.bfe_[your_frame]_battery_charging
        to: "off"
        for:
          minutes: 1
    condition:
      - condition: numeric_state
        entity_id: sensor.bfe_[your_frame]_battery_level
        above: 95
    action:
      - service: notify.mobile_app
        data:
          title: "🚴‍♂️ eBike Ready!"
          message: "Your bike is {{ states('sensor.bfe_[your_frame]_battery_level') }}% charged and ready to ride!"
```

#### Dashboard Card Example

```yaml
type: entities
title: eBike Status
entities:
  - entity: sensor.bfe_[your_frame]_battery_level
    name: Battery Level
  - entity: sensor.bfe_[your_frame]_battery_remaining_energy
    name: Energy Remaining
  - entity: binary_sensor.bfe_[your_frame]_battery_charging
    name: Charging
  - entity: sensor.bfe_[your_frame]_total_distance
    name: Total Distance
  - entity: sensor.bfe_[your_frame]_charge_cycles
    name: Charge Cycles
```

---

## Troubleshooting

### Integration Won't Load

1. Check Home Assistant logs for errors
2. Ensure you're running HA 2024.1.0 or newer
3. Try restarting Home Assistant after installation

### OAuth Login Fails

1. Make sure you're using your __Bosch eBike Flow app__ credentials
2. Check that your bike is registered in the Bosch eBike Flow app
3. Ensure your ConnectModule is paired and online

### Sensors Show "Unavailable"

1. Check that your bike's ConnectModule is paired with the Flow app
2. Power on your bike or plug it in to trigger an update
3. Wait up to 5 minutes for the next polling cycle

### Data Not Updating

The ConnectModule only sends updates when:

- Bike is charging
- Bike is powered on
- Alarm is triggered

This is normal behavior. The sensors will update once you power on or plug in your bike.

---

## Advanced

### Enable Diagnostic Sensors

Additional sensors are disabled by default but can be enabled:

1. Go to Settings → Devices & Services
2. Find your eBike device
3. Click the device
4. Enable desired sensors (software versions, serial numbers, etc.)

### Logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.bosch_ebike: debug
```

---

## Support & Contributing

### Get Help & Report Issues

- 🐛 __Report Bugs:__ [GitHub Issues](https://github.com/marq24/ha-bosch-ebike-flow/issues)
- 💬 __Discussions:__ [GitHub Discussions](https://github.com/marq24/ha-bosch-ebike-flow/discussions)
<!-- - 📖 __Documentation:__ [Wiki](https://github.com/marq24/ha-bosch-ebike-flow/wiki)
- 🤝 __Contributing:__ [DEPLOYMENT.md](DEPLOYMENT.md) for development setup  -->

### Support Development
If you like this integration and want to support the development, please consider supporting me on:

[![github][ghsbadge]][ghs] [![Wero][werobadge]][wero] [![Revolut][revolutbadge]][revolut] [![PayPal][paypalbadge]][paypal] [![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

Your support helps maintain and improve this integration. Thank you! ☕

---

## Disclaimer

This is an __unofficial__ integration and is __not affiliated with, endorsed by, or supported by Bosch eBike Systems__.

Use at your own risk. The author is not responsible for any damage to your bike, battery, or Home Assistant system.

---

## Credits / Kudos
- Thanks to [Phil-Barker](https://github.com/Phil-Barker/hass-bosch-ebike) for developing the origin integration.<br/>[![BuyPhilACoffee][philcoffee]](https://buymeacoffee.com/philbarker)
- Thanks to the Home Assistant community
- Built with the Home Assistant integration framework
- Bosch eBike Flow API (reverse engineered)

---

__Enjoying this integration?__ ⭐ Star the repo and share with other eBike enthusiasts!

[philcoffee]: https://img.buymeacoffee.com/button-api%2F%3Ftext%3DBuy%20Phil%20a%20coffee%26%E2%98%95%26slug%3Dphilbarker%26button_colour%3DFFDD00%26font_colour%3D000000%26font_family%3DLato%26outline_colour%3D000000%26coffee_colour%3Dffffff

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=ccc

[ghs]: https://github.com/sponsors/marq24
[ghsbadge]: https://img.shields.io/github/sponsors/marq24?style=for-the-badge&logo=github&logoColor=ccc&link=https%3A%2F%2Fgithub.com%2Fsponsors%2Fmarq24&label=Sponsors

[buymecoffee]: https://www.buymeacoffee.com/marquardt24
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a-coffee-blue.svg?style=for-the-badge&logo=buymeacoffee&logoColor=ccc

[buymecoffee2]: https://buymeacoffee.com/marquardt24/membership
[buymecoffeebadge2]: https://img.shields.io/badge/coffee-subs-blue.svg?style=for-the-badge&logo=buymeacoffee&logoColor=ccc

[paypal]: https://paypal.me/marq24
[paypalbadge]: https://img.shields.io/badge/paypal-me-blue.svg?style=for-the-badge&logo=paypal&logoColor=ccc

[wero]: https://share.weropay.eu/p/1/c/6O371wjUW5
[werobadge]: https://img.shields.io/badge/_wero-me_-blue.svg?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZwogICByb2xlPSJpbWciCiAgIHZpZXdCb3g9IjAgMCA0Mi4wNDY1MDEgNDAuODg2NyIKICAgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIgo+CiAgPGcKICAgICBjbGlwLXBhdGg9InVybCgjY2xpcDApIgogICAgIHRyYW5zZm9ybT0idHJhbnNsYXRlKC01Ny4zODE4KSI+CiAgICA8cGF0aAogICAgICAgZD0ibSA3OC40MDUxLDMwLjM1NzQgYyAwLDAgLTAuMDE4NSwwIC0wLjAyNzgsMCAtNC4zMTg0LDAgLTcuMzQ2MiwtMi41NzY5IC04LjY0NjEsLTUuOTg4NyBIIDk5LjA2OTggQyA5OS4zMDU3LDIzLjA4NDkgOTkuNDI4MywyMS43NzExIDk5LjQyODMsMjAuNDQxIDk5LjQyODMsOS43NTY3MyA5MS43Mzc1LDAuMDEzODc4NyA3OC40MDUxLDAgdiAxMC41MjcgYyA0LjM0MzksMC4wMTE2IDcuMzQxNiwyLjU4MzcgOC42Mjc2LDUuOTg4NyBoIC0yOS4yOTcgYyAtMC4yMzM2LDEuMjgzNyAtMC4zNTM5LDIuNTk3NiAtMC4zNTM5LDMuOTI3NiAwLDEwLjY5MTMgNy43MDAyLDIwLjQ0MzQgMjAuOTk1NSwyMC40NDM0IDAuMDA5MywwIDAuMDE4NSwwIDAuMDI3OCwwIHYgLTEwLjUyNyB6IgogICAgICAgZmlsbD0iI0NDQ0NDQyIvPgogICAgPHBhdGgKICAgICAgIGQ9Im0gNzguMzc3NCw0MC44ODQ0IGMgMC40NTEsMCAwLjg5NTEsLTAuMDEzOSAxLjMzNDYsLTAuMDM0NyAyLjcwMTcsLTAuMTM2NSA1LjE1MzUsLTAuNjgwMSA3LjMzOTMsLTEuNTU2NyAyLjE4NTgsLTAuODc2NyA0LjEwNTcsLTIuMDgxOCA1LjczODcsLTMuNTM5MSAxLjYzMywtMS40NTczIDIuOTgxNSwtMy4xNjQzIDQuMDI3LC01LjA0NDkgMC45NTA2LC0xLjcwOTQgMS42NDQ1LC0zLjU1OTkgMi4wNzk0LC01LjQ5MTMgSCA4Ni42NzIgYyAtMC4yNDk4LDAuNTE1OCAtMC41NDEzLDEuMDA4NSAtMC44NzQ0LDEuNDY4OCAtMC40NTU2LDAuNjI5MSAtMC45ODk5LDEuMjAwNSAtMS41OTYsMS42OTMyIC0wLjYwNiwwLjQ5MjcgLTEuMjg2LDAuOTA5IC0yLjAzNTQsMS4yMzA2IC0wLjc0OTUsMC4zMjE1IC0xLjU2NiwwLjU0ODIgLTIuNDQ5NSwwLjY2MTUgLTAuNDMwMywwLjA1NTUgLTAuODc0NCwwLjA4NzkgLTEuMzM0NywwLjA4NzkgLTIuNzUwMiwwIC00Ljk3NzYsLTEuMDQ3OCAtNi41NjY3LC0yLjY4NzggbCAtNy45NDc2LDcuOTQ3OCBjIDMuNTM2NiwzLjIyOTIgOC40NDI2LDUuMjY0NyAxNC41MTY2LDUuMjY0NyB6IgogICAgICAgZmlsbD0idXJsKCNwYWludDApIgogICAgICAgc3R5bGU9ImZpbGw6dXJsKCNwYWludDApIiAvPgogICAgPHBhdGgKICAgICAgIGQ9Ik0gNzguMzc3NywwIEMgNjcuMTAxNiwwIDU5Ljg1MDIsNy4wMTMzNyA1Ny45MDcyLDE1LjY2OTEgSCA3MC4wOTcgYyAxLjQ1NzIsLTIuOTgxNyA0LjMyNzcsLTUuMTQyMSA4LjI4MDcsLTUuMTQyMSAzLjE1MDMsMCA1LjU5NTIsMS4zNDYyIDcuMTkzNSwzLjM4MTggTCA5My41OTA1LDUuODg5MiBDIDkwLjAwNzYsMi4zMDE1NSA4NC44NTY1LDAuMDAyMzEzMTIgNzguMzc1MywwLjAwMjMxMzEyIFoiCiAgICAgICBmaWxsPSJ1cmwoI3BhaW50MSkiCiAgICAgICBzdHlsZT0iZmlsbDp1cmwoI3BhaW50MSkiIC8+CiAgPC9nPgogIDxkZWZzPgogICAgPGxpbmVhckdyYWRpZW50CiAgICAgICBpZD0icGFpbnQwIgogICAgICAgeDE9IjkyLjc0MzY5OCIKICAgICAgIHkxPSIxOC4wMjYxOTkiCiAgICAgICB4Mj0iNzQuNzU0NTAxIgogICAgICAgeTI9IjQwLjMxMDIiCiAgICAgICBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC4wMiIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIKICAgICAgICAgc3RvcC1vcGFjaXR5PSIwIi8+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC4zOSIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIKICAgICAgICAgc3RvcC1vcGFjaXR5PSIwLjY2Ii8+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC42OCIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudAogICAgICAgaWQ9InBhaW50MSIKICAgICAgIHgxPSI2MS4yNzA0MDEiCiAgICAgICB5MT0iMjMuMDE3Nzk5IgogICAgICAgeDI9Ijc5Ljc1NDUwMSIKICAgICAgIHkyPSI0LjUzNDI5OTkiCiAgICAgICBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC4wMiIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIKICAgICAgICAgc3RvcC1vcGFjaXR5PSIwIi8+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC4zOSIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIKICAgICAgICAgc3RvcC1vcGFjaXR5PSIwLjY2Ii8+CiAgICAgIDxzdG9wCiAgICAgICAgIG9mZnNldD0iMC42OCIKICAgICAgICAgc3RvcC1jb2xvcj0iI0NDQ0NDQyIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxjbGlwUGF0aAogICAgICAgaWQ9ImNsaXAwIj4KICAgICAgPHJlY3QKICAgICAgICAgd2lkdGg9IjE3Ny45MSIKICAgICAgICAgaGVpZ2h0PSI0MSIKICAgICAgICAgZmlsbD0iI2ZmZmZmZiIKICAgICAgICAgeD0iMCIKICAgICAgICAgeT0iMCIgLz4KICAgIDwvY2xpcFBhdGg+CiAgPC9kZWZzPgo8L3N2Zz4=

[revolut]: https://revolut.me/marq24
[revolutbadge]: https://img.shields.io/badge/_revolut-me_-blue.svg?style=for-the-badge&logo=revolut&logoColor=ccc

[hainstall]: https://my.home-assistant.io/redirect/config_flow_start/?domain=bosch_ebike
[hainstallbadge]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.bosch_ebike.total
