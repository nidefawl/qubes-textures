import os, subprocess
import itertools as itertools 
import threading
import time
import signal
import sys
import codecs
import traceback
import colorsys

from xml.dom import minidom
from convertcfg import outdir
from convertcfg import pathInkscape

killed=False
def signal_handler(signal, frame):
    global killed
    killed=True
    print('Abort!')
    sys.exit(1)
signal.signal(signal.SIGINT, signal_handler)



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
    print('Handling %s exception with message "%s" in %s' % \
        (exc_type.__name__, exc_value, threading.current_thread().name))
    traceback.print_exc()


def mkdir_p(path):
    global lock
    lock.acquire()
    if not os.path.exists(path):
        os.makedirs(path)
    lock.release()
    
lock = threading.Lock()
killed=False
def getCSSAttr(path, attr):
    cssStyle = path.attributes["style"].value
    attr_dict = {}
    for pair in cssStyle.split(";"):
        splitPair = pair.split(":")
        if len(splitPair) == 2:
            attr_dict[splitPair[0]]=splitPair[1]
    return attr_dict[attr]
def setCSSAttr(path, attr, val):
    cssStyle = path.attributes["style"].value
    attr_dict = {}
    for pair in cssStyle.split(";"):
        splitPair = pair.split(":")
        if len(splitPair) == 2:
            attr_dict[splitPair[0]]=splitPair[1]
    attr_dict[attr] = val
    cssStyle = ';'.join("%s:%s" % (key,val) for (key,val) in attr_dict.items())
    path.setAttribute("style", cssStyle)
def findColors(file):
    colorMap = {}
    svg = minidom.parse(open(file))
    for g in svg.getElementsByTagName("g"):
        if "inkscape:label" in g.attributes:
            label = g.attributes["inkscape:label"].value
            if "BG" in label:
                bgpath = g.getElementsByTagName("path")[0]
                colorMap["bg"] = getCSSAttr(bgpath, "fill")
            else:
                for path in g.getElementsByTagName("path"):
                    if "inkscape:label" not in path.attributes:
                        continue
                    if path.attributes["inkscape:label"].value.startswith("#light"):
                        colorMap["light"] = getCSSAttr(path, "fill")
                    if path.attributes["inkscape:label"].value.startswith("#front"):
                        colorMap["front"] = getCSSAttr(path, "fill")
                    if path.attributes["inkscape:label"].value.startswith("#dark"):
                        colorMap["dark"] = getCSSAttr(path, "fill")
    if len(colorMap) != 4:
        raise Exception("Colors not found in "+file+": "+str(colorMap))
    return colorMap
def parseSetColor(path, color_set, path_label, color_type):
    base_color = color_set[1][color_type]
    if path_label:
        split = path_label.split("_")
        options = split[1] if len(split) > 1 else None
        if options is not None:
            foption = int(options)/255.0
            color_hls = list(hex_to_hls(base_color))
            color_hls[1] = max(0, min(1, color_hls[1]+foption))
            base_color = hls_to_hex(color_hls)
    setCSSAttr(path, "fill", base_color)
