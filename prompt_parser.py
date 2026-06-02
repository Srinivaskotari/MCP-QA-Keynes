def extract_advertiser(prompt):

    advertisers = [

        "LSPACE",

        "Brighton",

        "Mira"
    ]

    for advertiser in advertisers:

        if advertiser.lower() in prompt.lower():

            return advertiser

    return "LSPACE"


def extract_level(prompt):

    prompt = prompt.lower()

    if "source medium" in prompt:

        return "source_medium"

    if "country" in prompt:

        return "country"

    if "device" in prompt:

        return "device"

    if "channel" in prompt:

        return "channel"

    return "source_medium"
