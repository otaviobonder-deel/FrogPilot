import os
import random

import openpilot.system.sentry as sentry

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.selfdrive.controls.controlsd import Desire
from openpilot.selfdrive.controls.lib.events import EventName, Events

class FrogPilotEvents:
  def __init__(self, FrogPilotPlanner):
    self.params = Params()
    self.params_memory = Params("/dev/shm/params")

    self.events = Events()
    self.frogpilot_planner = FrogPilotPlanner

    self.accel30_played = False
    self.accel35_played = False
    self.accel40_played = False
    self.dejaVu_played = False
    self.fcw_played = False
    self.firefox_played = False
    self.goat_played = False
    self.holiday_theme_played = False
    self.no_entry_alert_played = False
    self.openpilot_crashed_played = False
    self.previous_traffic_mode = False
    self.random_event_played = False
    self.stopped_for_light = False
    self.vCruise69_played = False

    self.frame = 0
    self.max_acceleration = 0
    self.random_event_timer = 0

  def update(self, carState, frogpilotCarControl, frogpilotCarState, modelData, v_cruise, frogpilot_toggles):
    self.events.clear()

    if self.random_event_played:
      self.random_event_timer += DT_MDL
      if self.random_event_timer >= 4:
        self.random_event_played = False
        self.random_event_timer = 0
        self.params_memory.remove("CurrentRandomEvent")

    if self.frogpilot_planner.frogpilot_vcruise.forcing_stop:
      self.events.add(EventName.forcingStop)

    if frogpilot_toggles.green_light_alert and not self.frogpilot_planner.tracking_lead and carState.standstill:
      if not self.frogpilot_planner.model_stopped and self.stopped_for_light:
        self.events.add(EventName.greenLight)
      self.stopped_for_light = self.frogpilot_planner.cem.stop_light_detected
    else:
      self.stopped_for_light = False

    if not self.holiday_theme_played and frogpilot_toggles.current_holiday_theme != 0 and self.frame >= 10:
      self.events.add(EventName.holidayActive)
      self.holiday_theme_played = True

    if self.frogpilot_planner.lead_departing:
      self.events.add(EventName.leadDeparting)

    if not self.openpilot_crashed_played and os.path.isfile(os.path.join(sentry.CRASHES_DIR, 'error.txt')):
      if frogpilot_toggles.random_events:
        self.events.add(EventName.openpilotCrashedRandomEvent)
      else:
        self.events.add(EventName.openpilotCrashed)
      self.openpilot_crashed_played = True

    if not self.random_event_played and frogpilot_toggles.random_events:
      acceleration = carState.aEgo

      if not carState.gasPressed:
        self.max_acceleration = max(acceleration, self.max_acceleration)
      else:
        self.max_acceleration = 0

      if not self.accel30_played and 3.5 > self.max_acceleration >= 3.0 and acceleration < 1.5:
        self.events.add(EventName.accel30)
        self.params_memory.put_int("CurrentRandomEvent", 2)
        self.accel30_played = True
        self.random_event_played = True
        self.max_acceleration = 0

      elif not self.accel35_played and 4.0 > self.max_acceleration >= 3.5 and acceleration < 1.5:
        self.events.add(EventName.accel35)
        self.params_memory.put_int("CurrentRandomEvent", 3)
        self.accel35_played = True
        self.random_event_played = True
        self.max_acceleration = 0

      elif not self.accel40_played and self.max_acceleration >= 4.0 and acceleration < 1.5:
        self.events.add(EventName.accel40)
        self.params_memory.put_int("CurrentRandomEvent", 4)
        self.accel40_played = True
        self.random_event_played = True
        self.max_acceleration = 0

      if not self.dejaVu_played and self.frogpilot_planner.taking_curve_quickly:
        self.events.add(EventName.dejaVuCurve)
        self.params_memory.put_int("CurrentRandomEvent", 5)
        self.dejaVu_played = True
        self.random_event_played = True

      if not self.no_entry_alert_played and frogpilotCarControl.noEntryEventTriggered:
        self.events.add(EventName.hal9000)
        self.no_entry_alert_played = True
        self.random_event_played = True

      if frogpilotCarControl.steerSaturatedEventTriggered:
        event_choices = []
        if not self.firefox_played:
          event_choices.append(1)
        if not self.goat_played:
          event_choices.append(2)

        if event_choices and self.frame % (100 // len(event_choices)) == 0:
          event_choice = random.choice(event_choices)
          if event_choice == 1:
            self.events.add(EventName.firefoxSteerSaturated)
            self.params_memory.put_int("CurrentRandomEvent", 1)
            self.firefox_played = True
          elif event_choice == 2:
            self.events.add(EventName.goatSteerSaturated)
            self.goat_played = True
          self.random_event_played = True

      if not self.vCruise69_played and 70 > v_cruise * (CV.MS_TO_KPH if frogpilot_toggles.is_metric else CV.MS_TO_MPH) >= 69:
        self.events.add(EventName.vCruise69)
        self.vCruise69_played = True
        self.random_event_played = True

      if not self.fcw_played and frogpilotCarControl.fcwEventTriggered:
        self.events.add(EventName.yourFrogTriedToKillMe)
        self.fcw_played = True
        self.random_event_played = True

    if frogpilot_toggles.speed_limit_alert and self.speed_limit_changed:
      self.events.add(EventName.speedLimitChanged)

    if self.frame == 5.5 and self.params.get("NNFFModelName", encoding='utf-8') is not None:
      self.events.add(EventName.torqueNNLoad)

    if frogpilotCarState.trafficModeActive != self.previous_traffic_mode:
      if self.previous_traffic_mode:
        self.events.add(EventName.trafficModeInactive)
      else:
        self.events.add(EventName.trafficModeActive)
      self.previous_traffic_mode = frogpilotCarState.trafficModeActive

    if modelData.meta.turnDirection == Desire.turnLeft:
      self.events.add(EventName.turningLeft)
    elif modelData.meta.turnDirection == Desire.turnRight:
      self.events.add(EventName.turningRight)

    self.frame = round(self.frame + DT_MDL, 2)
