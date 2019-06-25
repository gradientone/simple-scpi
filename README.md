# Simple SCPI Client

A simple python client for passing SCPI commands to VXI11 instruments

## Requirements

Requires Python and VXI11

### Python

[Download Python](https://www.python.org/downloads/)

### Python VXI11
Python VXI11 provides a pure python TCP/IP driver for LAN based instruments that support the VXI11 protocol. This includes most LXI instruments.

Home page: [http://www.alexforencich.com/wiki/en/python-vxi11/start](http://www.alexforencich.com/wiki/en/python-vxi11/start)

GitHub repository: [http://www.alexforencich.com/wiki/en/python-vxi11/start](https://github.com/python-ivi/python-vxi11)

## Usage:

The scpi_runner.py reads a scpi_script file to open a connection with an
instrument and send commands. The commands and their responses are logged
to a log file. A sample script is provided in scpi_script.sample for you to
modify as needed.

```
TCPIP::192.168.1.87::INSTR
G1:StartLoop:Max=3
*ESR?
*IDN?
G1:Sleep=2
G1:EndLoop
```

The above script opens a connection and runs the `*ESR?` and `*IDN?` commands
three times on a loop, sleeping 2 seconds in between each iteration.

If you don't already have a `~/scpi` directory you can make one with:

    mkdir ~/scpi

Once you have the directory you can copy the sample script with:

    cp scpi_script.sample ~/scpi/scpi_script

The above will work for MacOS, Linux, and even Windows Powershell, but if you're
using a Windows Command Prompt then the commands to use are:

    mkdir %userprofile%\scpi
    copy scpi_script.sample %userprofile%\scpi\scpi_script

To run the scpi script, you will need enter your instrument's TCPIP address.
This can be found on your instrument, usually under IO Setting -> LAN Config.
Replace the TCPIP address found in the sample script with your own.
Then edit the script as desired to run the commands you wish to run.

Then to run the program enter:

    python scpi_runner.py

This will run the scpi script that is expected in your `~/scpi`
directory. You should some output printed to your console and you
can find it logged to `~/scpi/scpi_runner.log` or for Windows Command Prompt
users: `%userprofile%\scpi\scpi_runner.log`

### Timeouts

The scpi_runner will time out commands and scripts that take too long
to run. The command timeouts will raise an exception and run the
next command. If the whole script times out then an exception is raised
and the remaining commands are not run.

These timeouts can be modified by editing the values set in `settings.py`

### GradientOne ScriptLogic

The scpi_runner.py supports basic loops and sleeps (delays).
The syntax for the GradienOne ScriptLogic objects is not case-sensitive,
so G1:StartLoop and g1:startloop are equivalent.

#### Loops

To start a block of commands to loop, a StartLoop command is needed.

    G1:StartLoop:Max=<NumberOfTimes>:BreakOn=<ResponseToBreak>

The Max is required, otherwise the block of commands will only run once.
The BreakOn is optional. The string `G1:StartLoop:Max=3` will start
a loop that runs 3 times. You then enter as many commands as needed in the
next lines and end the block of code to loop with a line with `G1:EndLoop`

Example:

```
G1:StartLoop:Max=3
*IDN?
G1:EndLoop
```

Will run the `*IDN?` command 3 times.


#### Sleeps

To add a delay to your script in between commands, use a `G1:Sleep`

    G1:Sleep=<NumberOfSeconds>

For example, to sleep 2 seconds:

    G1:Sleep=2

This calls python's time.sleep() function to delay running the next line.
This can also be used within a loop.