def makeTexture(file, color_set, file_out, unhide_border=False, outdir="SVG\\stones"):
    global lock
    global total
    global totalF
    global killed
    global colors
    exitcode=0
    output=""
    try:
        lock.acquire()
        print(file+" -> "+file_out)
        lock.release()
        svg = minidom.parse(open(file))
        layers = {}
        bg_node = None
        copyNodes = []
        for g in svg.getElementsByTagName("g"):
            if "inkscape:label" in g.attributes:
                label = g.attributes["inkscape:label"].value
                if "BG" in label:
                    bg_node = g
                    continue
                if "border" in label.lower():
                    continue
                if "fixed" in label.lower():
                    continue
                copyNodes.append(g)
        svg_root_node = svg.getElementsByTagName("svg")[0]
        coloredNodes = {"light":[], "dark":[], "front":[]}
        for path in bg_node.getElementsByTagName("path"):
            if "style" in path.attributes:
                setCSSAttr(path, "fill", color_set[1]["bg"])
        for g in svg.getElementsByTagName("g"):
            for path in g.getElementsByTagName("path"):
                path_label = None
                if "inkscape:label" in path.attributes:
                   path_label = path.attributes["inkscape:label"].value
                fillcolor = getCSSAttr(path, "fill")
                if fillcolor == "#000000":
                    if "darkopacity" in color_set[1]:
                            opac = float(getCSSAttr(path, "fill-opacity"))
                            setCSSAttr(path, "fill-opacity", opac*color_set[1]["darkopacity"])
                    parseSetColor(path, color_set, path_label, "dark")
                if fillcolor == "#ffffff":
                    parseSetColor(path, color_set, path_label, "light")
                if path_label is None:
                    continue
                if path_label.startswith("#light"):
                    parseSetColor(path, color_set, path_label, "light")
                elif path_label.startswith("#front"):
                    parseSetColor(path, color_set, path_label, "front")
                    if "frontopacity" in color_set[1]:
                        opac = float(getCSSAttr(path, "fill-opacity"))
                        setCSSAttr(path, "fill-opacity", color_set[1]["frontopacity"])
                elif path_label.startswith("#dark"):
                    parseSetColor(path, color_set, path_label, "dark")
                
            
            
        for copyNode in copyNodes:
            nIdx = 0
            for x in range(-1, 2):
                for z in range(-1, 2):
                    if x==0 and z == 0:
                        continue
                    nIdx += 1
                    n = copyNode.cloneNode(deep=True)
                    nName = copyNode.attributes["inkscape:label"].value+"_copy_"+str(nIdx)
                    n.setAttribute("inkscape:label", nName)
                    n_transform = n.getAttribute("transform")
                    n_offset = (0,0)
                    if len(n_transform):
                        n_offset = n_transform.split("translate")[1][1:-1].split(",")
                        n_offset = (float(n_offset[0]), float(n_offset[1]))
                        
                    nTransform = "translate(%d, %d)" % (x*512+n_offset[0], z*512+n_offset[1]);
                    n.setAttribute("transform", nTransform)
                    svg_root_node.appendChild(n)
               
        if unhide_border:
            # border = None
            for g in svg.getElementsByTagName("g"):
                if "inkscape:label" in g.attributes:
                    label = g.attributes["inkscape:label"].value
                    if "border" in label.lower():
                        g.attributes['style'].value = 'display:inline'
            # if border is not None:
            #     svg_root_node.removeChild(border)
            #     svg_root_node.appendChild(border)

        export = svg.toxml()
        codecs.open(outdir+"\\"+file_out+".svg", "w", encoding="utf8").write(export)
        
    except:
        lock.acquire() # will block if lock is already held
        printexc()
        lock.release()
