#!/usr/bin/env python
# coding: utf-8
import configparser
import logging
import uuid
import sys
import asyncio
import json
import requests
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from flask import request
from tplinkcloud import TPLinkDeviceManager
from pydantic import BaseModel

from square.client import Client

# To read your secret credentials
config = configparser.ConfigParser()
config.read("config.ini")

# Retrieve credentials based on is_prod
CONFIG_TYPE = config.get("DEFAULT", "environment").upper()
PAYMENT_FORM_URL = (
    "https://web.squarecdn.com/v1/square.js"
    if CONFIG_TYPE == "PRODUCTION"
    else "https://sandbox.web.squarecdn.com/v1/square.js"
)
APPLICATION_ID = config.get(CONFIG_TYPE, "square_application_id")
LOCATION_ID = config.get(CONFIG_TYPE, "square_location_id")
ACCESS_TOKEN = config.get(CONFIG_TYPE, "square_access_token")
TPLINK_EMAIL = config.get("DEFAULT", "tplink_email")
TPLINK_PASSWORD = config.get("DEFAULT", "tplink_password")
TPLINK_DEVICE_ALIAS = config.get("DEFAULT", "tplink_device_alias")
device_manager = TPLinkDeviceManager(TPLINK_EMAIL, TPLINK_PASSWORD)
COST_PER_CHARGE = config.get("DEFAULT", "cost_per_charge")
if not COST_PER_CHARGE.isdigit():
    sys.exit("Cost per hour must be a digit!")
if int(COST_PER_CHARGE) < 100:
    sys.exit("The minimum chargeable amount per hour is one dollar!")
dollarstr = "${:,.2f}".format(int(COST_PER_CHARGE) / 100)
TIMEOUT = config.get("DEFAULT", "timeout")
if not TIMEOUT.isdigit():
    sys.exit("Timeout must be an integer number of hours!")
if int(TIMEOUT) > 24:
    sys.exit("Timeout must be less than one day!")
EXPECTED_VOLTAGE = config.get("DEFAULT", "expected_voltage")
if not EXPECTED_VOLTAGE.isdigit():
    sys.exit("Expected voltage must be an integer!")


client = Client(
    access_token=ACCESS_TOKEN,
    environment=config.get("DEFAULT", "environment"),
    user_agent_detail="sample_app_python_payment",  # Remove or replace this detail when building your own app
)

location = client.locations.retrieve_location(location_id=LOCATION_ID).body["location"]
ACCOUNT_CURRENCY = location["currency"]
ACCOUNT_COUNTRY = location["country"]


async def get_device_location():
    devices = await device_manager.get_devices()
    lat = 0
    lon = 0
    for device in devices:

        async def get_info(device):
            data = await device.get_sys_info()
            lat = data["latitude_i"] / 10000
            lon = data["longitude_i"] / 10000
            return (lat, lon)

        if device.get_alias() == TPLINK_DEVICE_ALIAS:
            lat, lon = await get_info(device)
    return (lat, lon)


async def toggle_charger():
    devices = await device_manager.get_devices()
    fetch_tasks = []
    for device in devices:
        if device.get_alias() == TPLINK_DEVICE_ALIAS:
            await device.toggle()
    await asyncio.gather(*fetch_tasks)


def toggle_helper():
    asyncio.run(toggle_charger())

sched = BackgroundScheduler(daemon=True)
sched.add_job(toggle_helper, "interval", hours=int(TIMEOUT))


def schedule_toggle():
    global sched
    asyncio.run(toggle_charger())
    sched.shutdown()


