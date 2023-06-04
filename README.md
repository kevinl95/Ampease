# Ampease - A $50 Level 1 EV Charging Station you build at home!

![logo](./static/assets/logo.png)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kevinl95/Ampease)

AmpEase is an open-source Level 1 electric vehicle charger. These are much easier and cheaper to deploy than the level 2 and level 3 chargers you may be familiar with that require more than a regular 120V outlet. You likely have an outlet like this on the exterior of your building, or in a parking lot. They can charge an electric vehicle such that they recover 3-5 miles of range per hour, making them great for stops where they driver will be there for a longer period of time such as offices. shopping centers, and hotels. You can register your new charging station on services like PlugShare, making your business a destination for EV drivers!

AmpEase uses an off-the-shelf smart plug and toggles the power automatically based on if the customer has paid. You plug it in behind a locking outdoor outlet cover. While these plugs often have an external button, our software checks the status of the plug and toggles it on and off to ensure that a user hasn't tampered with the plug to get a free charge or disable charging for a paying customer. The required hardware can be acquired online or at a hardware store. The accounts needed to deploy our open-source software are free.

# What you need

- Any regular outlet at your home or business you want to make an EV charging station
- A Square developer account
- A TPLink outdoor smart plug (model KP401 is known to work)
- A TPLink Kasa account
- A Render.com account
- A locking outlet cover
- A padlock

# Setup Instructions

[Follow our getting started guide here!](https://www.ampease.com/getting-started) This details the software setup and physical assembly of an AmpEase charging station.

## Local setup

For development or local testing, install Python 3.11 then clone this repository and navigate inside. Run these commands:

```
python3 -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Now, open your web browser to http://localhost:8000 and fill in the setup form! Information about what information you need for this form can be found on our [getting started guide](https://www.ampease.com/getting-started) which also has screenshots!