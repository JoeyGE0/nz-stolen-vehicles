# NZ Stolen Vehicles

Home Assistant / HACS integration that downloads the public [NZ Police stolen vehicles list](https://www.police.govt.nz/can-you-help-us/stolen-vehicles) and lets you check a plate from automations.

Use it with Frigate LPR (or any other plate source) to alert when a stolen vehicle shows up on a camera.

## What it does

- Downloads the Police CSV (last 6 months) on a schedule
- Lets you pick one area at setup. **All of New Zealand is the default**
- Exposes `sensor.nz_stolen_vehicles_*` with the vehicle count
- Service `nz_stolen_vehicles.check_plate` returns whether that plate is on the list
- Fires `nz_stolen_vehicles_match` when a check hits

It does **not** scrape the search box. That form is behind reCAPTCHA. The download endpoint is public:

`https://www.police.govt.nz/stolenwanted/vehicles/csv/download?all=true&gzip=false`

## Install

1. HACS → Custom repositories → add `https://github.com/JoeyGE0/nz-stolen-vehicles` as **Integration**
2. Download **NZ Stolen Vehicles**
3. Restart Home Assistant
4. Settings → Devices & services → Add integration → **NZ Stolen Vehicles**
5. Leave area on **All of New Zealand** unless you only want one district

## Entities

| Entity | State | Notes |
| --- | --- | --- |
| Stolen vehicles sensor | count | Attributes: `area`, `newest_date_stolen`, `last_refresh`. The full plate list is **not** on the entity (too big for recorder). |

## Service: `nz_stolen_vehicles.check_plate`

```yaml
action: nz_stolen_vehicles.check_plate
data:
  plate: MSS927
response_variable: stolen_check
```

Response:

```yaml
stolen: true
plate: MSS927
normalized_plate: MSS927
match_count: 1
matches:
  - plate: MSS927
    colour: Blue
    make: Mazda
    model: DEMIO
    year: "2015"
    type: Hatchback
    date_stolen: "2026-09-01"
    district: Wellington
```

Plates are compared uppercase with spaces and dashes stripped.

## Driveway automation (Frigate LPR)

Point this at whatever topic/event already gives you a recognised plate. Then call the service:

```yaml
alias: Stolen vehicle on driveway
triggers:
  - trigger: mqtt
    topic: frigate/tracked_object_update
conditions:
  - condition: template
    value_template: "{{ trigger.payload_json.license_plate is defined }}"
actions:
  - action: nz_stolen_vehicles.check_plate
    data:
      plate: "{{ trigger.payload_json.license_plate }}"
    response_variable: stolen_check
  - if:
      - condition: template
        value_template: "{{ stolen_check.stolen }}"
    then:
      - action: notify.mobile_app_your_phone
        data:
          title: Stolen vehicle
          message: >-
            {{ stolen_check.normalized_plate }}
            {{ stolen_check.matches[0].colour }}
            {{ stolen_check.matches[0].make }}
            {{ stolen_check.matches[0].model }}
            ({{ stolen_check.matches[0].district }})
```

You can also trigger on the event the service fires:

```yaml
triggers:
  - trigger: event
    event_type: nz_stolen_vehicles_match
```

If a plate is stolen **and still being driven**, call **111**. Abandoned only → **105**. Do not chase it.

## Police data limits

Police say the file is a snapshot. It does **not** include vehicles that are:

- stolen but not reported
- reported but not on the database yet
- reported stolen and already recovered
- not registered with NZTA for use in New Zealand

Lost/stolen plates are not in this list. Refresh default is 6 hours.

## Areas

All of New Zealand, Auckland City, Bay of Plenty, Canterbury, Central, Counties/Manukau, Eastern, Northland, Southern, Tasman, Waikato, Waitematā, Wellington.
