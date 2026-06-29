from datetime import datetime, timezone
from typing import Optional

from deepblu_tools import utils
from deepblu_tools.models import deepblu as dm
from deepblu_tools.models import uddf as um


class DeepbluLog:
    def __init__(self, json_log: dict, media: dict):
        self._start_epoch = None
        self.id = "deepblu_divelog_" + json_log.get("_id")
        # Priority: diveDTUTC (corrected UTC) > diveDTRawUTC (raw local-as-epoch)
        dive_date = json_log.get("diveDTUTC") or json_log.get("diveDTRawUTC")
        if dive_date is not None:
            # Use naive datetime (no timezone) to match Subsurface's export format
            utc_dt = datetime.fromtimestamp(dive_date, tz=timezone.utc)
            self.dive_date = utc_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            self.dive_date = None
        self.air_pressure = json_log.get("airPressure", 1000)
        self.water_type = json_log.get("waterType", 0)
        self.notes = json_log.get("notes")
        self.dive_duration = json_log.get("diveDuration")
        self.dive_sample_interval = json_log.get("diveSampleInterval", None)
        self.min_temp = utils.convert_temp(json_log.get("diveMinTemperature", None))
        self.max_depth = utils.get_depth(
            json_log.get("diveMaxDepth", None),
            self.air_pressure,
            self.water_type,
        )
        self.dive_gear = dm.DiveGear(json_log.get("_DiveGear", {}))
        # UDDF scheme prescribes for dive mode (i.e. apnea or scuba) to be
        # included at waypoint level as it is technically possible to change
        # diving mode while diving
        # 'apnoe' is the German keyword used in UDDF < 3.2.2;
        # using this for compatibility reasons
        self.dive_mode = (
            "apnea" if json_log.get("diveType") == "Free" else "opencircuit"
        )
        self.dive_profile = dm.DiveProfile(json_log.get("_diveProfile"), self)
        self.dive_spot = dm.DiveSpot(json_log.get("divespot", {}))
        self.dive_base = self.dive_spot.dive_base
        self.visibility = json_log.get("_DiveCondition", {}).get("visibility", None)
        self.air_temperature = json_log.get("_DiveCondition", {}).get(
            "avgTemperature", None
        )
        if self.air_temperature:
            # For some obscure reason, this is not in decicelsius like elsewhere
            self.air_temperature = utils.convert_temp(self.air_temperature * 10)
        self.average_depth = utils.get_depth(
            json_log.get("_DiveCondition", {}).get("averageDepth", None),
            self.air_pressure,
            self.water_type,
        )
        self.surface_pressure = json_log.get("airPressure", None)
        self.dive_raw_hex = json_log.get("diveRawHEX", None)
        self.is_training_log = json_log.get("isTrainingLog", None)
        self.privacy_setting = json_log.get("privacySetting", None)
        self.source_type = json_log.get("sourceType", None)

        # --- NEW FIELD MAPPINGS ---

        # Group info (dive number within a multi-dive session)
        self.group_index = json_log.get("groupIndex")
        self.group_total = json_log.get("groupTotal")
        # Overall sequential dive number (set later by logbook)
        self.dive_number = None
        # Trip membership reference (set later by logbook)
        self.tripmembership_ref = None

        # Dive purpose(s)
        self.dive_purpose = json_log.get("divePurpose")
        raw_purposes = json_log.get("divePurposes", [])
        self.dive_purposes = raw_purposes if isinstance(raw_purposes, list) else []

        # Entry type (boat / shore / ice)
        self.dive_in_type = json_log.get("diveInType")

        # Weather condition
        self.weather = json_log.get("_DiveCondition", {}).get("weather")

        # Spot features
        raw_features = json_log.get("spotFeatures", [])
        self.spot_features = raw_features if isinstance(raw_features, list) else []

        # --- END NEW FIELD MAPPINGS ---

        self.buddies = []
        for buddy in json_log.get("diveBuddiesObj", {}):
            self.buddies.append(dm.Buddy(buddy))
        # Drafts may use a flat array of buddy user IDs instead
        if not self.buddies:
            raw_dive_buddies = json_log.get("diveBuddies", [])
            if isinstance(raw_dive_buddies, list):
                for buddy_id in raw_dive_buddies:
                    if isinstance(buddy_id, dict):
                        self.buddies.append(dm.Buddy(buddy_id))
                    elif isinstance(buddy_id, str):
                        self.buddies.append(dm.Buddy({"diveBuddyUserId": buddy_id}))

        self.media = []
        for medium in media:
            self.media.append(dm.Medium(medium))

    def to_uddf(self) -> um.DiveType:
        # ----- informationbeforedive -----
        before_dive = um.InformationbeforediveType(
            airtemperature=self.air_temperature,
            datetime=self.dive_date,
            link=[
                um.LinkType(ref=link.id)
                for link in self.buddies + [self.dive_spot]
                if link.id
            ],
        )

        # Surface pressure (atmospheric pressure at dive site)
        if self.surface_pressure is not None:
            before_dive.surfacepressure = float(self.surface_pressure)

        # Overall sequential dive number
        if self.dive_number is not None:
            before_dive.divenumber = self.dive_number

        # Dive number of day (groupIndex / groupTotal)
        if self.group_index is not None:
            before_dive.divenumberofday = self.group_index

        # Dive purpose
        purpose_str = self._resolve_purpose()
        if purpose_str:
            before_dive.purpose = self._map_purpose(purpose_str)

        # Trip membership (set by logbook for date-based grouping)
        if self.tripmembership_ref:
            before_dive.tripmembership = um.LinkType(ref=self.tripmembership_ref)

        # Equipment used (lead weight)
        before_dive.equipmentused = um.InformationbeforediveType.Equipmentused(
            leadquantity=0.0
        )

        # Dive entry type (boat/shore/ice)
        if self.dive_in_type:
            before_dive.platform = self._map_platform(self.dive_in_type)

        # Training log flag -> purpose override
        if self.is_training_log == "y":
            before_dive.purpose = um.InformationbeforediveTypePurpose.LEARNING

        # ----- informationafterdive -----
        notes_para = []
        if self.notes:
            notes_para.append(self.notes)
        if self.weather:
            notes_para.append(f"Weather: {self.weather}")
        if self.privacy_setting:
            notes_para.append(f"Privacy: {self.privacy_setting}")
        if self.source_type:
            notes_para.append(f"Source: {self.source_type}")
        if self.dive_raw_hex:
            notes_para.append(
                f"Raw HEX: {self.dive_raw_hex[:120]}{'...' if len(self.dive_raw_hex) > 120 else ''}"
            )
        for feature in self.spot_features:
            if isinstance(feature, str):
                notes_para.append(f"Spot feature: {feature}")

        notes = um.NotesType(
            para=notes_para if notes_para else [""],
            link=[um.LinkType(ref=m.id) for m in self.media],
        )

        after_dive = um.InformationafterdiveType(
            averagedepth=self.average_depth,
            # UDDF expects diveduration in minutes; Deepblu stores it in seconds
            diveduration=(self.dive_duration / 60.0) if self.dive_duration else None,
            greatestdepth=self.max_depth,
            lowesttemperature=self.min_temp,
            notes=notes,
            visibility=self.visibility,
        )

        # ----- tankdata (only emit when there is actual tank data) -----
        tankdata = []
        if (
            self.dive_gear.start_bar is not None
            or self.dive_gear.end_bar is not None
            or self.dive_gear.tank_volume is not None
        ):
            tankdata = [
                um.TankdataType(
                    tankpressurebegin=self.dive_gear.start_bar,
                    tankpressureend=self.dive_gear.end_bar,
                    tankvolume=self.dive_gear.tank_volume,
                )
            ]

        samples = self.dive_profile.to_uddf()
        # If there is no dive profile (empty samples) but we know the dive mode,
        # generate a single waypoint to carry the divemode so Subsurface
        # can identify freediving vs scuba. Use the actual dive duration and
        # max depth so Subsurface can compute the duration from waypoints.
        if not samples.waypoint and self.dive_mode != "opencircuit":
            wp_depth = self.max_depth if self.max_depth else 0.0
            wp_time = self.dive_duration if self.dive_duration else 0
            samples = um.SamplesType(
                waypoint=[
                    um.WaypointType(
                        depth=wp_depth,
                        divetime=wp_time,
                        temperature=self.min_temp,
                        divemode=um.WaypointType.Divemode(
                            type=getattr(um.DivemodeType, self.dive_mode.upper())
                        ),
                    )
                ]
            )

        return um.DiveType(
            id=self.id,
            informationafterdive=after_dive,
            tankdata=tankdata,
            samples=samples,
            informationbeforedive=before_dive,
        )

    def _resolve_purpose(self) -> Optional[str]:
        """Return the most specific dive purpose string available."""
        if self.dive_purpose:
            return self.dive_purpose
        if self.dive_purposes and len(self.dive_purposes) > 0:
            return self.dive_purposes[0]
        return None

    @staticmethod
    def _map_purpose(
        purpose: str,
    ) -> um.InformationbeforediveTypePurpose:
        mapping = {
            "sightseeing": um.InformationbeforediveTypePurpose.SIGHTSEEING,
            "learning": um.InformationbeforediveTypePurpose.LEARNING,
            "teaching": um.InformationbeforediveTypePurpose.TEACHING,
            "instruction": um.InformationbeforediveTypePurpose.TEACHING,
            "training": um.InformationbeforediveTypePurpose.LEARNING,
            "research": um.InformationbeforediveTypePurpose.RESEARCH,
            "scientific": um.InformationbeforediveTypePurpose.RESEARCH,
            "photography": um.InformationbeforediveTypePurpose.PHOTOGRAPHY_VIDEOGRAPHY,
            "video": um.InformationbeforediveTypePurpose.PHOTOGRAPHY_VIDEOGRAPHY,
            "spearfishing": um.InformationbeforediveTypePurpose.SPEARFISHING,
            "hunting": um.InformationbeforediveTypePurpose.SPEARFISHING,
            "proficiency": um.InformationbeforediveTypePurpose.PROFICIENCY,
            "work": um.InformationbeforediveTypePurpose.WORK,
            "fun": um.InformationbeforediveTypePurpose.OTHER,
            "other": um.InformationbeforediveTypePurpose.OTHER,
        }
        return mapping.get(
            purpose.lower().strip(),
            um.InformationbeforediveTypePurpose.OTHER,
        )

    @staticmethod
    def _map_platform(
        dive_in_type: str,
    ) -> um.InformationbeforediveTypePlatform:
        mapping = {
            "boat": um.InformationbeforediveTypePlatform.SMALL_BOAT,
            "small-boat": um.InformationbeforediveTypePlatform.SMALL_BOAT,
            "charter": um.InformationbeforediveTypePlatform.CHARTER_BOAT,
            "charter-boat": um.InformationbeforediveTypePlatform.CHARTER_BOAT,
            "liveaboard": um.InformationbeforediveTypePlatform.LIVE_ABOARD,
            "live-aboard": um.InformationbeforediveTypePlatform.LIVE_ABOARD,
            "shore": um.InformationbeforediveTypePlatform.BEACH_SHORE,
            "beach": um.InformationbeforediveTypePlatform.BEACH_SHORE,
            "beach-shore": um.InformationbeforediveTypePlatform.BEACH_SHORE,
            "pier": um.InformationbeforediveTypePlatform.PIER,
            "land": um.InformationbeforediveTypePlatform.LANDSIDE,
            "landside": um.InformationbeforediveTypePlatform.LANDSIDE,
            "barge": um.InformationbeforediveTypePlatform.BARGE,
            "ice": um.InformationbeforediveTypePlatform.OTHER,
            "chamber": um.InformationbeforediveTypePlatform.HYPERBARIC_FACILITY,
            "hyperbaric": um.InformationbeforediveTypePlatform.HYPERBARIC_FACILITY,
            "other": um.InformationbeforediveTypePlatform.OTHER,
        }
        return mapping.get(
            dive_in_type.lower().strip(),
            um.InformationbeforediveTypePlatform.OTHER,
        )
