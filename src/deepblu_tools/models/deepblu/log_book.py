import datetime

from deepblu_tools.models import deepblu as dm
from deepblu_tools.models import uddf as um


# Logbook (contains multiple logs, media, divespots,
# gas definitions, buddies, equipment)
class DeepbluLogBook:
    def __init__(self, posts: list, deepblu_user: "dm.DeepbluUser", max_posts: int):
        self.logs = []

        for post in posts:
            if (
                max_posts is not None and len(self.logs) >= max_posts
            ):  # max posts reached; stop appending
                break

            self.logs.append(dm.DeepbluLog(post.get("diveLog"), post.get("medias")))

        self.get_unique_media()
        self.get_unique_dive_bases()
        self.get_unique_dive_spots()
        self.get_unique_gas_definitions()
        self.get_unique_buddies()
        self.get_unique_equipment()
        self.get_unique_cameras()
        self.get_unique_suits()
        self.owner = deepblu_user.to_person_type()
        if self.owner:
            self.owner.equipment = self._build_equipment_type()

    def __len__(self):
        return len(self.logs)

    # Below functions eliminate duplicates from the summaries
    def get_unique_equipment(self):
        self.equipment = []
        for log in self.logs:
            for item in log.dive_gear.equipment:
                if not self.find_attr_by_id("equipment", item.id):
                    self.equipment.append(item)

    def get_unique_cameras(self):
        self.cameras = []
        for log in self.logs:
            cam = log.dive_gear.camera_type
            if cam is not None and not self._find_by_id("cameras", cam.id):
                self.cameras.append(cam)

    def get_unique_suits(self):
        self.suits = []
        for log in self.logs:
            suit = log.dive_gear.suit_type
            if suit is not None and not self._find_by_id("suits", suit.id):
                self.suits.append(suit)

    def get_unique_buddies(self):
        self.buddies = []
        for log in self.logs:
            for buddy in log.buddies:
                if not self.find_attr_by_id("buddies", buddy.id):
                    self.buddies.append(buddy)

    def get_unique_dive_spots(self):
        self.dive_spots = []
        for log in self.logs:
            if not self.find_attr_by_id("dive_spots", log.dive_spot.id):
                self.dive_spots.append(log.dive_spot)

    def get_unique_dive_bases(self):
        self.dive_bases = []
        for log in self.logs:
            if not self.find_attr_by_id("dive_bases", log.dive_base.id):
                self.dive_bases.append(log.dive_base)

    def get_unique_gas_definitions(self):
        self.gas_definitions = []
        for log in self.logs:
            if hasattr(log.dive_gear, "gas_definition"):
                if hasattr(log.dive_gear.gas_definition, "id"):
                    if not self.find_attr_by_id(
                        "gas_definitions", log.dive_gear.gas_definition.id
                    ):
                        self.gas_definitions.append(log.dive_gear.gas_definition)

    def get_unique_media(self):
        self.media = []
        for log in self.logs:
            for medium in log.media:
                if not self.find_attr_by_id("media", medium.id):
                    self.media.append(medium)

    def find_attr_by_id(self, attribute: str, id: str) -> list:
        try:
            return [item for item in getattr(self, attribute) if item.id == id][0]
        except Exception:
            return []

    def _find_by_id(self, attr: str, id: str) -> bool:
        """Check if an item with the given id exists in the attribute list."""
        try:
            items = getattr(self, attr, [])
            return any(item.id == id for item in items)
        except Exception:
            return False

    def _build_equipment_type(self) -> um.EquipmentType:
        """Build a fully categorized UDDF EquipmentType from collected equipment."""
        eq = um.EquipmentType()
        for e in self.equipment:
            piece = e.to_uddf()
            if e.type == "divecomputer":
                eq.divecomputer.append(piece)
            elif e.type == "regulator":
                eq.regulator.append(piece)
            elif e.type == "buoyancycontroldevice":
                eq.buoyancycontroldevice.append(piece)
            elif e.type == "fins":
                eq.fins.append(piece)
            elif e.type == "light":
                eq.light.append(piece)
            else:
                eq.variouspieces.append(piece)
        eq.camera = self.cameras
        eq.suit = self.suits
        return eq

    def _group_logs_by_date(self) -> list:
        """Group logs by date for trip grouping and assign dive numbers."""
        # Sort logs by dive date
        sorted_logs = sorted(
            self.logs,
            key=lambda x: x.dive_date if x.dive_date else "",
        )
        # Assign overall sequential dive number
        for i, log in enumerate(sorted_logs, 1):
            log.dive_number = i
        # Group by date
        groups = []
        current_date = None
        current_group = []
        for log in sorted_logs:
            date_key = log.dive_date[:10] if log.dive_date else "unknown"
            if current_date is not None and date_key != current_date:
                groups.append(current_group)
                current_group = []
            current_date = date_key
            current_group.append(log)
        if current_group:
            groups.append(current_group)
        return groups

    def to_uddf(self) -> um.Uddf:
        uddf = um.Uddf(version="3.2.2")
        uddf.generator = um.Generator(
            name="Deepblu Backup Tool",
            version="2.0.0",
            type=um.GeneratorType.CONVERTER,
            manufacturer=um.ManufacturerType(
                id="bluppfisk",
                name="Sander Van de Moortel",
                contact=um.ContactType(
                    email="sander.vandemoortel@gmail.com",
                    homepage=["https://github.com/bluppfisk/deepblu-tools"],
                ),
            ),
            datetime=datetime.datetime.now().isoformat(),
        )
        uddf.divesite = um.Divesite(
            site=[s.to_uddf() for s in self.dive_spots],
            divebase=[b.to_uddf() for b in self.dive_bases],
        )

        # Group logs by date and create repetition groups
        groups = self._group_logs_by_date()
        repetition_groups = []
        for i, logs_in_group in enumerate(groups):
            trip_ref = f"trip_{i}"
            group_id = f"group_{i}"
            for log in logs_in_group:
                log.tripmembership_ref = trip_ref
            repetition_groups.append(
                um.RepetitiongroupType(
                    id=group_id,
                    dive=[d.to_uddf() for d in logs_in_group],
                )
            )
        uddf.profiledata = um.Profiledata(repetitiongroup=repetition_groups)

        uddf.gasdefinitions = um.Gasdefinitions(
            mix=[g.to_uddf() for g in self.gas_definitions]
        )
        uddf.diver = um.Diver(
            owner=self.owner, buddy=[b.to_uddf() for b in self.buddies]
        )
        uddf.mediadata = um.Mediadata([m.to_uddf() for m in self.media])

        return uddf
