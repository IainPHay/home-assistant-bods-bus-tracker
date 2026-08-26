# BODS Bus Tracker for Home Assistant

[![Version](https://img.shields.io/badge/version-0.3.2-blue.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/releases/tag/v0.3.2)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Validate](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml/badge.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/LICENSE)

A native Home Assistant custom integration for English bus services using the UK Department for Transport **Bus Open Data Service (BODS)**.

It combines BODS live **SIRI-VM vehicle positions** with regional **GTFS timetables** to provide upcoming buses, live/scheduled status, estimated arrival or departure times, delay information, and per-service sensors directly in Home Assistant.

> **Beta software.** Version 0.3.2 has been tested primarily with Arriva North East services around Morpeth/Newcastle. The integration is designed to be generic, but wider testing across operators and BODS regions is still welcome.

> **Important:** BODS does not require operators to publish stop-by-stop predicted arrival times in SIRI-VM. Where no operator prediction is available, this integration estimates delay from live vehicle position and the published timetable. It should be treated as passenger information, not a guaranteed departure time.

## Screenshots

### Multiple stops under one BODS account

![BODS Bus Tracker showing multiple stop subentries](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/main/docs/images/multi-stop.png)

### Example departure card with walking guidance

![Example Home Assistant departure card with walking guidance](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/feature/walk-to-stop/docs/images/departure-card.png)

## Highlights

- Enter your **BODS API key once** and add multiple bus stops beneath the same account.
- Each monitored stop becomes its own Home Assistant device.
- Search stops by **name, ATCO code, or NaPTAN/SMS code** within a selected BODS region.
- Optional automatic region detection when an exact stop code is known.
- Discovers the route/operator combinations that actually call at the selected stop.
- Select only the services you want to monitor.
- Live vehicle positions are matched to the day's GTFS trips.
- Falls back cleanly to the published timetable when a live match is not yet available.
- Distinguishes **early**, **on time**, **late**, and **timetable-only** departures.
- Prevents an early-arriving vehicle at a journey origin from being shown as departing before its published departure time.
- Configurable live polling interval per stop.
- Optional per-stop walking time with **Leave by**, **Leave in** and automation-friendly **Leave now** entities.
- Built-in diagnostics and downloadable Home Assistant diagnostics with API keys redacted.
- Generic stock Home Assistant Markdown dashboard card included.
