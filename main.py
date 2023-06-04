#!/usr/bin/env python
# coding: utf-8
import configparser
import logging
import uuid
import sys
import asyncio
import json
import requests
import os
import datetime
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from geopy.distance import geodesic as GD
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse, HTMLResponse
from starlette_wtf import StarletteForm
from wtforms import StringField, EmailField, PasswordField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length
from tplinkcloud import TPLinkDeviceManager
from pydantic import BaseModel

from square.client import Client

chargerOn = False

CONFIG_TYPE = None
PAYMENT_FORM_URL = None
configPresent = True
sched = None
APPLICATION_ID = None
LOCATION_ID = None
ACCESS_TOKEN = None
TPLINK_EMAIL = None
TPLINK_PASSWORD = None
TPLINK_DEVICE_ALIAS = None
device_manager = None
COST_PER_CHARGE = None
dollarstr = None
TIMEOUT = None
EXPECTED_VOLTAGE = None
client = None
location = None
ACCOUNT_CURRENCY = None
ACCOUNT_COUNTRY = None


class SetupForm(StarletteForm):
    app_id = StringField(
        "Square Production Application ID", validators=[DataRequired()]
    )
    loc_id = StringField("Square Production Location ID", validators=[DataRequired()])
    access_token = StringField(
        "Square Production Access Token", validators=[DataRequired()]
    )
    tplink_email = EmailField("TPLink Email Address", validators=[DataRequired()])
    tplink_password = PasswordField("TPLink Password", validators=[DataRequired()])
    tplink_device_alias = StringField(
        "TPLink Device Alias", validators=[DataRequired()]
    )
    cost = IntegerField(
        "Cost Per Charge (in cents, e.g. 100 is $1.00)", validators=[DataRequired()]
    )
    timeout = IntegerField("Charge duration in hours", validators=[DataRequired()])
    expected_voltage = IntegerField(
        "Expected Voltage (e.g. in the USA this should be 120)",
        validators=[DataRequired()],
    )
    submit = SubmitField(label="Submit")


async def toggle_charger():
    global TPLINK_DEVICE_ALIAS
    global device_manager
    global chargerOn
    devices = await device_manager.get_devices()
    fetch_tasks = []
    for device in devices:
        if device.get_alias() == TPLINK_DEVICE_ALIAS:
            await device.toggle()
            if chargerOn:
                chargerOn = False
            else:
                chargerOn = True
    await asyncio.gather(*fetch_tasks)


def toggle_helper():
    asyncio.run(toggle_charger())


async def keep_state():
    global TPLINK_DEVICE_ALIAS
    global device_manager
    global chargerOn
    if TPLINK_DEVICE_ALIAS and device_manager:
        devices = await device_manager.get_devices()
        fetch_tasks = []
        for device in devices:
            if device.get_alias() == TPLINK_DEVICE_ALIAS:
                on = await device.is_on()
                if on and chargerOn == False:
                    await device.power_off()
                if on == False and chargerOn:
                    await device.power_on()
        await asyncio.gather(*fetch_tasks)


def state_helper():
    asyncio.run(keep_state())


state_keeper = BackgroundScheduler(daemon=True)
state_keeper.add_job(state_helper, "interval", seconds=30)
state_keeper.start()


def setupApp():
    # To read your secret credentials
    config = configparser.ConfigParser()
    config.read("config.ini")

    # Set up gloabls
    global sched
    global CONFIG_TYPE
    global PAYMENT_FORM_URL
    global configPresent
    global APPLICATION_ID
    global LOCATION_ID
    global ACCESS_TOKEN
    global TPLINK_EMAIL
    global TPLINK_PASSWORD
    global TPLINK_DEVICE_ALIAS
    global device_manager
    global COST_PER_CHARGE
    global dollarstr
    global TIMEOUT
    global EXPECTED_VOLTAGE
    global client
    global location
    global ACCOUNT_CURRENCY
    global ACCOUNT_COUNTRY

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
        user_agent_detail="ampease-payment",
    )

    locReq = client.locations.retrieve_location(location_id=LOCATION_ID)
    location = locReq.body["location"]
    ACCOUNT_CURRENCY = location["currency"]
    ACCOUNT_COUNTRY = location["country"]
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(toggle_helper, "interval", hours=int(TIMEOUT))


