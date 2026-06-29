import hashlib

from deepblu_tools.models import deepblu as dm
from deepblu_tools.models import uddf as um


# All gear, including list of equipment
class DiveGear:
    def __init__(self, dive_gear: dict):
        self.gas_definition = dm.GasDefinition(dive_gear.get("airMix"))
        self.tank_volume = dive_gear.get("airTank", {}).get("volume")
        if dive_gear.get("endmar"):
            self.end_bar = int(dive_gear.get("endmar")) * 10**5
        else:
            self.end_bar = None
        if dive_gear.get("startedmar"):
            self.start_bar = int(dive_gear.get("startedmar")) * 10**5
        else:
            self.start_bar = None

        self.equipment = []  # List of Equipment objects for regular gear
        self.camera_type = None  # um.CameraType if camera data exists
        self.suit_type = None  # um.SuitType if suit data exists

        # Dive computers
        for dc in dive_gear.get("diveComputer", {}):
            self.equipment.append(dm.Equipment("divecomputer", dc))

        # Regulator (first stage + second stage)
        reg = dive_gear.get("regulator", {})
        if isinstance(reg, dict):
            if reg.get("firstStage"):
                self.equipment.append(dm.Equipment("regulator", reg["firstStage"]))
            if reg.get("secondStage"):
                self.equipment.append(dm.Equipment("regulator", reg["secondStage"]))

        # BCD
        if dive_gear.get("BCD"):
            self.equipment.append(
                dm.Equipment("buoyancycontroldevice", dive_gear["BCD"])
            )

        # Fins
        if dive_gear.get("fins"):
            self.equipment.append(dm.Equipment("fins", dive_gear["fins"]))

        # Light / Torch
        if dive_gear.get("lightTorch"):
            self.equipment.append(dm.Equipment("light", dive_gear["lightTorch"]))

        # Camera system (needs special CameraType in UDDF)
        self._build_camera(dive_gear)

        # Suit (needs special SuitType in UDDF)
        self._build_suit(dive_gear)

    def _build_camera(self, dive_gear: dict):
        body = []
        housing = []
        lens = []
        flash = []

        if dive_gear.get("camera"):
            body.append(self._make_camera_piece("camera_body", dive_gear["camera"]))
        if dive_gear.get("cameraHousing"):
            housing.append(
                self._make_camera_piece("camera_housing", dive_gear["cameraHousing"])
            )
        if dive_gear.get("cameraLens"):
            lens.append(self._make_camera_piece("camera_lens", dive_gear["cameraLens"]))
        if dive_gear.get("cameraLight"):
            flash.append(
                self._make_camera_piece("camera_flash", dive_gear["cameraLight"])
            )
        if dive_gear.get("cameraStrobe"):
            flash.append(
                self._make_camera_piece("camera_strobe", dive_gear["cameraStrobe"])
            )

        if body or housing or lens or flash:
            id_input = "".join(str(p.name) for p in body + housing + lens + flash)
            cam_id = "cam_" + hashlib.sha1(id_input.encode("UTF-8")).hexdigest()[0:8]
            self.camera_type = um.CameraType(
                id=cam_id,
                body=body,
                lens=lens,
                housing=housing,
                flash=flash,
            )

    @staticmethod
    def _make_camera_piece(kind: str, name: str) -> um.EquipmentPieceType:
        return um.EquipmentPieceType(id=kind, name=name)

    def _build_suit(self, dive_gear: dict):
        suit_str = dive_gear.get("suitType")
        if not suit_str:
            return
        suit_enum = self._map_suit_type(suit_str)
        self.suit_type = um.SuitType(
            id="suit",
            name=suit_str,
            suittype=suit_enum,
        )

    @staticmethod
    def _map_suit_type(suit_str: str) -> um.SuitTypeSuittype:
        mapping = {
            "dive-skin": um.SuitTypeSuittype.DIVE_SKIN,
            "dive skin": um.SuitTypeSuittype.DIVE_SKIN,
            "diveskin": um.SuitTypeSuittype.DIVE_SKIN,
            "wet-suit": um.SuitTypeSuittype.WET_SUIT,
            "wet suit": um.SuitTypeSuittype.WET_SUIT,
            "wetsuit": um.SuitTypeSuittype.WET_SUIT,
            "dry-suit": um.SuitTypeSuittype.DRY_SUIT,
            "dry suit": um.SuitTypeSuittype.DRY_SUIT,
            "dry": um.SuitTypeSuittype.DRY_SUIT,
            "hot-water": um.SuitTypeSuittype.HOT_WATER_SUIT,
            "hot water": um.SuitTypeSuittype.HOT_WATER_SUIT,
        }
        lower = suit_str.lower().strip()
        return mapping.get(lower, um.SuitTypeSuittype.OTHER)
