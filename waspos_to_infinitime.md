# Notes on how I switched from wasp-os to infinisleep

*This file contains notes I took when I switched from waspos to infinitime. It is not a proper tutorial. The original message was posted in november 2024 and can be found [here](https://github.com/thiswillbeyourgithub/SleepTk_pinetime_sleep_tracker/issues/13#issuecomment-2486362429)*

- I initially followed this guide: https://pine64.org/documentation/PineTime/Software/Switching_between_InfiniTime_and_Wasp-os/

- use ota-dfu **from waspos** to flash the recovery file:
`./waspos/tools/ota-dfu/dfu.py -z ../infinitime/infinisleep/reloader-infinitime-recovery-0.14.1.zip -a $MAC_ADDRESS --legacy`

- This seemed to work fine.

- Then after a while I finally understood how to get the pineapple to be red and make the watch ready to accept the infinitime zip.

- Then when I tried the same with flashing the mcuboot from infinisleep at https://github.com/cyberneel/InfiniTime/releases:
`./waspos/tools/ota-dfu/dfu.py -z ./infinitime/infinisleep/pinetime-mcuboot-app-dfu-1.14.0.zip -a $MAC_ADDRESS --legacy`

- I continually got error : `Checking DFU State...
Exception at line 163: UUID not found: 8ec90001-f315-4f60-REDACTED-REDACTED`

- I also failed to get gadgetbridge to upload it.

- Then finally tried again with the dfu.py **from infinitime (instead of the one from wasp-os)** and finally it worked. The full command was: `python dfu.py -z ../../../infinisleep/pinetime-mcuboot-app-dfu-1.14.0.zip -a $MAC_ADDRESS --legacy`

- **Note: a big difference between waspos and infinitime is that on infinitime every time you flash the OS (for example for updates) you have to go to `settings > firmware > validate` as if you don't the next boot will use the previous version instead of the one you just flashed!**