try:
    setupApp()
except Exception as e:
    print(e)
    configPresent = False


async def get_device_location():
    global TPLINK_DEVICE_ALIAS
    devices = await device_manager.get_devices()
    lat = 0
    lon = 0
    for device in devices:

        async def get_info(device):
            data = await device.get_sys_info()
            print(data)
            lat = data["latitude_i"] / 10000
            lon = data["longitude_i"] / 10000
            return (lat, lon)

        if device.get_alias() == TPLINK_DEVICE_ALIAS:
            lat, lon = await get_info(device)
    return (lat, lon)


def schedule_toggle():
    global sched
    asyncio.run(toggle_charger())
    sched.shutdown()


def geofence(distance):
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
    global PAYMENT_FORM_URL
    global APPLICATION_ID
    global LOCATION_ID
    global ACCOUNT_CURRENCY
    global EXPECTED_VOLTAGE
    global dollarstr
    global TIMEOUT
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
        + """V) that has already been activated by paying a small fee to get started.</p>
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
    global PAYMENT_FORM_URL
    global APPLICATION_ID
    global LOCATION_ID
    global ACCOUNT_CURRENCY
    global ACCOUNT_COUNTRY
    global EXPECTED_VOLTAGE
    global dollarstr
    global TIMEOUT
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
@app.post("/", response_class=HTMLResponse)
async def read_root(request: Request):
    global configPresent
    global sched
    clientIP = request.client.host
    setupForm = await SetupForm.from_formdata(request)
    app_id = setupForm.app_id.data
    loc_id = setupForm.loc_id.data
    access_token = setupForm.access_token.data
    tplink_email = setupForm.tplink_email.data
    tplink_password = setupForm.tplink_password.data
    tplink_device_alias = setupForm.tplink_device_alias.data
    cost = setupForm.cost.data
    timeout = setupForm.timeout.data
    expected_voltage = setupForm.expected_voltage.data
    if await setupForm.validate_on_submit() and not configPresent:
        with open("config.ini", "w") as f:
            f.write("[DEFAULT]\n")
            f.write("environment = production\n")
            f.write("tplink_email = " + tplink_email + "\n")
            f.write("tplink_password = " + tplink_password + "\n")
            f.write("tplink_device_alias = " + tplink_device_alias + "\n")
            f.write("cost_per_charge = " + str(cost) + "\n")
            f.write("timeout = " + str(timeout) + "\n")
            f.write("expected_voltage = " + str(expected_voltage) + "\n")
            f.write("\n")
            f.write("[PRODUCTION] \n")
            f.write("square_application_id = " + app_id + "\n")
            f.write("square_access_token = " + access_token + "\n")
            f.write("square_location_id = " + loc_id + "\n")
        configPresent = True
        setupApp()
    elif not configPresent:
        return templates.TemplateResponse(
            "setup.html", {"request": request, "form": setupForm}
        )
    if clientIP != "127.0.0.1":
        url = "http://ip-api.com/json/{}".format(clientIP)
        r = requests.get(url)
        j = json.loads(r.text)
        cliCoords = (j["lat"], j["lon"])
        print(cliCoords)
        coords = await get_device_location()
        print(coords)
        distance = GD(cliCoords, coords).km
        print(distance)
        if distance > 100:
            return geofence(distance)
    if sched.running:
        return activated()
    return generate_index_html()


@app.get("/graphics", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("graphics.html", {"request": request})


@app.post("/process-payment")
def create_payment(payment: Payment):
    global sched
    global COST_PER_CHARGE
    global ACCOUNT_CURRENCY
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
