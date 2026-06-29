from deepblu_tools import utils
from deepblu_tools.models import uddf as um


# wayPoint contains depth, temperature and time
# think of it as a dive computer sample point
# 'parent' refers to diveProfile; 'root' to DeepbluLog
class WayPoint:
    def __init__(self, way_point, root, parent):
        # convert from millibar to water depth
        air_pressure = root.air_pressure
        water_type = root.water_type
        depth = utils.get_depth(way_point.get("pressure"), air_pressure, water_type)

        # A quirk of Deepblu is that, for some logs, it saves the dive time of waypoints
        # in Unix epoch time. This is why we keep track of the first waypoint time
        # and subtract it later from each following waypoint's time
        raw_time = way_point.get("time")
        if root._start_epoch is None:
            root._start_epoch = raw_time if raw_time is not None else 0
        if raw_time is not None:
            parent.time = raw_time
        else:
            # If no time is set, use the sample interval (default 20 s)
            interval = root.dive_sample_interval if root.dive_sample_interval else 20
            parent.time = parent.time + interval
        parent.time -= root._start_epoch  # subtract 0 or unix time from each waypoint

        self.depth = depth
        self.time = parent.time
        self.dive_mode = (
            root.dive_mode
        )  # 'apnoe' for freediving; 'opencircuit' for scuba
        self.temp = utils.convert_temp(
            way_point.get("temperature")
        )  # convert to Kelvin

    def to_uddf(self):
        return um.WaypointType(
            depth=self.depth,
            divetime=self.time,
            temperature=self.temp,
            divemode=um.WaypointType.Divemode(
                type=getattr(um.DivemodeType, self.dive_mode.upper())
            ),
        )
