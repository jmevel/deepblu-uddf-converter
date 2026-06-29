from typing import Optional

from deepblu_tools.models import deepblu as dm
from deepblu_tools.models import uddf as um


# A dive location
class DiveSpot:
    def __init__(self, divespot: dict):
        try:
            self.id = "deepblu_spot_" + divespot.get("_id")
        except TypeError:
            self.id = None

        self.name = divespot.get("divespot")
        self.lat = divespot.get("gpsLocation", {}).get("lat")
        self.lon = divespot.get("gpsLocation", {}).get("lng")
        self.country = divespot.get("country")
        self.region = divespot.get("region")
        self.continent = divespot.get("continent")
        self.timezone_offset = divespot.get("timezone", {}).get("rawOffset")
        self.timezone_id = divespot.get("timezone", {}).get("timeZoneId")
        self.spottype = divespot.get("spottype")
        self.rating_avg = divespot.get("ratingAvg")
        self.features = divespot.get("features", [])
        self.local_region = divespot.get("localRegion")
        self.local_site = divespot.get("localSite")
        self.local_spot = divespot.get("localSpot")
        self.dive_base = dm.DiveBase(divespot.get("divesite", ""))

    def to_uddf(self) -> um.SiteType:
        address = None
        if self.country or self.region:
            address = um.AddressType(
                country=self.country,
                province=self.region,
            )

        # Use continent as city hint if available
        if self.continent and address is not None:
            address.city = self.continent

        geog = um.GeographyType(
            latitude=self.lat,
            longitude=self.lon,
            location=self.name,
            address=address,
            timezone=self.timezone_offset,
        )

        environment = self._map_environment(self.spottype)

        rating = None
        if self.rating_avg is not None:
            rating = um.RatingType(ratingvalue=int(round(self.rating_avg)))

        # Build notes with local names and features
        notes_para = []
        if self.local_region or self.local_site or self.local_spot:
            parts = []
            if self.local_spot:
                parts.append(f"local spot: {self.local_spot}")
            if self.local_site:
                parts.append(f"local site: {self.local_site}")
            if self.local_region:
                parts.append(f"local region: {self.local_region}")
            notes_para.append("; ".join(parts))
        if self.timezone_id:
            notes_para.append(f"Timezone: {self.timezone_id}")
        for feature in self.features:
            if isinstance(feature, str):
                notes_para.append(f"Feature: {feature}")

        notes = None
        if notes_para:
            notes = um.NotesType(para=notes_para)

        # Add aliasname for local spot names
        alias_names = []
        if self.local_spot and self.local_spot != self.name:
            alias_names.append(self.local_spot)
        if self.local_site:
            alias_names.append(self.local_site)

        return um.SiteType(
            id=self.id,
            name=self.name,
            aliasname=alias_names,
            geography=geog,
            environment=environment,
            rating=[rating] if rating else [],
            notes=notes,
        )

    @staticmethod
    def _map_environment(
        spottype: str,
    ) -> Optional[um.SiteTypeEnvironment]:
        mapping = {
            "ocean": um.SiteTypeEnvironment.OCEAN_SEA,
            "sea": um.SiteTypeEnvironment.OCEAN_SEA,
            "lake": um.SiteTypeEnvironment.LAKE_QUARRY,
            "quarry": um.SiteTypeEnvironment.LAKE_QUARRY,
            "river": um.SiteTypeEnvironment.RIVER_SPRING,
            "spring": um.SiteTypeEnvironment.RIVER_SPRING,
            "cave": um.SiteTypeEnvironment.CAVE_CAVERN,
            "cavern": um.SiteTypeEnvironment.CAVE_CAVERN,
            "pool": um.SiteTypeEnvironment.POOL,
            "ice": um.SiteTypeEnvironment.UNDER_ICE,
            "chamber": um.SiteTypeEnvironment.HYPERBARIC_CHAMBER,
        }
        if not spottype:
            return None
        return mapping.get(spottype.lower(), um.SiteTypeEnvironment.OTHER)
