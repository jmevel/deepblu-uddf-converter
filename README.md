# Deeplu UDDF Converter

A simple tool to convert Deepblu log files (both 'dives' and 'drafts') into UDDF

Retrieves dive logs from Deepblu and exports them in [Universal Dive Data Format](http://uddf.org) (UDDF), which can be imported into other applications that support it, including [Subsurface Divelog](https://subsurface-divelog.org/).

![Deepblu logs imported into Subsurface](/web/img/imported_into_subsurface.jpg)

## Prerequisites  

You should manually retrieve your logs from Deepblu.
1. Go to deepblu.com website
2. Log in
3. Go to `Your logbook`. You should now be on an URL with the format `https://www.deepblu.com/user/[YOUR ID]/profile/divelogs`
4. Go to the following URL: `https://www.deepblu.com/apis/discover/v0/post/[YOUR ID]/diveLog?limit=999` (replace `[YOUR ID]` by the correct value)
5. Right-click on the displayed text and `Save as` to save the file somewhere on your computer

If you want to retrieve your draft as well, it's a bit more tricky:
1. Use the FIREFOX browser
2. Go to deepblu.com website
3. Log in
4. Go to `Your logbook`. You should now be on an URL with the format `https://www.deepblu.com/user/[YOUR ID]/profile/divelogs`
5. Press `F12` to open the developers console
6. On the web page click on `Drafts`
7. In the developers console, go to the `Network` tab
8. Spot the request that starts by `getRawLogs` (you can use the filter field to find it easily)
9. Right-click on it and `Edit and resend`
10. Change the URL to be `https://www.deepblu.com/apis/divelog/v0/getRawLogs?hide=0&type=1&limit=999` and click on `Send`
11. Spot the newly sent `getRawLogs` request, click on it and go to the `Response` tab
12. Click on the `Raw` toggle and select the entire JSON response, copy and save the content to a text file named `drafts.json` 

## Requirements

Make sure you have Python 3 and pip3 installed then install the required libraries

```sh
pip install -r requirements.txt
```

## Usage

```
Usage: python -m deepblu_tools.bin.cli [OPTIONS]


Options:
  -f, --infile TEXT       load data from JSON file
  -o, --outfile TEXT      Write results to this file
  --help                  Show this message and exit.
```

### Examples

```sh
python -m deepblu_tools.bin.cli -f ./diveLog.json -o ./diveLog.uddf
python -m deepblu_tools.bin.cli -f ./drafts.json -o ./drafts.uddf
```