def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(float(int(value[i:i + lv // 3], 16))/255.0 for i in range(0, lv, lv // 3))
def hex_to_hls(value):
    rgb = hex_to_rgb(value)
    return colorsys.rgb_to_hls(*rgb)
def rgb_to_hex(rgb):
    rgb_int = tuple(round(f*255.0) for f in rgb)
    return '#%02x%02x%02x' % rgb_int

def hls_to_hex(value):
    return rgb_to_hex(colorsys.hls_to_rgb(*value))
def makeColorSetting(hex, lit=(0.33, 1.25, 0.66), sat=(1,1,1)):
    map = {}
    hls=hex_to_hls(hex)
    hls_bg = list(hls[:])
    print(hls_bg)
    hls_bg[1] *= lit[0]
    hls_bg[2] *= sat[0]
    print(hls_bg)
    map["bg"] = hls_to_hex(hls_bg)
    hls_light = list(hls[:])
    hls_light[1] *= lit[1]
    hls_light[2] *= sat[1]
    map["light"] = hls_to_hex(hls_light)
    hls_dark = list(hls[:])
    hls_dark[1] *= lit[2]
    hls_dark[2] *= sat[2]
    map["dark"] = hls_to_hex(hls_dark)
    map["front"] = hex
    map["hls"] = hls
    return map
def fixedColors(front, bg, light, dark):
    map = {}
    map["bg"] = bg
    map["light"] = "#ffffff"
    map["dark"] = "#000000"
    map["front"] = front
    map["hls"] = hex_to_hls(front)
    return map
#granite = findColors("SVG\\rocks\\granite.svg")
#diorite = findColors("SVG\\rocks\\diorite.svg")
#marble = findColors("SVG\\rocks\\marble.svg")
#basalt = findColors("SVG\\rocks\\basalt.svg")
#print "marble {}".format(marble)
#print "granite {}".format(granite)
#print "diorite {}".format(diorite)
#print "basalt {}".format(basalt)

#colors = [("granite", granite), ("marble",marble), ("diorite",diorite), ("basalt",basalt)]
colors = []
# colors.append(("acacia", fixedColors(*(["#b36254"]*4)), "wood"))
# colors.append(("birch", fixedColors(*(["#d1944b"]*4)), "wood"))
# colors.append(("cocoa", fixedColors(*(["#d89634"]*4)), "wood"))
# colors.append(("coconut", fixedColors(*(["#532f25"]*4)), "wood"))
# colors.append(("ebony", fixedColors(*(["#333333"]*4)), "wood"))
# colors.append(("mahagoni", fixedColors(*(["#8c2317"]*4)), "wood"))
# colors.append(("oak", fixedColors(*(["#a2865a"]*4)), "wood"))
pineSetting = ("pine", fixedColors(*(["#efe2bf"]*4)), "wood")
hls_light = list(pineSetting[1]["hls"][:])
hls_light[1] *= 0.88
pineSetting[1]["bg"]=hls_to_hex(hls_light)
hls_light[1] *= 0.98
pineSetting[1]["front"]=hls_to_hex(hls_light)
hls_light[1] *= 0.8
hls_light[2] *= 0.7
pineSetting[1]["dark"]=hls_to_hex(hls_light)
pineSetting[1]["darkopacity"]=1.4
pineSetting[1]["frontopacity"]=0.4
colors.append(pineSetting)
# colors.append(("redwood", fixedColors(*(["#bb4e13"]*4)), "wood"))
# colors.append(("spruce", fixedColors(*(["#b38d54"]*4)), "wood"))
# colors.append(("walnut", fixedColors(*(["#91632b"]*4)), "wood"))
# colors.append(("willow", fixedColors(*(["#80aa8a"]*4)), "wood"))
outdir_generated=r"C:\dev\workspace_game\textures_svg\SVG_generated\wood\\"
mkdir_p(outdir_generated)

for color_set in colors:
    makeTexture("SVG\\template\\"+color_set[2]+".svg", color_set, color_set[0]+"_1", outdir=outdir_generated)
    makeTexture("SVG\\template\\"+color_set[2]+".svg", color_set, color_set[0]+"_0", outdir=outdir_generated, unhide_border=True)
    makeTexture("SVG\\template\\wood_parquet_0.svg", color_set, color_set[0]+"_parquet_0", outdir=outdir_generated)
    makeTexture("SVG\\template\\wood_parquet_1.svg", color_set, color_set[0]+"_parquet_1", outdir=outdir_generated)
    makeTexture("SVG\\template\\wood_parquet_2.svg", color_set, color_set[0]+"_parquet_2", outdir=outdir_generated)
    makeTexture("SVG\\template\\wood_parquet_3.svg", color_set, color_set[0]+"_parquet_3", outdir=outdir_generated)


print("Starting...")


# for i in range(num_threads):
#     threads[i] = threading.Thread(name='worker #'+str(i), target=work, args=(i,sublists[i], ))
# for i in range(num_threads):
#     threads[i].start()
# while total < len(fileList)-5:
#     time.sleep(1)
    

# for i in range(num_threads):
#     threads[i].join()

    


