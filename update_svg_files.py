#! python2
import os, subprocess
import itertools as itertools 
import threading
import time
import signal
import sys
import codecs
import traceback

from xml.dom import minidom
from convertcfg import outdir
from convertcfg import pathImageMagickDir
from convertcfg import pathInkscape
from convertcfg import onlyExportFileWithName

killed=False
def signal_handler(signal, frame):
    global killed
    killed=True
    print('Abort!')
    sys.exit(1)
signal.signal(signal.SIGINT, signal_handler)

workingdir = os.path.dirname(os.path.realpath(__file__))
rootdir="."
fileList=[]
for subdir, dirs, files in os.walk(rootdir):
    print subdir
    if not "SVG_NEW" in subdir[0:9]:
        continue
    for file in files:
        #print os.path.join(subdir, file)
        filepath = subdir + os.sep + file

        if filepath.endswith(".svg") and onlyExportFileWithName in filepath:
            if "deleteme" in filepath:
                os.remove( filepath )
                continue
            fileList.append(filepath);
            
print('workingdir:', workingdir)           


def execute(command):
    global lock
    #lock.acquire()
    #print " ".join(command)
    #lock.release()
    my_env = os.environ.copy()
    my_env["PATH"] = pathImageMagickDir + ";" + my_env["PATH"]

    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
    output = ''
    # Poll process for new output until finished
    for line in iter(process.stdout.readline, ""):
        output += line
    process.wait()
    exitCode = process.returncode
    return (exitCode, output)
def printexc():
    exc_type, exc_value = sys.exc_info()[:2]
    print 'Handling %s exception with message "%s" in %s' % \
        (exc_type.__name__, exc_value, threading.current_thread().name)
    traceback.print_exc()

def mkdir_p(path):
    global lock
    lock.acquire()
    if not os.path.exists(path):
        os.makedirs(path)
    lock.release()

lock = threading.Lock()
mkdir_p(outdir)
total=0
totalF=len(fileList)
killed=False
print "{} svg files to update ".format(totalF)
if totalF==0:
    sys.exit(1)
def work(threadid, sublist):
    global lock
    global total
    global totalF
    global killed
    exitcode=0
    for file in sublist:
        try:
            lock.acquire()
            print file
            lock.release()
            path_out, file_name_out = os.path.split(file)
                    
            cmd = [pathInkscape, file, '--verb', 'FileSave', '--verb', 'FileClose' ]
            
            exitcode, output = execute(cmd)
            if exitcode != 0:
                lock.acquire()
                print "svg export failed (exit code {}): {}".format(exitcode, output)
                lock.release()
                continue      
            lock.acquire() # will block if lock is already held
            total=total+1
            print "Converting...{}/{}".format(total, totalF)
            lock.release()
            if killed:
                break
            break
        except:
            lock.acquire() # will block if lock is already held
            printexc()
            lock.release()
num_threads=1
threads=[None]*num_threads
sublists=[None]*num_threads
iLen = len(fileList)/num_threads
if len(fileList) % num_threads != 0:
    iLen=iLen+1
splitsize = iLen
for i in range(num_threads):
    istart = i*splitsize
    iend = istart+splitsize if istart+splitsize < len(fileList) else len(fileList)
    sublists[i]=fileList[istart:iend]
for i in range(num_threads):
    threads[i] = threading.Thread(name='worker #'+str(i), target=work, args=(i,sublists[i], ))
for i in range(num_threads):
    threads[i].start()
while total < len(fileList)-5:
    time.sleep(1)

print "Starting..."



    

for i in range(num_threads):
    threads[i].join()

    

