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

## Quickstart Guide:

Before using `scpi_runner.py` you will need a `scpi_script.txt`.

A sample script have been provided for you to copy and edit as needed.

For MacOS, Linux, and Windows Powershell you can run the following from the command line.

    git clone https://gitlab.com/gradientone/scpi-client
    cd scpi-client
    cp scpi_script.txt.py scpi_script.txt.py

Note that for the Windows Command Prompt the copy command is different. You will need to
replace the last line with:

    copy sample_settings.py settings.py

To run the scpi script, you will need enter your instrument's TCPIP address.
This can be found on your instrument, usually under IO Setting -> LAN Config.
Replace the sample TCPIP address (192.168.1.87) in the script with your own.
Then edit the script as desired to run the commands you wish to run.

When you're ready to run the script, enter the following into the command line

    python scpi_runner.py

The `scpi_runner.py` reads a `scpi_script.txt` file to open a connection with
an instrument and send commands. The commands and their responses are logged
to a log file.

You should some output printed to your console and you
can find it logged to `logs/scpi_runner.log` or for Windows Command Prompt
users: `logs\scpi_runner.log`

**NOTE for GradientOne API Commands:**

While not required for running basic commands locally, any commands that
make requests to the GradientOne API will need a `GradientOneAuthConfig.txt`

Follow the instructions in the next section if you need help getting one.

## Using the GradienOne API

To use the GradientOne API you will need an a GradientOne account. If you do not
have an account you can [sign up for free!](https://demo.gradientone.com/welcome)

Once you have an account, go to the account page to download your auth token.
You can find it in *Auth Info* -> *Download Config*

When you run the `scpi_runner.py` it will move the config file from your
Downloads directory to a relative `etc/` directory for the the script runner
to use when making API calls.

Now you should be ready to use the GradientOne API. Yay!

**About the sample script**

The sample script starts with:

```
G1:Open:TCPIP::192.168.1.87::INSTR
G1:StartLoop:Max=3
*ESR?
*IDN?
G1:Sleep(2)
G1:EndLoop
```

The above section opens a connection and runs the `*ESR?` and `*IDN?` commands
three times on a loop, sleeping 2 seconds in between each iteration.

## How the SCPI Client Works

For more info on how this all works and more advanced features

### Opening an Instrument Connection

As mentioned in the Quickrstart Guide, to send commands to an instrument you
will first have to open a connection with an instrument. Typically this will
be the first thing you do in your script. The command string to open an instrument
looks like:

    G1:Open:TCPIP::192.168.1.87::INSTR

The importat part is to start with the `G1:Open:` and then follow with the
resource string you want to use to open the instrument connection.

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

    G1:Sleep(<NumberOfSeconds>)

For example, to sleep 2 seconds:

    G1:Sleep(2)

This calls python's time.sleep() function to delay running the next line.
This can also be used within a loop.


### Fetching Data

To fetch data from the instrument the `G1:FetchScreenshot` and
`G1:FetchWaveform` can be used as part of a scpi script.

**Fetching a Screenshot**

When the `G1:FetchScreenshot` is run, an image of what is on the instrument
screen is captured and written to the file location specified in `settings.py`.
Be sure that you have an instrument initialized before running this.

**Fetching a Waveform**

When the `G1:FetchWaveform` is run, instrument will iterate over each channel
and fetch a trace for each. The y values (e.g. volts) will be saved to a dictionary
object that will be written as JSON to the file location specified in `settings.py`.

*IMPORTANT NOTE:* These commands will *not* send data to the GradienOne servers.
To do that will require an Auth Token and using the GradienOne Post commands.

### Posting Screenshots

You can post a screenshot to the GradientOne API so that you can save, share, and
review it whenever, wherever you like. To do so, add a `G1:PostScreenshot` command
to your `scpi_script.txt` file. Be sure that you run a `G1:FetchScreenshot` before
trying to post one, otherwise the command will fail without anything to post.

### Posting Waveforms

To post a waveform to the GradientOne API works very similarly to posting a screenshot.
Add a `G1:PostWaveform` command into your `scpi_script.txt` file after you run
a `G1:FetchWaveform` command and this will post the waveform data to the GradientOne
servers to create a result.

### Putting it together: Fetching Data and Posting

Below is a sample script and some expected output for fetching data and posting it
to GradientOne.

```
# This is a sample to open an instrument
# You will need to update it with your own address
G1:Open:TCPIP::192.168.1.87::INSTR

# To fetch a screenshot and save to file
G1:FetchScreenshot

# To post that screenshot to GradientOne
G1:PostScreenshot

# To fetch a waveform and save to file
G1:FetchWaveform

# To post that waveform to GradientOne
G1:PostWaveform
```

Console log output. Sample dummy ID info inserted to replace private data.

```
2019-08-19 16:48:13 :: [ INFO ] Initializing instrument at: TCPIP::192.168.1.87::INSTR
2019-08-19 16:48:13 :: [ INFO ] building G1Script: [G1:FETCHSCREENSHOT', 'PostScreenshotCommand', 'G1:FETCHWAVEFORM', 'PostWaveformCommand']
2019-08-19 16:48:15 :: [ INFO ] FetchScreenshotCommand response: Screenshot saved to: C:\Users\UserName\scpi-client\data\screenshot.png
2019-08-19 16:48:15 :: [ INFO ] Using file_key: screenshot-2019-08-19T16:48:15.196000
2019-08-19 16:48:19 :: [ INFO ] File upload succeeded!
2019-08-19 16:48:19 :: [ INFO ] Result ID for screenshot: R321321321
2019-08-19 16:48:19 :: [ INFO ] You can view the result at: https://gradientone-demo.appspot.com/results/R321321321
2019-08-19 16:48:19 :: [ INFO ] Running FetchWaveformCommand
2019-08-19 16:48:20 :: [ INFO ] FetchWaveformCommand response: Waveform saved to: C:\Users\UserName\scpi-client\data\waveform.json
2019-08-19 16:48:23 :: [ INFO ] Request to https://gradientone-demo.appspot.com/results response.status_code: 200
2019-08-19 16:48:23 :: [ INFO ] Result created successfully with result_id: R123123123
2019-08-19 16:48:23 :: [ INFO ] You can view the result at: https://gradientone-demo.appspot.com/results/R123123123
2019-08-19 16:48:23 :: [ INFO ] Writing full trace to file: C:\Users\UserName\scpi-client\data\full-trace-R123123123.json

```

You'll notice some data files saved to the `data` directory and some links where you
can view your results.

If you need further support you can contact support@gradientone.com for more help.