def geofence():
    html_content = """<!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="x-ua-compatible" content="ie=edge">
        <title>AmpEase</title>
        <link rel="manifest" href="/static/manifest.json">
        <link rel="icon" type="image/x-icon" href="/static/assets/favicon.ico">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        
        <!-- link to the custom styles for Web SDK -->
        <link rel='stylesheet', href='/static/stylesheets/sq-payment.css' />
        <link rel='stylesheet', href='/static/stylesheets/style.css' />
      </head>

      <body>
        <img src="/static/assets/logo.png" alt="AmpEase Logo"> 
        <p class="center">Welcome! You are currently too far away from this charging station. Move to within 100 feet to continue.</p>
        </body>

    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


def activated():
    global sched
    nextTime = None
    for job in sched.get_jobs():
        nextTime = job.next_run_time
    html_content = (
        """<!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="x-ua-compatible" content="ie=edge">
        <title>AmpEase</title>
        <link rel="manifest" href="/static/manifest.json">
        <link rel="icon" type="image/x-icon" href="/static/assets/favicon.ico">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        
        <!-- link to the custom styles for Web SDK -->
        <link rel='stylesheet', href='/static/stylesheets/sq-payment.css' />
        <link rel='stylesheet', href='/static/stylesheets/style.css' />
      </head>

      <body>
        <img src="/static/assets/logo.png" alt="AmpEase Logo"> 
        <h1>Charger is currently activated!</h1>
        <p class="center">Welcome! This is a level 1 EV charging station ("""
        + EXPECTED_VOLTAGE
        + """V) that has already been activated by paying a small fee to get started using the form below.</p>
        <p class="center">Your host has specified that there is a charge of """
        + dollarstr
        + """ to use this charger.</p>
        <p class="center">The charger will be active until """
        + nextTime.strftime("%H:%M")
        + """.</p>
        </body>

    </html>
    """
    )
    return HTMLResponse(content=html_content, status_code=200)


def generate_index_html():
    html_content = (
        """<!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="x-ua-compatible" content="ie=edge">
        <title>AmpEase</title>
        <link rel="manifest" href="/static/manifest.json">
        <link rel="icon" type="image/x-icon" href="/static/assets/favicon.ico">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <!-- link to the Web SDK library -->
        <script type="text/javascript" src="""
        + PAYMENT_FORM_URL
        + """></script>

        <script type="application/javascript">
            window.applicationId = '"""
        + APPLICATION_ID
        + """';
            window.locationId = '"""
        + LOCATION_ID
        + """';
            window.currency = '"""
        + ACCOUNT_CURRENCY
        + """';
            window.country = '"""
        + ACCOUNT_COUNTRY
        + """';
            window.idempotencyKey = '"""
        + str(uuid.uuid4())
        + """';
        </script>

        <!-- link to the custom styles for Web SDK -->
        <link rel='stylesheet', href='/static/stylesheets/sq-payment.css' />
        <link rel='stylesheet', href='/static/stylesheets/style.css' />
      </head>

      <body>
        <img src="/static/assets/logo.png" alt="AmpEase Logo"> 
        <p class="center">Welcome! This is a level 1 EV charging station ("""
        + EXPECTED_VOLTAGE
        + """V) that can be activated by paying a small fee to get started using the form below.</p>
        <p class="center">Your host has specified that there is a charge of """
        + dollarstr
        + """ to use this charger.</p>
        <p class="center">Important! After activation the charger will be on for """
        + str(TIMEOUT)
        + """ hours.</p>
        <form class="payment-form" id="fast-checkout">
          <div class="wrapper">
            <div id="card-container"></div>
            <button id="card-button" type="button">
              Pay with Card
            </button>
            <span id="payment-flow-message">
          </div>
        </form>
        <script type="text/javascript" src="/static/js/sq-card-pay.js"></script>
      </body>

      <!-- link to the local Web SDK initialization -->
      <script type="text/javascript" src="/static/js/sq-payment-flow.js"></script>
    </html>
    """
    )
    return HTMLResponse(content=html_content, status_code=200)


class Payment(BaseModel):
    token: str
    idempotencyKey: str


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    global sched
    clientIP = request.client.host
    if clientIP != "127.0.0.1":
        url = "http://ip-api.com/json/{}".format(clientIP)
        r = requests.get(url)
        j = json.loads(r.text)
        cliCoords = (j["lat"], j["lon"])
        coords = asyncio.run(get_device_location())
        distance = geopy.distance.geodesic(cliCoords, coords).km
        if distance > 0.03:
            return geofence()
    if sched.running:
        return activated()
    return generate_index_html()


@app.get("/graphics", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("graphics.html", {"request": request})


@app.post("/process-payment")
def create_payment(payment: Payment):
    global sched
    logging.info("Creating payment")
    # Charge the customer's card
    create_payment_response = client.payments.create_payment(
        body={
            "source_id": payment.token,
            "idempotency_key": payment.idempotencyKey,
            "amount_money": {
                "amount": int(COST_PER_CHARGE),
                "currency": ACCOUNT_CURRENCY,
            },
        }
    )

    logging.info("Payment created")
    if create_payment_response.is_success():
        # Turn on the charger
        asyncio.run(toggle_charger())
        sched.start()
        return create_payment_response.body
    elif create_payment_response.is_error():
        return create_payment_response
