#! python2
import os, subprocess
import itertools as itertools 
import threading
import time
import signal
import sys
import codecs
import traceback
import shutil

from xml.dom import minidom
from CommandTimeout import Command
from convertcfg import outdir
from convertcfg import pathImageMagickDir
from convertcfg import pathInkscape
from convertcfg import skipExisting
from convertcfg import onlyExportFileWithName
from convertcfg import targetResolution

num_threads=1
usethreading = num_threads > 1
res=targetResolution
res3=res*3

killed=False
def signal_handler(signal, frame):
    global killed
    killed=True
    print('Abort!')
    sys.exit(1)
if usethreading:
    signal.signal(signal.SIGINT, signal_handler)

workingdir = os.path.dirname(os.path.realpath(__file__))
rootdir="."
fileList=[]
for subdir, dirs, files in os.walk(rootdir):
    if not "SVG" in subdir[0:5]:
        continue
    for file in files:
        #print os.path.join(subdir, file)
        filepath = subdir + os.sep + file

        if filepath.endswith(".svg") and onlyExportFileWithName in filepath:
            if "deleteme" in filepath:
                os.remove( filepath )
                continue
            fileList.append(filepath);
            #break;
    #if len(fileList) > 0:
    #    break;
            
print(('workingdir:', workingdir))            
#py2output = execute(['python', 'py2.py', '-i', 'test.txt'])
#print('fileList:', fileList)


def execute_subprocess(command):
    #global lock
    #lock.acquire()
    #print " ".join(command)
    #lock.release()
    my_env = os.environ.copy()
    my_env["PATH"] = pathImageMagickDir + ";" + my_env["PATH"]
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
    output = ""
    while process.poll() is None:
        output += process.stdout.readline().decode(sys.stdout.encoding)
    process.wait()
    exitCode = process.returncode
    if exitCode != 0:
        global killed
        killed = True
    return (exitCode, output)
