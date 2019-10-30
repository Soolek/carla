#!/usr/bin/env python

# Copyright (c) 2019 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
CARLA Dynamic Weather:

Connect to a CARLA Simulator instance and control the weather. Change Sun
position smoothly with time and generate storms occasionally.
"""

import glob
import os
import sys

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

import argparse
import math


def clamp(value, minimum=0.0, maximum=100.0):
    return max(minimum, min(value, maximum))


def trapezoid_flow(value, min_val, max_val):
    # returns height at position (value) of a isosceles trapezoid with
    # bottom base width of (max-min) and upper base width of (max-min)/2
    center = (max_val + min_val) / 2
    spread = (max_val - min_val) / 2
    return clamp(2 * (spread - abs(value - center)) / spread, 0, 1)


class Sun(object):
    def __init__(self, azimuth, altitude):
        self.azimuth = azimuth
        self.altitude = altitude
        self._t = 0.0

    def tick(self, delta_seconds):
        self._t += 0.008 * delta_seconds
        self._t %= 2.0 * math.pi
        self.azimuth += 0.25 * delta_seconds
        self.azimuth %= 360.0
        self.altitude = 35.0 * (math.sin(self._t) + 1.0)

    def __str__(self):
        return 'Sun(%.2f, %.2f)' % (self.azimuth, self.altitude)


class Storm(object):
    def __init__(self, precipitation):
        self.clouds = 0.0
        self.rain = 0.0
        self.puddles = 0.0
        self.wind = 0.0

        self.fog_exp = 0.0
        self.fog_vol = 0.0
        self.snow = 0.0

    def tick(self, delta_seconds):
        delta = delta_seconds % 200
        self.clouds = trapezoid_flow(delta, 30.0, 90.0) + trapezoid_flow(delta, 130.0, 190.0)
        self.rain = trapezoid_flow(delta, 40.0, 80.0)
        self.puddles = trapezoid_flow(delta, 50.0, 100.0)
        self.wind = trapezoid_flow(delta, 20.0, 60.0)

        self.fog_exp = trapezoid_flow(delta, 120.0, 180.0)
        self.fog_vol = trapezoid_flow(delta, 120.0, 180.0)
        self.snow = trapezoid_flow(delta, 140.0, 190.0)

    def __str__(self):
        ret = 'Storm(clouds=%d%%, rain=%d%%, puddles=%d%%, wind=%d%%, ' \
              % (self.clouds, self.rain, self.puddles, self.wind)
        ret += 'fog_exp=%d%%, fog_vol=%d%%, snow=%d%%)' \
               % (self.fog_exp, self.fog_vol, self.snow)
        return ret


class Weather(object):
    def __init__(self, weather):
        self.weather = weather
        self._sun = Sun(weather.sun_azimuth_angle, weather.sun_altitude_angle)
        self._storm = Storm(weather.precipitation)

    def tick(self, delta_seconds):
        self._sun.tick(delta_seconds)
        self._storm.tick(delta_seconds)

        self.weather.sun_azimuth_angle = self._sun.azimuth
        self.weather.sun_altitude_angle = self._sun.altitude

        self.weather.cloudyness = clamp(self._storm.clouds * 90.0, 0.0, 90.0)
        self.weather.precipitation = clamp(self._storm.rain * 80.0, 0.0, 80.0)
        self.weather.precipitation_deposits = clamp(self._storm.puddles * 75.0, 0.0, 75.0)
        self.weather.wind_intensity = clamp(self._storm.wind * 80.0, 0.0, 80.0)
        self.weather.exponential_fog_intensity = clamp(self._storm.fog_exp, 0.0, 1.0)
        self.weather.volumetric_fog_intensity = clamp(self._storm.fog_vol * 0.25, 0.0, 0.25)
        self.weather.snow_intensity = clamp(self._storm.snow * 50.0, 0.0, 50.0)
        self.weather.dirtiness = clamp(self._storm.snow * 10.0, 0.0, 10.0)

    def __str__(self):
        return '%s %s' % (self._sun, self._storm)


def main():
    argparser = argparse.ArgumentParser(
        description=__doc__)
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-s', '--speed',
        metavar='FACTOR',
        default=1.0,
        type=float,
        help='rate at which the weather changes (default: 1.0)')
    args = argparser.parse_args()

    speed_factor = args.speed
    update_freq = 0.1 / speed_factor

    client = carla.Client(args.host, args.port)
    client.set_timeout(2.0)
    world = client.get_world()

    weather = Weather(world.get_weather())

    elapsed_time = 0.0

    while True:
        timestamp = world.wait_for_tick(seconds=30.0).timestamp
        elapsed_time += timestamp.delta_seconds
        if elapsed_time > update_freq:
            weather.tick(speed_factor * elapsed_time)
            world.set_weather(weather.weather)
            sys.stdout.write('\r' + str(weather) + 12 * ' ')
            sys.stdout.flush()
            elapsed_time = 0.0


if __name__ == '__main__':
    main()
