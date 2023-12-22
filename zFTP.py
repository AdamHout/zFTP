#!/usr/bin/env python3
# zFTP - A tool for remotely running jobs on a z/OS mainframe via FTP
#
# Summary:
#  -Connect to the IBM zXPLORE mainframe via FTP
#  -Delete JCL3OUT dataset if present
#  -Run job JCL3 / Retrieve the job log
#     -Automatically display the job log upon failure and exit
#  -Download the dataset built by the submitted job
#  -Provide the option to display the job log and/or the downloaded dataset
#
# Notes:
# When submitting a job via FTP, the job name in the JCL may need
# to match the user ID in order to retrieve the job log listing. See:
# https://www.ibm.com/support/pages/ftp-clients-failing-retrieve-jes-output-zos-ftp-server
# https://www.ibm.com/support/pages/sitelocsite-commands-mvs-ftp

# ---Imports---
import ftplib
from yaspin import yaspin
from yaspin.spinners import Spinners
#import logging

# ---Globals---
jlog = []
jlist = []
jname = 'JCL3'
jid = ''
jrc = ''
jerr = ''
nlist = []
sel = ''
dset = 'JCL3OUT'


# ---Functions---
# Callback function to retrieve and audit the job log
def jescallback(line):
    global jlog, jid, jrc, jerr
    jlog.append(line.strip())
    if jid == '' and str(line).find('JOB') != -1:
        parts = str(line).split(' ')
        for word in parts:
            if str(word).find('JOB') != -1:
                jid = word
                break
    if jrc == '' and str(line).find('RC=') != -1:
        parts = str(line).split(' ')
        for word in parts:
            if str(word).find('RC=') != -1:
                jrc = word
                break
    if jrc == '':
        if str(line).find('ABEND') != -1 or str(line).find('- JOB FAILED -') != -1:
            jrc = 'Job aborted'
            jerr = line


# Write z/OS dataset lines to a local file
def retrcallback(line):
    lclfile.write(line + '\n')


# -----------------------Begin mainline logic-------------------------------

# ---Pull credentials from disk---
fp = open('creds.ftp', 'r')
HOSTNAME = fp.readline().strip()
USERNAME = fp.readline().strip()
PASSWORD = fp.readline().strip()
fp.close()

# ---Connect to the IBM zXplore mainframe via FTP---
print(f"Connecting to zXPLORE FTP server {HOSTNAME}")
try:
    ftp = ftplib.FTP(HOSTNAME, USERNAME, PASSWORD)
except OSError as err:
    print(err.strerror)
    exit(err.errno)

print(ftp.getwelcome())
ftp.encoding = "utf-8"
# ftp.debug(1)
print(f"Home server directory: {ftp.pwd()}")

# ---Delete the old dataset if present---
try:
    nlist = ftp.nlst()
except ftplib.all_errors as err:
    print(err)
    exit(err.errno)

for entry in nlist:
    if entry == dset:
        try:
            ftp.delete(entry)
            print(f"Existing dataset {dset} deleted")
        except ftplib.all_errors as err:
            print(err)
            exit(err.errno)


# "JESOWNER=*" allows FTP to retrieve all jobs owned by the submitting userid
# "jes fil=" Specifies the file type of the data set. The description of each file type is:
#    SEQ: Sequential or partitioned data sets on DASD
#    PIO: PIO data sets on DASD
#    SQL: SQL query function
#    JES: Remote job submission
ftp.voidcmd('SITE JESOWNER=*')
ftp.voidcmd('site file=JES')

# ---Submit job JCL3 and retrieve the job log---
print(f"Submitting job {jname}")
spinner = yaspin(Spinners.line, side='right', text=f"Waiting for {jname} job log...")
spinner.start()
try:
    ftp.retrlines("RETR 'Z34426.JCL(JCL3)'", jescallback)
except ftplib.all_errors as err:
    print(err)
    exit(err.errno)

spinner.stop()
print(f"{jid} completed with {jrc}")

# ---Download the new dataset---
if jrc == 'Job aborted':
    print(jerr)
    ftp.quit()
    print("FTP client closed")
    x = input('Hit any key for job log: ')
    for entry in jlog:
        print(entry)
else:
    ftp.voidcmd('site file=SEQ')                                     # Switch the FTP server back to dataset mode
    lclfile = open(dset, 'w')
    try:
        ftp.retrlines(f"RETR {dset}", retrcallback)
    except ftplib.all_errors as err:
        print(err)
        exit(err.errno)

    lclfile.close()
    print(f"Dataset {dset} downloaded from server")
    ftp.quit()
    print("FTP client closed")

    # ---Display the job log and/or the output dataset file if desired---
    while True:
        sel = input('Display (j)ob log (d)ataset (b)oth (n)one? ')
        if sel == 'j' or sel == 'd' or sel == 'b' or sel == 'n':
            break
        else:
            print(f"{sel} is an invalid option")

    if sel == 'j' or sel == 'b':
        for entry in jlog:
            print(entry)

    if sel == 'd' or sel == 'b':
        file = open(dset, "r")
        print('\nDataset Content:\n', file.read())

print('Process complete')
exit(0)