def execute_timeout(command):
    #global lock
    #lock.acquire()
    #print " ".join(command)
    #lock.release()
    my_env = os.environ.copy()
    my_env["PATH"] = pathImageMagickDir + ";" + my_env["PATH"]
    command = Command(command)
    status, output, error = command.run(timeout=3, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
    return (status, output)
def execute(command):
    return execute_subprocess(command)
def printexc():
    exc_type, exc_value = sys.exc_info()[:2]
    print('Handling %s exception with message "%s" in %s' % \
        (exc_type.__name__, exc_value, threading.current_thread().name))
    traceback.print_exc()
        
def exportSVG(file, path512, offset):
    min = 512+offset
    max = min+512
    cmd = [pathInkscape, '--export-area=512:'+str(min)+':1024:'+str(max), '--export-png='+path512, file]
    ret_process = execute(cmd)
    #print "Execute {}: {} {}".format(" ".join(cmd), ret_process[0], ret_process[1])
    return ret_process

def repeat(path512, path1536):
    repeat_cmd = "montage -background transparent -mode concatenate -tile 3x3".split(' ')
    repeat_cmd[0] = "montage"
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
    global res
    if res == 512:
        shutil.copyfile(path1536, path384)
        return (0, "")
    downsample_cmd = "convert {input} -colorspace RGB -distort Resize XXXxYYY -colorspace sRGB {output}".split(' ')
    downsample_cmd[0] = "convert"
    downsample_cmd[1] = path1536
    downsample_cmd[6] = "{}x{}".format(res3, res3)
    downsample_cmd[-1] = "PNG32:"+path384
    return execute(downsample_cmd)

def downsampleNoRepeat(path512, path128):
    global res
    if res == 512:
        shutil.copyfile(path512, path128)
        return (0, "")
    #downsample_cmd = "convert {input} -colorspace RGB -filter Lanczos -define filter:blur=.9 -distort Resize XXXxYYY -colorspace sRGB {output}".split(' ')
    #downsample_cmd = "convert {input} -colorspace RGB -filter Cosine -resize XXXxYYY -colorspace sRGB {output}".split(' ')
    downsample_cmd = "convert {input} -colorspace RGB -distort Resize XXXxYYY -colorspace sRGB {output}".split(' ')
    downsample_cmd[0] = "convert"
    downsample_cmd[1] = path512
    downsample_cmd[6] = "{}x{}".format(res, res)
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
    
    crop_cmd = "convert {input} -crop XXXxYYY+XXX+YYY {output}".split(' ')
    crop_cmd[0] = "convert"
    crop_cmd[1] = path384
    crop_cmd[3] = "{}x{}+{}+{}".format(res, res, res, res)
    crop_cmd[-1] = "PNG32:"+path128
    return execute(crop_cmd)
    
lock = threading.Lock()
mkdir_p(outdir)
total=0
totalF=len(fileList)
killed=False

print("{} svg files to convert".format(totalF))
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
            print(file)
            lock.release()
            svg = minidom.parse(open(file))
            layers = {}
            # extract layers (bush_forget_me_not)
            for g in svg.getElementsByTagName("g"):
                if "inkscape:label" in g.attributes:
                    label = g.attributes["inkscape:label"].value
                    if "layer" in label and "layer" == label[:5]:
                        idx = int(label[5:])
                        layers[idx] = {}
                        layers[idx]["element"] = g
                        print("layer[{}] = {}".format(idx, str(g)))
                        if not g.hasAttribute("style"):
                            g.setAttribute("style", "")
                        layers[idx]["prevstyle"] = g.attributes['style'].value
                        g.attributes['style'].value = 'display:none'
            filesdelete = []
            subfiles = [[file, file, 0]]
            if len(layers):
                subfiles = []
                lock.acquire()
                print("Found "+str(len(layers))+" layers on "+file)
                lock.release()
                for idx, mapEl in layers.items():
                    g = mapEl["element"]
                    g.attributes['style'].value = mapEl["prevstyle"]
                    export = svg.toxml()
                    filein = file[:-4]+".layer"+str(idx)+".deleteme.svg"
                    codecs.open(filein, "w", encoding="utf8").write(export)
                    g.attributes['style'].value = 'display:none'
                    subfiles.append([filein, file[:-4]+".layer"+str(idx)+".svg", 0])
                    filesdelete.append(filein)
                totalF = totalF + len(subfiles)-1
            export_double = False
            path_out, file_name_out = os.path.split(file)
            if ("flowers" in path_out or "plants" in path_out) and "double_" in file_name_out:
                print("export double plant")
                newSubFiles = []
                for subfile in subfiles:
                    filein = subfile[0]
                    fileout = subfile[1]
                    newSubFiles.append([filein, file[:-4]+".lower.svg", 0])
                    newSubFiles.append([filein, file[:-4]+".upper.svg", 512])
                subfiles = newSubFiles
            for subfile in subfiles:
                filein = subfile[0]
                fileout = subfile[1]
                offset = subfile[2]
                path_out, file_name_out = os.path.split(fileout)
                pathsplit = path_out.split("\\")
                blockpath = pathsplit[2] if len(pathsplit) > 2 else ""
                needTiling = not ("flowers" in blockpath or "plants" in blockpath or "_side" in file_name_out)
                if "vines" in file_name_out:
                    needTiling = True
                filepath512 = outdir+"\\"+file_name_out[:-4]+"_full.png"
                filepath1536 = outdir+"\\"+file_name_out[:-4]+"_tile_repeat_full.png"
                filepath384 = outdir+"\\"+file_name_out[:-4]+"_tile_repeat_target.png"
                filepath128 = outdir+"\\"+path_out[5:]+"\\"+file_name_out[:-4]+".png"
                if not skipExisting or not os.path.isfile(filepath128):
                    
                    mkdir_p(outdir+"\\"+path_out[5:]+"\\")
                    
                    filesdelete.append(filepath512)
                    if needTiling:
                        print("need tiling")
                        filesdelete.append(filepath1536)
                        filesdelete.append(filepath384)
            
                    exitcode, output = exportSVG(filein, filepath512, offset)
                    if exitcode != 0:
                        lock.acquire()
                        print("svg export failed (exit code {}): {}".format(exitcode, output))
                        lock.release()
                        continue
                    if killed:
                        break
                    if needTiling:
                        exitcode, output = repeat(filepath512, filepath1536)
                        if exitcode != 0:
                            lock.acquire()
                            print("repeat failed (exit code {}): {}".format(exitcode, output))
                            lock.release()
                            killed=True
                            continue
                        if killed:
                            break
                        exitcode, output = downsample(filepath1536, filepath384)
                        if exitcode != 0:
                            lock.acquire()
                            print("downsample failed (exit code {}): {}".format(exitcode, output))
                            lock.release()
                            killed=True
                            continue
                        if killed:
                            break
                        exitcode, output = crop(filepath384, filepath128)
                        if exitcode != 0:
                            lock.acquire()
                            print("crop failed (exit code {}): {}".format(exitcode, output))
                            lock.release()
                            killed=True
                            continue
                    else:
                        exitcode, output = downsampleNoRepeat(filepath512, filepath128)
                        if exitcode != 0:
                            lock.acquire()
                            print("downsampleNoRepeat failed (exit code {}): {}".format(exitcode, output))
                            print("filepath512: {}".format(filepath512))
                            print("filepath128: {}".format(filepath128))
                            lock.release()
                            killed=True
                            continue
                    
                lock.acquire() # will block if lock is already held
                total=total+1
                print("Converting...{}/{}".format(total, totalF))
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
            killed = True
            lock.release()
            
if usethreading:
    threads=[None]*num_threads
    sublists=[None]*num_threads
    iLen = int(len(fileList)/num_threads)
    if len(fileList) % num_threads != 0:
        iLen=iLen+1
    splitsize = iLen
    for i in range(num_threads):
        istart = i*splitsize
        iend = istart+splitsize if istart+splitsize < len(fileList) else len(fileList)
        sublists[i]=fileList[istart:iend]
    totallen = 0
    for list in sublists:
        totallen += len(list)
    if totallen != len(fileList):
        raise Exception("Illegal state")

    print("Starting...")


    for i in range(num_threads):
        threads[i] = threading.Thread(name='worker #'+str(i), target=work, args=(i,sublists[i], ))
    for i in range(num_threads):
        threads[i].start()
    time.sleep(111)
    for i in range(num_threads):
        threads[i].join()
else:
    sublists = fileList[:]
    work(0, sublists)



    

