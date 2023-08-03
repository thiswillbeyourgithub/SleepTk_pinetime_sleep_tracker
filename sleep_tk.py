# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SleepTk is a sleep monitor and alarm clock with several dinstinctive features:
    * **Privacy friendly**: your data is not sent to anyone, it is stored directly on the watch (but you can still download it if needed).
    * **Fully open source**
    * **Easy to snooze but hard to stop** You have to swipe several times to make it stop, but can snooze easily.
    * **Optimized for waking up refreshed**: suggests wake up time according to average sleep cycles length.
    * **Gradual wake**: vibrates the watch a tiny bit a few times before the alarm to lift you gently back to consciousness.
    * **Natural wake**: small vibration every 30s until you wake up, instead of a full blown alarm.
    * **Insomnia insights**: if you turn on the screen during the night, SleepTk will tell you how long you slept and in what part of the sleep cycle you are supposed to be. Helpful to figure out insomnia patterns.
    * **Body tracking**: logs your body movement during the night, infers your sleep cycle and write it all down in a `.csv` file.
    * **Heart tracking**: tracks your heart rate throughout the night. *(edit: will be vastly improved when [this issue][https://github.com/daniel-thompson/wasp-os/pull/363#issuecomment-1257055637) gets sorted out)*
    * **Status: fully functional**

Still somewhat under developpement, more information at
[the github](https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os)

Icon kindly designed by [Emanuel Löffler](https://github.com/plan5)

.. figure:: res/screenshots/SleepTkApp.png
    :width: 179

Note: the time might be inaccurate in the simulator (offset by 1 hour passed
midnight or something) but is fine on the watch.
"""

import wasp
import widgets
import shell
import fonts
import math
import ppg
from array import array
from micropython import const
import random

# 1-bit RLE, 64x68, kindly designed by [Emanuel Löffler](https://github.com/plan5), 225 bytes
icon = (
    64, 68,
    b'\xff\x00\x17\x12.\x12.\x12.\x18(\x186\n6\n'
    b':\x04\x02\x028\x04\x02\x028\x04\x04\x044\x04\x04\x04'
    b'4\x04\x04\x044\x04\x04\x046\x02\x04\x082\x02\x04\x08'
    b'2\x02\x04\x082\x02\x04\x08$\x04\n\x02\x06\x06$\x04'
    b'\n\x02\x06\x06$\x04\x08\x06\x04\x06$\x04\x08\x06\x04\x06'
    b'"\x08\x06\x06\x04\x06"\x08\x06\x06\x04\x06"\x08\x06\x06'
    b'\x04\x06"\x08\x06\x06\x04\x06 \n\x06\x06\x04\x06 \x16'
    b'\x04\x06 \x16\x04\x06 \x16\x04\x06\x0b-\x08\x04\x07-'
    b'\x08\x04\x07-\x08\x04\x07-\x08\x04&\x06\x04\x04\x06\x02'
    b'*\x06\x04\x04\x06\x02*\x06\x04\x04\x06\x02*\x06\x04\x04'
    b'\x06\x02*\x06\x04\x06\x04\x02*\x06\x04\x06\x04\x02,\x02'
    b'\x04\x08\x02\x02.\x02\x04\x08\x02\x022\x0e2\x0e2\x0e'
    b'2\x0e.\x11/\x11/\x11/\x11)\x17)\x14\x1a&'
    b'\x1a&\x1a    \x1e"\x1e&\x14,\x14\xff\x00'
    b']'
)

# HARDCODED VARIABLES:
_HEART_RATE_UNKNOWN = const(1) # Use HR of 1 as unknown

# Pages
_PAGE_SLEEPING = const(0)
_PAGE_RINGING = const(1)
_PAGE_SETTINGS1 = const(2)
_PAGE_SETTINGS2 = const(3)

_FONT = fonts.sans18
_FONT_COLOR = const(0xf800)  # red font to reduce eye strain at night
_TIMESTAMP = const(946684800)  # unix time and time used by wasp os don't have the same reference date

## USER SETTINGS #################################
_KILL_BT = const(0)
# set to 0 to disable turning off bluetooth while tracking to save battery
# (you have to reboot the watch to reactivate BT, default: 0)
_STOP_LIMIT = const(10)
# number of times to swipe or press the button to turn off ringing (default: 10)
_SNOOZE_TIME = const(180)
# number of seconds to snooze for (default: 180 i.e. 3 minutes)
_FREQ = const(2)
# get accelerometer data every X seconds, but process and store them only
# every _STORE_FREQ seconds (default: 2)
_HR_FREQ = const(300)
# how many seconds between heart rate data (default: 300, minimum 120)
_STORE_FREQ = const(120)
# process data and store to file every X seconds (recomended: 120)
_BATTERY_THRESHOLD = const(20)
# under X% of battery, stop tracking and only keep the alarm, set at -200
# or lower to disable (default: 30)
_GRADUAL_WAKE = array("f", (0.5, 1, 1.5, 2, 3, 4, 5, 7, 10))
# nb of minutes before alarm to send a tiny vibration, designed to wake
# you more gently. (default: array("f", (0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10)) )
_NATURAL_WAKE_IVL = const(60)
# nb of seconds between vibration when natural wake is on.
_NATURAL_WAKE_RAND = const(30)
# percent of _NATURAL_WAKE_IVL to be randomized. For example 20 means that
# the natural wake will happen at x + x * 20 / 100 * (random.random() - 0.5) * 2
_CYCLE_LENGTH = const(95)
# sleep cycle length in minutes. Currently used only to display best wake up
# time! (default should be: 90 or 100, according to https://sleepyti.me/)
_SLEEP_GOAL_CYCLE = const(5)
# number of sleep cycle you wish to sleep. With _CYCLE_LENGTH this is used
# to suggest best wake up time to user when setting the alarm. (default: 5)
##################################################


# States :
_IDX_STATE_1 = const(0) # App States 1 (8 bit register)
_IDX_STATE_2 = const(1) # App States 2 (8 bit register)
_IDX_STATE_3 = const(2) # App States 3 (8 bit register)
_IDX_ALARM_HOUR = const(3) # Alarm hour (8 bit int)
_IDX_ALARM_MIN = const(4) # Alarm min (8 bit int)
_IDX_LAST_HR = const(5) # Last Heart Rate (8 bit int)
_IDX_LAST_HR_PRINTED = const(6) # Last Heart Rate Printed (8 bit int)

# App States 1 (8 bit register)
_ALARM_ENABLED = const(0x01)
_MOVEMENT_ENABLED = const(0x02)
_HR_ENABLED = const(0x04)
_GRADUAL_WAKE_ENABLED = const(0x08)
_NAT_WAKE_ENABLED = const(0x10)
_CURRENTLY_TRACKING = const(0x20)

# App States 2 (8 bit register)
_PAGE_MASK = const(0x03) # First 2 bits for 4 page states
_PAGE_SHIFT = const(0)
_META_STATE_MASK = const(0x0C) # Second 2 bits for 4 meta states
_META_STATE_SHIFT = const(2) # Shift 2 bits over to read meta state
_NUM_VIB_MASK = const(0xF0) # Last 4 bits for ring counter (max 16)
_NUM_VIB_SHIFT = const(4)

# App States 3 (8 bit register)
_STOP_TRIAL_MASK = const(0x0F) # First 4 bits for stop trial (max 16)
_STOP_TRIAL_SHIFT = const(0)
_PREV_BRIGHT_MASK = const(0x30) # 2 bits for previous brightness level (max 4)
_PREV_BRIGHT_SHIFT = const(4)
_PREV_NOTE_MASK = const(0xC0) # 2 bits for previous notification level (max 4)
_PREV_NOTE_SHIFT = const(6)


class SleepTkApp():
    NAME = 'SleepTk'
    ICON = icon
    VERSION = const(1)

    def __init__(self):
        # simple flag to init the variables only when the app is launched and
        # not as soon as the app is loaded
        self._states = None
        self._WU_t = None

    def _actual_init(self):
        """lots of things to load so only load when the app is started instead
        of directly when the watch is booted."""
        self._states = bytearray(7)

        try:
            shell.mkdir("logs")
        except:  # folder already exists
            pass
        try:
            shell.mkdir("logs/sleep")
        except:  # folder already exists
            pass

        # Init settings
        self._set_bit_flag(_IDX_STATE_1, _ALARM_ENABLED, True)
        self._set_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED, True)
        self._set_bit_flag(_IDX_STATE_1, _HR_ENABLED, True)
        self._set_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED, True)
        self._set_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED, False)
        self._set_bit_flag(_IDX_STATE_1, _CURRENTLY_TRACKING, False)
        self._load_settings()

        self._states[_IDX_LAST_HR] = _HEART_RATE_UNKNOWN
        self._states[_IDX_LAST_HR_PRINTED] = _HEART_RATE_UNKNOWN

        self._hrdata = None
        self._last_HR_date = 0
        self._track_HR_once = 0  # either 0 or the timestamp of when the
        # tracking is supposed to stop
        self._last_touch = int(wasp.watch.rtc.time())
        self._conf_view = None # confirmation view
        self._change_page(_PAGE_SETTINGS1)

        return True

    def _change_page(self, new_page):
        self._clean_up_page(self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT))
        self._set_up_page(new_page)
        self._set_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT, new_page)
        self._draw()

    def _set_up_page(self, page):
        if page == _PAGE_SETTINGS1:
            self._spin_H = widgets.Spinner(30, 70, 0, 23, 2)
            self._spin_H.value = self._states[_IDX_ALARM_HOUR]
            self._spin_M = widgets.Spinner(150, 70, 0, 59, 2, 5)
            self._spin_M.value = self._states[_IDX_ALARM_MIN]
            self._check_al = widgets.Checkbox(x=0, y=40, label="Wake me up")
            self._check_al.state = self._states[_IDX_STATE_1] & _ALARM_ENABLED > 0
        elif page == _PAGE_SETTINGS2:
            self._check_body_tracking = widgets.Checkbox(x=0, y=40, label="Movement track")
            self._check_body_tracking.state = self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED)
            self._btn_HR = widgets.Checkbox(x=0, y=80, label="Heart rate track")
            self._btn_HR.state = self._get_bit_flag(_IDX_STATE_1, _HR_ENABLED)
            self._check_grad = widgets.Checkbox(0, 120, "Gradual wake")
            self._check_grad.state = self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED)
            self._check_natwake = widgets.Checkbox(0, 160, "Natural wake")
            self._check_natwake.state = self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED)
            self._btn_sta = widgets.Button(x=0, y=200, w=240, h=40, label="Start")
        elif page == _PAGE_RINGING:
            self._btn_snooz = widgets.Button(x=0, y=90, w=240, h=120, label="SNOOZE")
        elif page == _PAGE_SLEEPING:
            self._btn_off = widgets.Button(x=0, y=200, w=240, h=40, label="Stop")

    def _clean_up_page(self, page):
        if page == _PAGE_SETTINGS1:
            self._spin_H = None
            self._spin_M = None
            self._check_al = None
            del self._spin_H, self._spin_M, self._check_al
        elif page == _PAGE_SETTINGS2:
            self._check_body_tracking = None
            self._btn_HR = None
            self._check_grad = None
            self._check_natwake = None
            self._btn_sta = None
            del self._check_body_tracking, self._btn_HR, self._check_grad, self._check_natwake, self._btn_sta
        elif page == _PAGE_RINGING:
            self._btn_snooz = None
            del self._btn_snooz
        elif page == _PAGE_SLEEPING:
            self._conf_view = None
            self._btn_off = None
            del self._btn_off

    def foreground(self):
        if not self._states:
            self._actual_init()

        self._draw_system_bar()
        self._conf_view = None
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH |
                                  wasp.EventMask.SWIPE_LEFTRIGHT |
                                  wasp.EventMask.SWIPE_UPDOWN |
                                  wasp.EventMask.BUTTON)
        if self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT) == _PAGE_SLEEPING and self._track_HR_once:
            wasp.system.request_tick(1000 // 8)

    def sleep(self):
        self._set_shifted_int(_IDX_STATE_3, _STOP_TRIAL_MASK, _STOP_TRIAL_SHIFT, 0)
        return True

    def background(self):
        wasp.watch.hrs.disable()
        self._hrdata = None
        # If not tracking de-initialize the app
        if not self._get_bit_flag(_IDX_STATE_1, _CURRENTLY_TRACKING):
            self._clean_up_page(self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT))
            self._buff = None
            del self._buff
            self._states = None

        if not self._WU_t:
            # also removes possible reference to the previous class
            wasp.system.cancel_alarm(None, self._activate_ticks_to_ring)
            wasp.system.cancel_alarm(None, self._start_natural_wake)
            wasp.system.cancel_alarm(None, self._trackOnce)
            wasp.system.cancel_alarm(None, self._tiny_vibration)

        wasp.gc.collect()

    def _try_stop_alarm(self):
        """If button or swipe more than _STOP_LIMIT, then stop ringing"""
        stop_trial = self._get_shifted_int(_IDX_STATE_3, _STOP_TRIAL_MASK, _STOP_TRIAL_SHIFT)
        if stop_trial + 1 >= _STOP_LIMIT:
            # reset app:
            self._set_shifted_int(_IDX_STATE_3, _NUM_VIB_MASK, _NUM_VIB_SHIFT, 0)
            self._stop_tracking()
            self._WU_t = None
            del self._WU_t
            self._change_page(_PAGE_SETTINGS1)
            self.foreground()
        else:
            self._set_shifted_int(_IDX_STATE_3, _STOP_TRIAL_MASK, _STOP_TRIAL_SHIFT, stop_trial + 1)
            draw = wasp.watch.drawable
            draw.set_font(_FONT)
            draw.set_color(_FONT_COLOR)
            draw.string("{} to stop".format(_STOP_LIMIT - stop_trial), 0, 70)

    def press(self, button, state):
        "stop ringing alarm if pressed physical button"
        if not state:
            return
        self._last_touch = int(wasp.watch.rtc.time())
        wasp.watch.display.mute(False)
        wasp.watch.backlight.set(1)
        wasp.watch.display.poweron()
        self._conf_view = None
        page = self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT)
        meta_state = self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT)
        if page == _PAGE_RINGING:
            self._try_stop_alarm()
        elif page == _PAGE_SLEEPING:
            wasp.watch.drawable.set_color(_FONT_COLOR)
            self._draw_system_bar()
            if meta_state == 2:  # if gradual vibration
                self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 3) # also pressed
            else:
                self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 1) # pressed
            # disable pressing to exit, use swipe up instead
            self._draw()
        else:
            wasp.system.navigate(wasp.EventType.HOME)

    def swipe(self, event):
        "navigate between settings page"
        wasp.watch.display.mute(False)
        wasp.watch.backlight.set(1)
        wasp.watch.display.poweron()
        self._last_touch = int(wasp.watch.rtc.time())
        page = self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT)
        if page == _PAGE_SETTINGS1:
            if event[0] == wasp.EventType.LEFT:
                self._change_page(_PAGE_SETTINGS2)
            else:
                return True
        elif page == _PAGE_SETTINGS2:
            if event[0] == wasp.EventType.RIGHT:
                self._change_page(_PAGE_SETTINGS1)
            else:
                return True
        elif page == _PAGE_RINGING:
            self._try_stop_alarm()
        else:
            return True

    def touch(self, event):
        """either start trackign or disable it, draw the screen in all cases"""
        draw = wasp.watch.drawable
        wasp.watch.display.mute(False)
        wasp.watch.backlight.set(1)
        wasp.watch.display.poweron()
        draw.set_font(_FONT)
        self._last_touch = int(wasp.watch.rtc.time())

        page = self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT)
        meta_state = self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT)
        if page == _PAGE_SLEEPING:
            wasp.watch.drawable.set_color(_FONT_COLOR)
        self._draw_system_bar()

        if page == _PAGE_SLEEPING:
            if meta_state == 2:  # if gradual vibration
                self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 3) # also touched
            else:
                self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 1) # touched
            if not self._conf_view:
                if self._btn_off.touch(event):
                    self._conf_view = widgets.ConfirmationView()
                    self._conf_view.draw("Stop tracking?")
                    draw.reset()
                    return
            else:
                if self._conf_view.touch(event):
                    if self._conf_view.value:
                        # reset app:
                        self._stop_tracking()
                        self._change_page(_PAGE_SETTINGS1)
                        self.foreground()
                        return
                    self._conf_view = None
                draw.reset()
        elif page == _PAGE_RINGING:
            if self._btn_snooz.touch(event):
                if self._track_HR_once:  # if currently tracking HR, stop
                    self._track_HR_once = 0
                    self._hrdata = None
                    wasp.watch.hrs.disable()
                wasp.system.cancel_alarm(None, self._start_natural_wake)
                wasp.system.cancel_alarm(None, self._activate_ticks_to_ring)
                self._WU_t = int(wasp.watch.rtc.time()) + _SNOOZE_TIME
                if self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED):
                    wasp.system.set_alarm(self._WU_t, self._start_natural_wake)
                else:
                    wasp.system.set_alarm(self._WU_t, self._activate_ticks_to_ring)
                self._change_page(_PAGE_SLEEPING)
                wasp.system.sleep()
                return
        elif page == _PAGE_SETTINGS1:
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED) and (self._spin_H.touch(event) or self._spin_M.touch(event)):
                if self._states[_IDX_ALARM_MIN] == 0 and self._spin_M.value == 55:
                    self._spin_H.value -= 1
                elif self._states[_IDX_ALARM_MIN] == 55 and self._spin_M.value == 0:
                    self._spin_H.value += 1
                if self._spin_H.value >= 24:
                    self._spin_H.value = 0
                elif self._spin_H.value <= -1:
                    self._spin_H.value = 23
                self._states[_IDX_ALARM_MIN] = self._spin_M.value
                self._spin_M.update()
                self._states[_IDX_ALARM_HOUR] = self._spin_H.value
                self._spin_H.update()
                self._draw_duration(draw)
                return
            elif self._check_al.touch(event):
                self._set_bit_flag(_IDX_STATE_1, _ALARM_ENABLED, self._check_al.state)
                self._check_al.update()
                if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                    self._states[_IDX_ALARM_MIN] = self._spin_M.value
                    self._states[_IDX_ALARM_HOUR] = self._spin_H.value
                    self._spin_M.draw()
                    self._spin_H.draw()
                    self._draw_duration(draw)
                else:
                    self._draw()
            return
        elif page == _PAGE_SETTINGS2:
            if self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED):
                if self._btn_HR.touch(event):
                    self._btn_HR.draw()
                    self._set_bit_flag(_IDX_STATE_1, _HR_ENABLED, self._btn_HR.state)
                    return
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                if self._check_grad.touch(event):
                    self._set_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED, self._check_grad.state)
                    self._check_grad.draw()
                    return
                elif self._check_natwake.touch(event):
                    self._set_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED, self._check_natwake.state)
                    self._check_natwake.draw()
                    return
            if self._btn_sta.touch(event):
                draw.fill()
                draw.string("Loading", 0, 100)
                self._start_tracking()
            elif self._check_body_tracking.touch(event):
                self._set_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED, self._check_body_tracking.state)
                self._check_body_tracking.draw()
                if not self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED):
                    self._set_bit_flag(_IDX_STATE_1, _HR_ENABLED, False)
        self._draw()

    def _draw_duration(self, draw):
        """draws the part of the screen that displays duration as it is
        used both when setting the alarm and throughout the night
        """
        draw.set_font(_FONT)

        page = self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT)
        if page == _PAGE_SETTINGS1:
            duration = (self._read_time(self._states[_IDX_ALARM_HOUR], self._states[_IDX_ALARM_MIN]) - wasp.watch.rtc.time()) / 60
            percent_str = ""
            y = 180
        elif page == _PAGE_SLEEPING:
            draw.set_color(_FONT_COLOR)
            duration = (wasp.watch.rtc.time() - self._track_start_time) / 60
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                percent = (wasp.watch.rtc.time() - self._track_start_time) / (self._WU_t - self._track_start_time)
                percent_str = " ({:02d}%)".format(int(percent * 100))
            else:
                percent_str = ""
            if duration <= 0:  # don't print when not yet asleep
                return
            y = 130

        draw.string("Sleep: {:02d}h{:02d}m{}".format(
            int(duration // 60),
            int(duration % 60),
            percent_str), 0, y)
        cycl = duration / _CYCLE_LENGTH
        cycl_modulo = cycl % 1
        draw.string("so {} cycles   ".format(str(cycl)[0:4]), 0, y + 20)
        if duration > 30 and not self._track_HR_once:
            if cycl_modulo > 0.10 and cycl_modulo < 0.90:
                draw.set_font(_FONT)
                draw.string("Not rested!", 0, y + 40)
            else:
                draw.reset()
                draw.set_font(_FONT)
                draw.string("Well rested", 0, y + 39)
                draw.set_color(_FONT_COLOR)

    def _draw(self):
        """GUI"""
        wasp.watch.display.mute(False)
        wasp.watch.backlight.set(1)
        wasp.watch.display.poweron()
        draw = wasp.watch.drawable
        draw.fill(0)
        self._draw_system_bar()
        draw.set_font(_FONT)
        draw.set_color(_FONT_COLOR)
        page = self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT)
        if page == _PAGE_RINGING:
            ti = wasp.watch.time.localtime(self._WU_t_orig)
            draw.string("WAKE UP - {:02d}:{:02d}".format(ti[3], ti[4]), 0, 50)
            self._btn_snooz.draw()
            draw.reset()
        elif page == _PAGE_SLEEPING:
            self._draw_system_bar()  # updates color
            ti_start = wasp.watch.time.localtime(self._track_start_time)
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                ti_stop = wasp.watch.time.localtime(self._WU_t_orig)
                draw.string('{:02d}:{:02d}  ->|  {:02d}:{:02d}'.format(ti_start[3], ti_start[4], ti_stop[3], ti_stop[4]), 0, 50)
                if self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED) and self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED):
                    draw.string("(Grad&Nat wake)", 0, 70)
                elif self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED):
                    draw.string("(Gradual wake)", 0, 70)
                elif self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED):
                    draw.string("(Natural wake)", 0, 70)
            else:
                draw.string('{:02d}:{:02d}  ->  ??'.format(ti_start[3], ti_start[4]), 0, 50)
            # draw.string("data points: {} / {}".format(str(self._data_point_nb), str(self._data_point_nb * _FREQ // _STORE_FREQ)), 0, 110)
            if self._track_HR_once:
                draw.string("(ongoing)", 0, 170)
            if self._get_bit_flag(_IDX_STATE_1, _HR_ENABLED):
                draw.string("HR:{}".format(self._states[_IDX_LAST_HR_PRINTED]), 160, 170)
            self._btn_off.update(txt=_FONT_COLOR, frame=0, bg=0)
            self._draw_duration(draw)
        elif page == _PAGE_SETTINGS1:
            # reset spinval values between runs
            self._check_al.state = self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED)
            self._check_al.draw()
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                # suggest wake up time, on the basis of desired sleep goal + time to fall asleep
                (H, M) = wasp.watch.rtc.get_localtime()[3:5]
                goal_h = _SLEEP_GOAL_CYCLE * _CYCLE_LENGTH // 60
                goal_m = _SLEEP_GOAL_CYCLE * _CYCLE_LENGTH % 60
                M += goal_m
                while M % 5 != 0:
                    M += 1
                self._states[_IDX_ALARM_HOUR] = ((H + goal_h) % 24 + (M // 60)) % 24
                self._states[_IDX_ALARM_MIN] = M % 60

                self._spin_H.value = self._states[_IDX_ALARM_HOUR]
                self._spin_H.draw()
                self._spin_M.value = self._states[_IDX_ALARM_MIN]
                self._spin_M.draw()
                if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                    self._draw_duration(draw)
        elif page == _PAGE_SETTINGS2:
            self._check_body_tracking.state = self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED)
            self._check_body_tracking.draw()
            if self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED):
                self._btn_HR.state = self._get_bit_flag(_IDX_STATE_1, _HR_ENABLED)
                self._btn_HR.draw()
            if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
                self._check_grad.state = self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED)
                self._check_grad.draw()
                self._check_natwake.state = self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED)
                self._check_natwake.draw()
            self._btn_sta.draw()
        draw.reset()

    def _start_tracking(self):
        self._set_bit_flag(_IDX_STATE_1, _CURRENTLY_TRACKING, True)

        # accel data not yet written to disk:
        self._data_point_nb = 0  # total number of data points so far
        self._latest_save =  -1  # multiple of the saving frequency elapsed since start
        self._last_checkpoint = 0  # to know when to save to file
        self._track_start_time = int(wasp.watch.rtc.time())  # makes output more compact

        self._next_track_time = None
        self._states[_IDX_LAST_HR_PRINTED] = _HEART_RATE_UNKNOWN
        self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 0)
        wasp.watch.accel.reset()

        xyz = wasp.watch.accel.accel_xyz()
        self._accel_memory = array("f",
            (xyz[0], xyz[1], xyz[2]))  # contains previous accelerometer value
        self._buff = array("f", (0, 0, 0)) # contains the sum of diff between each accel recordings and the previous recording, along each axis

        # if enabled, add alarm to log accel data in _FREQ seconds
        if self._get_bit_flag(_IDX_STATE_1, _MOVEMENT_ENABLED):
            # create one file per recording session:
            self.filep = "logs/sleep/{}_{}_{}.csv".format(str(self._track_start_time + _TIMESTAMP), _STORE_FREQ, self.VERSION)
            with open(self.filep, "wb") as f:
                f.write("Timestamp,Motion,BPM,Meta".encode("ascii"))
            self._next_track_time = wasp.watch.rtc.time() + _FREQ
            wasp.system.set_alarm(self._next_track_time, self._trackOnce)
        else:
            self._next_track_time = None

        if (self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED) or self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED)) and not self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
            # fix incompatible settings
            self._set_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED, False)
            self._set_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED, False)

        # setting up alarm
        if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED):
            self._old_notification_level = wasp.system.notify_level
            self._WU_t = self._read_time(self._states[_IDX_ALARM_HOUR], self._states[_IDX_ALARM_MIN])
            self._WU_t_orig = self._WU_t
            if self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED):
                wasp.system.set_alarm(self._WU_t, self._start_natural_wake)
            else:
                wasp.system.set_alarm(self._WU_t, self._activate_ticks_to_ring)

            # also set alarm to vibrate a tiny bit before wake up time
            # to wake up gradually
            if self._get_bit_flag(_IDX_STATE_1, _GRADUAL_WAKE_ENABLED):
                for t in _GRADUAL_WAKE:
                    wasp.system.set_alarm(self._WU_t - int(t*60), self._tiny_vibration)
        else:
            self._WU_t = 0  # this is just to avoid the app overwriting itself when going in the background

        # reduce brightness
        self._set_shifted_int(_IDX_STATE_3, _PREV_BRIGHT_MASK, _PREV_BRIGHT_SHIFT, wasp.system.brightness)
        wasp.system.brightness = 1

        # don't track heart rate right away, wait a few seconds
        if self._get_bit_flag(_IDX_STATE_1, _HR_ENABLED):
            self._last_HR_date = int(wasp.watch.rtc.time()) + 10
        wasp.system.notify_level = 1  # silent notifications

        # kill bluetooth
        if _KILL_BT:
            import ble
            if ble.enabled():
                ble.disable()

        self._change_page(_PAGE_SLEEPING)
        self._set_shifted_int(_IDX_STATE_3, _STOP_TRIAL_MASK, _STOP_TRIAL_SHIFT, 0)

        # save settings as future defaults
        self._save_settings()

    def _read_time(self, HH, MM):
        "convert time from spinners to seconds"
        (Y, Mo, d, h, m) = wasp.watch.rtc.get_localtime()[0:5]
        HH = self._states[_IDX_ALARM_HOUR]
        MM = self._states[_IDX_ALARM_MIN]
        if HH < h or (HH == h and MM <= m):
            d += 1
        return wasp.watch.time.mktime((Y, Mo, d, HH, MM, 0, 0, 0, 0))

    def _stop_tracking(self, keep_main_alarm=False):
        """called by touching "STOP TRACKING" or when battery is low"""
        self._set_bit_flag(_IDX_STATE_1, _CURRENTLY_TRACKING, False)
        if self._next_track_time:
            wasp.system.cancel_alarm(None, self._trackOnce)
        if self._get_bit_flag(_IDX_STATE_1, _ALARM_ENABLED) and not keep_main_alarm:
            # to keep the alarm when stopping because of low battery
            wasp.system.cancel_alarm(None, self._start_natural_wake)
            wasp.system.cancel_alarm(None, self._activate_ticks_to_ring)
            wasp.system.cancel_alarm(None, self._tiny_vibration)
        wasp.watch.hrs.disable()
        self._periodicSave()

        # Clean up vars only used while tracking
        self._buff = None
        self._accel_memory = None
        self._data_point_nb = None
        self._latest_save =  None
        self._last_checkpoint = None
        self._track_start_time = None
        self._next_track_time = None
        del self._buff, self._accel_memory, self._data_point_nb, self._latest_save, self._last_checkpoint, self._track_start_time, self._next_track_time

        #self._change_page(_PAGE_SETTINGS1)

        wasp.gc.collect()

    def _trackOnce(self):
        """get one data point of accelerometer every _FREQ seconds, keep
        the diff of each axis then store in a file every
        _STORE_FREQ seconds"""
        if self._get_bit_flag(_IDX_STATE_1, _CURRENTLY_TRACKING):
            buff = self._buff
            xyz = wasp.watch.accel.accel_xyz()
            if xyz == (0, 0, 0):
                wasp.watch.accel.reset()
                xyz = wasp.watch.accel.accel_xyz()
            buff[0] += (abs(self._accel_memory[0]) - abs(xyz[0]))
            buff[1] += (abs(self._accel_memory[1]) - abs(xyz[1]))
            buff[2] += (abs(self._accel_memory[2]) - abs(xyz[2]))
            self._accel_memory = array("f", (xyz[0], xyz[1], xyz[2]))  # contains previous accelerometer value
            self._data_point_nb += 1

            # add alarm to log accel data in _FREQ seconds
            self._next_track_time = wasp.watch.rtc.time() + _FREQ
            wasp.system.set_alarm(self._next_track_time, self._trackOnce)

            self._periodicSave()
            if wasp.watch.battery.level() <= _BATTERY_THRESHOLD and ((not hasattr(wasp, "_is_in_simulation")) or wasp._is_in_simulation is False):
                # strop tracking if battery low
                self._stop_tracking(keep_main_alarm=True)
                h, m = wasp.watch.time.localtime(wasp.watch.rtc.time())[3:5]
                wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {
                    "src": "SleepTk",
                    "title": "Bat low",
                    "body": "Stopped tracking sleep at {}h{}m because your "
                            "battery went below {}%. Alarm kept "
                            "on but bluetooth turned off.".format(
                                h, m, _BATTERY_THRESHOLD)})
                import ble  # disable bluetooth to save battery
                if ble.enabled():
                    ble.disable()
                del ble
            elif self._get_bit_flag(_IDX_STATE_1, _HR_ENABLED) and \
                    wasp.watch.rtc.time() - self._last_HR_date > _HR_FREQ and \
                    not self._track_HR_once:
                self._track_HR_once = int(wasp.watch.rtc.time())
                wasp.system.wake()
                if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
                    wasp.watch.display.mute(True)
                    wasp.watch.display.poweroff()
                    wasp.watch.backlight.set(0)
                wasp.system.switch(self)
                wasp.system.request_tick(1000 // 8)

    def _periodicSave(self):
        """save data to csv with row order:
            1. multiple from saving frequency from start, if different
                than a simple increment from previous value
            2/3/4. X/Y/Z diff values since the last recording. The values are
                also averaged since the last recording then converted to
                grad then into a single motion angle. This saves a lot of
                space and allows for more frequent file savings.
            5. BPM value or "?" if unknown
            6. meta: 0 if nothing
                     1 if pressed or touched (indicating wake state)
                     2 if gradual vibration happened or natural wake
                     3 if pressed or touched after gradual vibration
        """
        # fix the status bar never updating
        wasp.watch.drawable.set_color(_FONT_COLOR)
        self._draw_system_bar()

        buff = self._buff
        n = self._data_point_nb - self._last_checkpoint
        if wasp.watch.rtc.time() - self._track_HR_once > 60:
            # if for some reason we are still trying to compute the
            # heart rate after 60s, something went wrong and saving motion
            # data is more important so cancelling this tracking
            self._track_HR_once = 0
        if n >= _STORE_FREQ // _FREQ and not self._track_HR_once:
            if self._states[_IDX_LAST_HR] != 0:
                bpm = self._states[_IDX_LAST_HR]
                self._states[_IDX_LAST_HR] = 0
            elif self._states[_IDX_LAST_HR] == _HEART_RATE_UNKNOWN:
                bpm = "?"
            else:
                bpm = ""  # save a character if no value to print
            if self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT) == 0:
                meta = ""
            else:
                meta = self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT)
            fac = 2 * math.pi / 2000 / n * 1000  # conversion factor
            motion = math.atan(
                    (buff[2] * fac) / (
                        math.sqrt(
                            (buff[0] * fac) ** 2 + (buff[1] * fac) ** 2 + 0.00001)
                        ))
            # only write the number if it's not obvious, meaning saving was
            # delayed
            timestamp = int((wasp.watch.rtc.time() - self._track_start_time) / _STORE_FREQ)
            if timestamp == self._latest_save + 1:
                self._latest_save = timestamp
                timestamp = ""
            else:
                self._latest_save = timestamp
            with open(self.filep, "ab") as f:
                f.write("\n{},{:.3f},{},{}".format(
                    timestamp,
                    motion,
                    bpm,
                    meta,
                    ).encode("ascii"))
            # reset buffer
            self._buff = array("f", (0, 0, 0))
            wasp.watch.accel.reset()
            self._last_checkpoint = self._data_point_nb
            self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 0)

    def _activate_ticks_to_ring(self):
        """listen to ticks every second, telling the watch to vibrate and
        completely wake the user up"""
        if self._WU_t is None:
            # alarm was already started and stopped
            return
        wasp.system.wake()
        wasp.system.switch(self)
        self._change_page(_PAGE_RINGING)
        self._set_shifted_int(_IDX_STATE_2, _NUM_VIB_MASK, _NUM_VIB_SHIFT, 0)
        wasp.system.request_tick(period_ms=1000)
        wasp.system.notify_level = self._get_shifted_int(_IDX_STATE_3, _PREV_NOTE_MASK, _PREV_NOTE_SHIFT)  # restore notification level
        wasp.system.brightness = self._get_shifted_int(_IDX_STATE_3, _PREV_BRIGHT_MASK, _PREV_BRIGHT_MASK)
        if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
            wasp.watch.display.mute(True)
            wasp.watch.display.poweroff()
            wasp.watch.backlight.set(0)
        self._draw()

    def _start_natural_wake(self):
        """do a tiny vibration every 30s until the user wakes up"""
        if self._WU_t is None:
            # alarm was already started and stopped
            return
        wasp.system.wake()
        wasp.system.switch(self)

        # cancel alarm then set to of them to make sure it does not skip one
        wasp.system.cancel_alarm(None, self._start_natural_wake)
        self._WU_t = int(wasp.watch.rtc.time() + _NATURAL_WAKE_IVL + _NATURAL_WAKE_IVL * _NATURAL_WAKE_RAND / 100 * (random.random() - 0.5) * 2)
        wasp.system.set_alarm(self._WU_t, self._start_natural_wake)
        self._change_page(_PAGE_RINGING)

        wasp.system.notify_level = self._get_shifted_int(_IDX_STATE_3, _PREV_NOTE_MASK, _PREV_NOTE_SHIFT)
        wasp.system.brightness = self._get_shifted_int(_IDX_STATE_3, _PREV_BRIGHT_MASK, _PREV_BRIGHT_MASK)
        self._set_shifted_int(_IDX_STATE_2, _NUM_VIB_MASK, _NUM_VIB_SHIFT, 0)
        if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
            wasp.watch.display.mute(True)
            wasp.watch.display.poweroff()
            wasp.watch.backlight.set(0)

        # tiny vibration
        wasp.watch.vibrator.pulse(duty=3, ms=50)
        if self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT) == 1:  # if pressed or touched
            self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 3)  # because also pressed
        else:
            self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 2) # gradual vibration
        self._draw()

        if not self._track_HR_once and _NATURAL_WAKE_IVL >= 60:
            # if the interval is too short, making the watch sleep after
            # each vibration will actually make it wait too long between
            # vibrations
            wasp.watch.display.mute(False)
            wasp.watch.backlight.set(1)
            wasp.watch.display.poweron()
            wasp.system.sleep()

    def tick(self, ticks):
        """vibrate to wake you up OR track heart rate using code from heart.py"""
        wasp.system.switch(self)
        if self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT) == _PAGE_RINGING and not self._get_bit_flag(_IDX_STATE_1, _NAT_WAKE_ENABLED):
            wasp.system.keep_awake()
            # in 60 vibrations, ramp up from subtle to strong:
            wasp.watch.vibrator.pulse(duty=max(80 - 1 * self._n_vibration, 20),
                                      ms=min(100 + 6 * self._n_vibration, 500))
            self._set_shifted_int(_IDX_STATE_2, _NUM_VIB_MASK, _NUM_VIB_SHIFT, self._get_shifted_int(_IDX_STATE_2, _NUM_VIB_MASK, _NUM_VIB_SHIFT) + 1)
        elif self._track_HR_once:
            wasp.watch.hrs.enable()
            if self._hrdata is None:
                self._hrdata = ppg.PPG(wasp.watch.hrs.read_hrs())
            t = wasp.machine.Timer(id=1, period=8000000)
            t.start()
            wasp.system.keep_awake()
            if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
                wasp.watch.display.mute(True)
                wasp.watch.display.poweroff()
                wasp.watch.backlight.set(0)
            self._subtick()
            while t.time() < 41666:
                pass
            wasp.system.keep_awake()
            self._subtick()
            while t.time() < 83332:
                pass
            wasp.system.keep_awake()
            self._subtick()
            t.stop()
            del t

            wasp.system.keep_awake()
            if len(self._hrdata.data) >= 240:  # 10 seconds passed
                bpm = self._hrdata.get_heart_rate()
                bpm = int(bpm) if bpm is not None else None
                if bpm is None:
                    # in case of invalid data, write it in the file but
                    # keep trying to read HR
                    self._states[_IDX_LAST_HR] = _HEART_RATE_UNKNOWN
                    self._hrdata = None
                    self._states[_IDX_LAST_HR_PRINTED] = self._states[_IDX_LAST_HR]
                elif bpm < 100 and bpm > 40:
                    # if HR was already computed since last periodicSave,
                    # then average the two values
                    if self._states[_IDX_LAST_HR] != _HEART_RATE_UNKNOWN:
                        self._states[_IDX_LAST_HR] = (self._states[_IDX_LAST_HR] + bpm) // 2
                    else:
                        self._states[_IDX_LAST_HR] = bpm
                    self._states[_IDX_LAST_HR_PRINTED] = elf._states[_IDX_LAST_HR]
                    self._last_HR_date = int(wasp.watch.rtc.time())
                    self._track_HR_once = None
                    self._hrdata = None
                    wasp.watch.hrs.disable()
                    if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
                        wasp.system.sleep()

    def _subtick(self):
        """track heart rate at 24Hz"""
        self._hrdata.preprocess(wasp.watch.hrs.read_hrs())

    def _tiny_vibration(self):
        """vibrate just a tiny bit before waking up, to gradually return
        to consciousness"""
        if abs(int(wasp.watch.rtc.time()) - self._last_touch) > 5:
            wasp.watch.display.mute(True)
            wasp.watch.display.poweroff()
            wasp.watch.backlight.set(0)
        wasp.system.wake()
        wasp.system.switch(self)
        if self._get_shifted_int(_IDX_STATE_2, _PAGE_MASK, _PAGE_SHIFT) != _PAGE_RINGING:  # safeguard: don't vibrate anymore if already on ringing page
            #wasp.watch.vibrator.pulse(duty=3, ms=50)
            wasp.watch.vibrator.pulse(duty=80, ms=100)
            # time.sleep(0.1)
            # wasp.watch.vibrator.pulse(duty=3, ms=50)
        if self._get_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT) == 1:  # if pressed or touched
            self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 3)  # because also pressed
        else:
           self._set_shifted_int(_IDX_STATE_2, _META_STATE_MASK, _META_STATE_SHIFT, 2) # gradual vibration
        if not self._track_HR_once:
            wasp.system.sleep()

    def _load_settings(self):
        if hasattr(wasp.system, "get") and callable(wasp.system.get):
            try:
                self._states[_IDX_STATE_1] = wasp.system.get("sleeptk_settings")
            except Exception:
                pass

    def _save_settings(self):
        if hasattr(wasp.system, "set") and callable(wasp.system.set):
            wasp.system.set("sleeptk_settings", self._states[_IDX_STATE_1])

    def _draw_system_bar(self):
        sbar = wasp.system.bar
        sbar.clock = True
        sbar.draw()

    def _get_shifted_int(self, register_idx, bit_mask, bit_shift):
        return (self._states[register_idx] & bit_mask) >> bit_shift

    def _set_shifted_int(self, register_idx, bit_mask, bit_shift, value):
        self._states[register_idx] = (self._states[register_idx] & bit_mask) | (value << bit_shift)

    def _get_bit_flag(self, register_idx, bit_mask):
        return self._states[register_idx] & bit_mask > 0

    def _set_bit_flag(self, register_idx, bit_mask, new_state):
        if new_state:
            self._states[register_idx] = self._states[register_idx] | bit_mask
        else:
            self._states[register_idx] = self._states[register_idx] & ~bit_mask
