import hashlib

from deepblu_tools.models import uddf as um


# Every piece of equipment is of a certain type, and has a manufacturer and model
class Equipment:
    def __init__(self, kind: str, brand_model):
        """Create an equipment piece.

        Args:
            kind: UDDF equipment slot name (e.g. "divecomputer", "regulator", "fins").
            brand_model: Either a dict with "brand" and "officialModel" keys,
                         or a plain string (used as both name and model).
        """
        self.type = kind
        if isinstance(brand_model, dict):
            self.brand = brand_model.get("brand")
            self.model = brand_model.get("officialModel")
        else:
            self.brand = None
            self.model = str(brand_model) if brand_model else None
        id_input = str(self.brand or "") + str(self.model or "") + self.type
        try:
            self.id = "eq_" + hashlib.sha1(id_input.encode("UTF-8")).hexdigest()[0:8]
        except TypeError:
            self.id = None

    def to_uddf(self):
        manufacturer = None
        if self.brand:
            manufacturer = um.ManufacturerType(id=self.brand, name=self.brand)
        return um.EquipmentPieceType(
            id=self.id,
            name=self.type,
            manufacturer=manufacturer,
            model=self.model,
        )
