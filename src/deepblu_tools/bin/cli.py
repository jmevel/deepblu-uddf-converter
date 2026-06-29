#! /usr/bin/env python3

###
# Deepblu Backup Tool
# by Sander Van de Moortel
#
# https://github.com/bluppfisk/deepblu-tools
#
# Converts Deepblu JSON exports to UDDF format
# See http://uddf.org for more information on the format
#

import json
import sys
from datetime import datetime, timezone

import click
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from deepblu_tools.models import deepblu as dm

PUBLISHED_FIELDS = {
    "_id": None,
    "diveDTRawUTC": None,
    "diveDTUTC": None,
    "airPressure": 1000,
    "waterType": 0,
    "notes": None,
    "diveDuration": None,
    "diveMinTemperature": None,
    "diveMaxDepth": None,
    "_DiveGear": {},
    "_diveProfile": [],
    "divespot": {},
    "_DiveCondition": {},
    "diveBuddiesObj": {},
    "diveBuddies": [],
    "groupIndex": None,
    "groupTotal": None,
    "divePurpose": None,
    "divePurposes": [],
    "diveInType": None,
    "spotFeatures": [],
    "diveRawHEX": None,
    "isTrainingLog": None,
    "privacySetting": None,
    "sourceType": None,
    "diveSampleInterval": None,
    "macAddress": None,
    "diveType": None,
}


def normalize_dive_log(raw: dict) -> dict:
    """Map a raw dive log (published or draft) to the expected published format."""
    normalized = {}
    for field, default in PUBLISHED_FIELDS.items():
        normalized[field] = raw.get(field, default)

    # Priority for dive timestamp:
    # 1. diveDTUTC - corrected UTC time (available for published dives & some old drafts)
    # 2. createDTUTC - creation/upload time (most reliable for modern drafts where
    #    the dive computer's internal clock was wrong – e.g. all June 2022 freedives
    #    have diveDTRawUTC stuck in Sept 2021 while createDTUTC has the real date)
    # 3. diveDTRawUTC - raw computer time stored as epoch
    # 4. diveDTRaw - string format "year,month,day,hour,minute,second" (last resort)
    correct_utc = raw.get("diveDTUTC")
    if correct_utc is not None:
        normalized["diveDTRawUTC"] = correct_utc
        return normalized

    # For drafts without diveDTUTC: prefer createDTUTC (upload/sync time)
    # over diveDTRawUTC and diveDTRaw because the computer's raw timestamps
    # may be stale/wrong (common with Deepblu freediving logs).
    create_utc = raw.get("createDTUTC")
    if create_utc is not None:
        normalized["diveDTRawUTC"] = create_utc
        return normalized

    # Fallback: parse diveDTRaw string (format: "year,month,day,hour,minute,second")
    if normalized["diveDTRawUTC"] is None:
        dive_dt_raw = raw.get("diveDTRaw")
        if dive_dt_raw and isinstance(dive_dt_raw, str):
            try:
                parts = [int(p) for p in dive_dt_raw.split(",")]
                if len(parts) >= 6:
                    dt = datetime(
                        parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
                    )
                    normalized["diveDTRawUTC"] = int(
                        dt.replace(tzinfo=timezone.utc).timestamp()
                    )
            except (ValueError, IndexError):
                pass

    return normalized


def normalize_post(post: dict) -> dict:
    """Ensure a post dict has a non-None 'diveLog' and a 'medias' key.

    Published posts come in as {"diveLog": {...}, "medias": [...]}.
    Draft posts come in as raw dive log objects without the wrapper.
    """
    if isinstance(post, dict) and post.get("diveLog") is not None:
        return post
    dive_log = normalize_dive_log(post)
    return {"diveLog": dive_log, "medias": {}}


def load_posts_from_file(infile: str) -> list:
    try:
        with open(infile, "r") as fp:
            data = json.load(fp)
    except Exception as e:
        raise click.ClickException(f"Could not load infile: {e}")

    # If the file is already a flat list of posts, use it directly
    if isinstance(data, list):
        raw_posts = data
    # Otherwise, try to extract posts from the Deepblu API response format
    # {"result": {"posts": [...], ...}}
    elif isinstance(data, dict):
        result = data.get("result", {})
        if "posts" in result:
            raw_posts = result["posts"]
        elif "logs" in result:
            raw_posts = result["logs"]
        else:
            # As a fallback, find the first list-valued key
            for key, value in data.items():
                if isinstance(value, list):
                    raw_posts = value
                    break
            else:
                raise click.ClickException(
                    "Could not find a list of posts in the JSON file. "
                    "The file should contain a JSON array of posts, "
                    "or a Deepblu API response with a 'result.posts' key."
                )
    else:
        raise click.ClickException(
            f"Unexpected JSON type: {type(data).__name__}. "
            "Expected a JSON array or object."
        )

    return [normalize_post(p) for p in raw_posts if isinstance(p, dict)]


@click.command()
@click.option(
    "-f",
    "--infile",
    help="JSON file containing the Deepblu dive data",
    required=True,
)
@click.option(
    "-m", "--max-logs", help="Maximum number of logs to parse", required=False, type=int
)
@click.option("-o", "--outfile", help="Write UDDF output to this file", type=str)
def main(
    infile: str,
    max_logs: int,
    outfile: str,
):
    posts = load_posts_from_file(infile)

    if not posts:
        raise click.ClickException("No posts found in the provided file")

    deepblu_user = dm.DeepbluUser()
    logbook = dm.DeepbluLogBook(posts, deepblu_user, max_posts=max_logs)
    uddf = logbook.to_uddf()
    config = SerializerConfig(pretty_print=True)

    try:
        fp = sys.stdout
        if outfile:
            fp = open(outfile, "w+")

        raw_xml = XmlSerializer(config=config).render(
            uddf, ns_map={None: "http://www.streit.cc/uddf/3.2/"}
        )
        # Strip the default namespace declaration so that Subsurface's UDDF
        # XSLT can locate elements (e.g. samples/waypoint/divemode/@type)
        # which lack namespace-prefixed alternatives in the XSLT.
        raw_xml = raw_xml.replace(' xmlns="http://www.streit.cc/uddf/3.2/"', "")
        fp.write(raw_xml)
    except BrokenPipeError:
        pass
    except Exception as e:
        raise click.ClickException(f"Could not write to file: {e}")


if __name__ == "__main__":
    main()
