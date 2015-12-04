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
from convertcfg import pathImageMagick
from convertcfg import pathImageMagick2
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
    for file in files:
        #print os.path.join(subdir, file)
        filepath = subdir + os.sep + file

        if filepath.endswith(".svg") and onlyExportFileWithName in filepath:
            if "deleteme" in filepath:
                os.remove( filepath )
                continue
            fileList.append(filepath);
            
print('workingdir:', workingdir)            
#py2output = execute(['python', 'py2.py', '-i', 'test.txt'])
#print('fileList:', fileList)


def execute(command):
    global lock
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
        
def exportSVG(file, path512):
    cmd = [pathInkscape, '--export-area=512:512:1024:1024', '--export-png='+path512, file]
    return execute(cmd)

def repeat(path512, path1536):
    repeat_cmd = "montage -background transparent -mode concatenate -tile 3x3".split(' ')
    repeat_cmd[0] = pathImageMagick2
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append(path512)
    repeat_cmd.append("PNG32:"+path1536)
    return execute(repeat_cmd)


def downsample(path1536, path384):
    downsample_cmd = "convert {input} -colorspace RGB -filter LanczosRadius -distort Resize 384x384 -colorspace sRGB {output}".split(' ')
    downsample_cmd[0] = pathImageMagick
    downsample_cmd[1] = path1536
    downsample_cmd[-1] = "PNG32:"+path384
    return execute(downsample_cmd)

def downsampleNoRepeat(path512, path128):
    downsample_cmd = "convert {input} -colorspace RGB -filter Lanczos -define filter:blur=.9 -distort Resize 128x128 -colorspace sRGB {output}".split(' ')
    #downsample_cmd = "convert {input} -colorspace RGB -filter Cosine -resize 128x128 -colorspace sRGB {output}".split(' ')
    downsample_cmd = "convert {input} -colorspace RGB -distort Resize 128x128 -colorspace sRGB {output}".split(' ')
    downsample_cmd[0] = pathImageMagick
    downsample_cmd[1] = path512
    downsample_cmd[-1] = "PNG32:"+path128
    return execute(downsample_cmd)

def mkdir_p(path):
    global lock
    lock.acquire()
    if not os.path.exists(path):
        os.makedirs(path)
    lock.release()
def crop(path384, path128):
    mkdir_p(os.path.dirname(path128))
    
    crop_cmd = "convert {input} -crop 128x128+128+128 {output}".split(' ')
    crop_cmd[0] = pathImageMagick
    crop_cmd[1] = path384
    crop_cmd[-1] = "PNG32:"+path128
    return execute(crop_cmd)
    
lock = threading.Lock()
mkdir_p(outdir)
total=0
totalF=len(fileList)
killed=False
print "{} svg files to convert".format(totalF)
if totalF==0:
    sys.exit(1)
def work(threadid, sublist):
    global lock
    global total
    global totalF
    global killed
    exitcode=0
    output=""
    for file in sublist:
        try:
            lock.acquire()
            print file
            lock.release()
            svg = minidom.parse(open(file))
            layers = {}
            for g in svg.getElementsByTagName("g"):
                if g.attributes.has_key("inkscape:label"):
                    label = g.attributes["inkscape:label"].value
                    if "layer" in label and "layer" == label[:5]:
                        idx = int(label[5:])
                        layers[idx] = {}
                        layers[idx]["element"] = g
                        if not g.hasAttribute("style"):
                            g.setAttribute("style", "")
                        layers[idx]["prevstyle"] = g.attributes['style'].value
                        g.attributes['style'].value = 'display:none'
            filesdelete = []
            subfiles = [[file, file]]
            if len(layers):
                subfiles = []
                lock.acquire()
                print "Found "+str(len(layers))+" layers on "+file
                lock.release()
                for idx, mapEl in layers.iteritems():
                    g = mapEl["element"]
                    g.attributes['style'].value = mapEl["prevstyle"]
                    export = svg.toxml()
                    filein = file[:-4]+".layer"+str(idx)+".deleteme.svg"
                    codecs.open(filein, "w", encoding="utf8").write(export)
                    g.attributes['style'].value = 'display:none'
                    subfiles.append([filein, file[:-4]+".layer"+str(idx)+".svg"])
                    filesdelete.append(filein)
                totalF = totalF + len(subfiles)-1
            for subfile in subfiles:
                filein = subfile[0]
                fileout = subfile[1]
                path_out, file_name_out = os.path.split(fileout)
                pathsplit = path_out.split("\\")
                blockpath = pathsplit[2] if len(pathsplit) > 2 else ""
                needTiling = not ("flowers" in blockpath or "plants" in blockpath)
                filepath512 = outdir+"\\"+file_name_out[:-4]+"_512.png"
                filepath1536 = outdir+"\\"+file_name_out[:-4]+"_1536.png"
                filepath384 = outdir+"\\"+file_name_out[:-4]+"_384.png"
                filepath128 = outdir+"\\"+path_out[5:]+"\\"+file_name_out[:-4]+".png"
                filesdelete.append(filepath512)
                if needTiling:
                    filesdelete.append(filepath1536)
                    filesdelete.append(filepath384)
        
                exitcode, output = exportSVG(filein, filepath512)
                if exitcode != 0:
                    lock.acquire()
                    print "svg export failed (exit code {}): {}".format(exitcode, output)
                    lock.release()
                    continue
                if killed:
                    break
                if needTiling:
                    exitcode, output = repeat(filepath512, filepath1536)
                    if exitcode != 0:
                        lock.acquire()
                        print "repeat failed (exit code {}): {}".format(exitcode, output)
                        lock.release()
                        continue
                    if killed:
                        break
                    exitcode, output = downsample(filepath1536, filepath384)
                    if exitcode != 0:
                        lock.acquire()
                        print "downsample failed (exit code {}): {}".format(exitcode, output)
                        lock.release()
                        continue
                    if killed:
                        break
                    exitcode, output = crop(filepath384, filepath128)
                    if exitcode != 0:
                        lock.acquire()
                        print "crop failed (exit code {}): {}".format(exitcode, output)
                        lock.release()
                        continue
                else:
                    exitcode, output = downsampleNoRepeat(filepath512, filepath128)
                    if exitcode != 0:
                        lock.acquire()
                        print "downsampleNoRepeat failed (exit code {}): {}".format(exitcode, output)
                        lock.release()
                        continue
                    
                lock.acquire() # will block if lock is already held
                total=total+1
                print "Converting...{}/{}".format(total, totalF)
                lock.release()
                if killed:
                    break
            if killed:
                break
            for f in filesdelete:
                os.remove( f )
        except:
            lock.acquire() # will block if lock is already held
            printexc()
            lock.release()
num_threads=2
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


print "Starting..."


for i in range(num_threads):
    threads[i] = threading.Thread(name='worker #'+str(i), target=work, args=(i,sublists[i], ))
for i in range(num_threads):
    threads[i].start()
while total < len(fileList)-5:
    time.sleep(1)
    

for i in range(num_threads):
    threads[i].join()

    

